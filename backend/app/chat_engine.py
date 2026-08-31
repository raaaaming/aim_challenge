# -*- coding: utf-8 -*-
"""
대화 엔진.

핵심 규칙
  1) 평가 기준(취향 지표) 중 **P0 를 먼저** 질문한다. P0 가 모두 확보된 뒤 P1 을 묻는다.
  2) 사용자의 대답으로 해당 지표에 점수를 매기기 어려우면(확신도 < 0.5)
     **같은 지표를 더 구체적인 질문으로 바꿔 한 번 더** 물어본다. (clarify)
  3) 모든 지표가 정리되면 정확히
     "그렇다면 당신에게 추천하는 여행지는?" 메시지 + 결과 화면으로 가는 임베드를 보낸다.

LLM 키가 없으면 내장 규칙 엔진이 같은 흐름을 그대로 수행한다.
"""
from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from . import llm, recommender, repository as repo
from . import supabase as sb

log = logging.getLogger("pohang.chat")

MIN_CONFIDENCE = 0.5      # 이 값 이상이어야 '점수를 매길 수 있었다'고 본다
MAX_ASK_PER_AXIS = 2      # 같은 지표는 최대 2번까지 (원질문 1 + 되묻기 1)
MAX_TURNS = 16

FINAL_QUESTION = "그렇다면 당신에게 추천하는 여행지는?"

GREETING = (
    "안녕하세요, 포항항입니다. ⚓\n"
    "포항의 여행지 20곳 중 딱 한 곳을 골라 드릴게요.\n"
    "몇 가지만 여쭤볼 테니 편하게 대답해 주세요."
)

_SESSIONS: Dict[str, "Session"] = {}


# ===========================================================================
# 세션
# ===========================================================================
class Session:
    def __init__(self):
        self.id = str(uuid.uuid4())
        self.slots: Dict[str, Dict[str, Any]] = {}   # axis -> {value, confidence, evidence}
        self.asked: Dict[str, int] = {}              # axis -> 질문 횟수
        self.history: List[Dict[str, str]] = []      # {role, content}
        self.current_axis: Optional[str] = None
        self.finished = False
        self.result: Optional[Dict[str, Any]] = None
        self.turns = 0

    # --- 진행 상태 -------------------------------------------------------
    def settled(self, key: str) -> bool:
        s = self.slots.get(key)
        if s and float(s.get("confidence") or 0) >= MIN_CONFIDENCE:
            return True
        return self.asked.get(key, 0) >= MAX_ASK_PER_AXIS

    def pending_axes(self) -> List[Dict[str, Any]]:
        """아직 정리되지 않은 축을 P0 → P1 순으로."""
        axes = repo.axes()
        p0 = [a for a in axes if a["priority"] == "P0" and not self.settled(a["key"])]
        p1 = [a for a in axes if a["priority"] == "P1" and not self.settled(a["key"])]
        return p0 + p1

    def progress(self) -> Dict[str, int]:
        axes = repo.axes()
        return {
            "total": len(axes),
            "resolved": sum(
                1 for a in axes
                if float((self.slots.get(a["key"]) or {}).get("confidence") or 0) >= MIN_CONFIDENCE
            ),
            "settled": sum(1 for a in axes if self.settled(a["key"])),
        }

    def to_payload(self) -> Dict[str, Any]:
        return {
            "slots": self.slots,
            "messages": self.history,
            "finished": self.finished,
            "result_place_id": (self.result or {}).get("place", {}).get("place_id"),
        }

    def persist(self):
        sb.upsert_session(self.id, self.to_payload())


def get_session(sid: str) -> Optional[Session]:
    return _SESSIONS.get(sid)


def start_session() -> Tuple[Session, List[Dict[str, Any]]]:
    s = Session()
    _SESSIONS[s.id] = s
    first = s.pending_axes()[0]
    s.current_axis = first["key"]
    s.asked[first["key"]] = 1
    msgs = [
        {"role": "assistant", "text": GREETING},
        {"role": "assistant", "text": first["question"], "axis": first["key"]},
    ]
    s.history.append({"role": "assistant", "content": GREETING})
    s.history.append({"role": "assistant", "content": first["question"]})
    s.persist()
    return s, msgs


# ===========================================================================
# 규칙 기반 추출기 (LLM 키가 없을 때 / LLM 실패 시)
# ===========================================================================
_UNSURE = re.compile(
    r"(모르|글쎄|상관\s*없|아무거나|아무렇게|딱히|그냥|둘\s*다|반반|고민|애매|잘\s*몰)"
)

# (정규식, 축 위 목표값, 확신도)
#   exclusive=True 패턴이 맞으면 같은 축의 다른 패턴은 무시한다.
RULES: Dict[str, List[Tuple]] = {
    "transit": [
        (r"(대중교통|버스|지하철|기차|ktx|포항역|터미널|뚜벅|도보|걸어|택시)", 8.5, 0.8),
        (r"(자차|자가용|렌트|렌터카|차\s*가지|차\s*로|운전|드라이브)", 2.0, 0.8),
    ],
    "participation": [
        (r"(체험|참여|직접|해보|만들|액티비티|활동적|몸으로|타보|낚시|서핑)", 8.5, 0.85),
        (r"(전시|관람|구경|감상|보는|보고|눈으로|박물관|미술|조용히\s*보)", 1.5, 0.85),
    ],
    "nature_food": [
        (r"(미식|맛집|먹|음식|회|대게|과메기|식도락|맛있)", 9.0, 0.85),
        (r"(자연|경치|경관|풍경|바다|산|계곡|폭포|일출|노을|절경)", 1.5, 0.85),
    ],
    "companion": [
        (r"(혼자|혼행|나\s*홀로|1인|솔로)", 0.5, 0.9, True),
        (r"(아이|애들|아기|유아|자녀|어린|가족|부모님|엄마|아빠|단체|회사|동료|아이들)", 8.5, 0.85),
        (r"(연인|여자친구|남자친구|커플|둘이|친구\s*랑|친구\s*한|둘\s*이서)", 3.0, 0.7),
    ],
    "barrier_free": [
        # 부정형(“많이 걷는 건 힘들어요”)을 먼저 단독으로 잡는다
        (r"(걷는\s*건?\s*힘들|걷기\s*힘들|많이\s*못\s*걷|오래\s*못\s*걷|걷는\s*거\s*싫|"
         r"등산은?\s*좀?\s*(힘|싫|무리|그러)|계단은?\s*좀?\s*(힘|싫|무리))", 8.5, 0.9, True),
        (r"(등산|트레킹|많이\s*걷|계단|경사|빡세|체력|땀|험한|올라)", 1.5, 0.8),
        (r"(평지|편하게|무장애|휠체어|유모차|다리가|무릎|힘들|걷기\s*싫|짧게\s*걷|많이\s*못\s*걷)", 8.5, 0.85),
    ],
    "liveliness": [
        (r"(한적|조용|고요|사람\s*없|붐비는\s*건|한산|여유|힐링|쉬고)", 1.5, 0.85),
        (r"(활기|북적|핫플|사람\s*많|시끌|번화|인기\s*많|떠들)", 8.5, 0.85),
    ],
    "depth": [
        (r"(역사|문화|유적|박물관|배우|공부|스토리|이야기|유래|설화|전통|깊게|인문)", 8.5, 0.85),
        (r"(가볍|부담\s*없|편하게\s*즐|힐링|쉬엄|그냥\s*놀|사진만)", 1.5, 0.8),
    ],
    "indoor": [
        (r"(실내|비\s*와|비가|더워|추워|날씨\s*상관|에어컨|안에서)", 8.5, 0.85),
        (r"(야외|바깥|밖|바람|공기|탁\s*트인|노천|햇빛)", 1.0, 0.85),
    ],
    "budget": [
        (r"(무료|공짜|0원|안\s*쓰|아끼|저렴|가성비|돈\s*없|최소)", 1.0, 0.85),
        (r"(제대로|많이\s*쓸|비싸도|플렉스|고급|여유\s*있|상관\s*없이\s*쓸|5만|십만|10만)", 8.5, 0.8),
        (r"(적당|보통|2~?3만|2만|3만|중간)", 5.0, 0.7),
    ],
    "duration": [
        (r"(반나절|하루\s*종일|오래|길게|푹|종일|4시간|5시간|6시간)", 8.5, 0.85),
        (r"(짧게|잠깐|30분|찍고|금방|후딱|1시간|한\s*시간|가볍게\s*보고)", 1.5, 0.85),
        (r"(두\s*어\s*시간|2시간|3시간|적당히)", 5.0, 0.7),
    ],
}


def rule_extract(axis_key: str, text: str) -> Optional[Dict[str, Any]]:
    """대상 축에 대해 사용자 발화를 0~10 값으로 환산."""
    t = (text or "").strip().lower()
    if not t:
        return None
    if _UNSURE.search(t) and not any(
        re.search(r[0], t) for r in RULES.get(axis_key, [])
    ):
        return None

    hits = []
    for rule in RULES.get(axis_key, []):
        pat, val, conf = rule[0], rule[1], rule[2]
        exclusive = len(rule) > 3 and rule[3]
        m = re.search(pat, t)
        if m:
            if exclusive:
                return {"value": val, "confidence": conf,
                        "evidence": f"'{m.group(0)}' 라고 답함"}
            hits.append((val, conf, m.group(0)))
    if not hits:
        return None
    if len(hits) == 1:
        v, c, ev = hits[0]
        return {"value": v, "confidence": c, "evidence": f"'{ev}' 라고 답함"}
    # 상충되는 신호가 여럿이면 평균 + 확신도 하향
    v = sum(h[0] for h in hits) / len(hits)
    return {
        "value": round(v, 1),
        "confidence": 0.45,
        "evidence": "상반된 표현이 함께 등장: " + ", ".join(f"'{h[2]}'" for h in hits),
    }


def rule_extract_all(text: str, target: Optional[str]) -> Dict[str, Dict[str, Any]]:
    """대상 축은 물론, 발화에 드러난 다른 축도 함께 줍는다."""
    out: Dict[str, Dict[str, Any]] = {}
    for key in RULES:
        r = rule_extract(key, text)
        if not r:
            continue
        if key != target:
            r = {**r, "confidence": min(float(r["confidence"]), 0.7)}
        out[key] = r
    return out


# ===========================================================================
# LLM 기반 추출 + 질문 생성
# ===========================================================================
def _axes_spec() -> str:
    lines = []
    for a in repo.axes():
        lines.append(
            f"- key={a['key']} | {a['label']} | 우선순위 {a['priority']} | "
            f"0.0={a['low']} / 10.0={a['high']}"
        )
    return "\n".join(lines)


SYSTEM_PROMPT = """당신은 포항 여행지 추천 서비스 '포항항'의 상담 챗봇입니다.
사용자와 한국어로 자연스럽게 대화하면서, 아래 '취향 지표' 각각에 대해 사용자를 0.0~10.0 사이의 값으로 파악하는 것이 임무입니다.

[취향 지표]
{axes}

[반드시 지킬 규칙]
1. 우선순위 P0 지표를 먼저 파악합니다. P0 가 전부 끝난 뒤에 P1 을 묻습니다.
2. 한 번에 하나의 지표만 질문합니다. 질문은 2문장 이내로 짧고 구어체로 씁니다.
3. 사용자의 대답이 모호해서 그 지표에 점수를 매기기 어려우면(확신도 0.5 미만),
   다른 지표로 넘어가지 말고 **같은 지표를 더 구체적인 예시나 양자택일로 바꿔서 다시** 물어보세요.
   이때 mode 는 "clarify" 입니다. 앞선 질문을 그대로 반복하면 안 됩니다.
4. 사용자가 한 문장에서 여러 지표를 동시에 드러내면 updates 에 모두 담으세요.
5. 사용자의 직전 대답에 짧게 공감/반응한 뒤 다음 질문을 이어가세요.
6. 여행지 이름을 먼저 언급하거나 추천하지 마세요. 추천은 시스템이 계산합니다.

[출력 형식] 아래 JSON 만 출력합니다. 다른 텍스트 금지.
{{
  "updates": [
    {{"axis": "<지표 key>", "value": <0.0~10.0>, "confidence": <0.0~1.0>, "evidence": "<사용자 발화 근거 한 줄>"}}
  ],
  "mode": "ask" | "clarify",
  "target_axis": "<이번에 질문할 지표 key>",
  "message": "<사용자에게 보낼 한국어 메시지>"
}}"""


def _state_brief(s: Session) -> str:
    lines = []
    axmap = repo.axis_map()
    for a in repo.axes():
        slot = s.slots.get(a["key"])
        if slot:
            lines.append(
                f"- {a['key']}: value={slot['value']} confidence={slot['confidence']} "
                f"(근거: {slot.get('evidence','')})"
            )
        else:
            lines.append(f"- {a['key']}: 미파악 (질문 {s.asked.get(a['key'], 0)}회)")
    pend = s.pending_axes()
    nxt = pend[0]["key"] if pend else "(없음 — 모두 파악됨)"
    cur = s.current_axis
    cur_conf = float((s.slots.get(cur) or {}).get("confidence") or 0) if cur else 0
    return (
        "[현재 파악 상태]\n" + "\n".join(lines) +
        f"\n\n[직전에 질문한 지표] {cur} (현재 확신도 {cur_conf})"
        f"\n[아직 안 끝난 지표 중 우선순위 최상단] {nxt}"
        f"\n[안내] 직전 지표의 확신도가 0.5 미만이고 그 지표를 아직 1번만 물었다면 mode=clarify 로 그 지표를 다시 물으세요."
    )


async def _llm_turn(s: Session, user_text: str) -> Optional[Dict[str, Any]]:
    system = SYSTEM_PROMPT.format(axes=_axes_spec())
    msgs: List[Dict[str, str]] = []
    for h in s.history[-10:]:
        msgs.append({"role": h["role"], "content": h["content"]})
    msgs.append({"role": "user", "content": f"{user_text}\n\n---\n{_state_brief(s)}"})
    try:
        return await llm.complete_json(system, msgs, temperature=0.5)
    except Exception as e:
        log.warning("LLM 턴 실패 → 규칙 엔진 폴백: %s", e)
        return None


# ===========================================================================
# 메인 처리
# ===========================================================================
def _merge_updates(s: Session, updates: List[Dict[str, Any]]):
    axkeys = {a["key"] for a in repo.axes()}
    for u in updates or []:
        key = str(u.get("axis") or "").strip()
        if key not in axkeys:
            continue
        try:
            val = float(u.get("value"))
            conf = float(u.get("confidence"))
        except (TypeError, ValueError):
            continue
        val = max(0.0, min(10.0, val))
        conf = max(0.0, min(1.0, conf))
        prev = s.slots.get(key)
        # 확신도가 더 높은 관측만 덮어쓴다
        if prev and float(prev.get("confidence") or 0) > conf:
            continue
        s.slots[key] = {
            "value": round(val, 1),
            "confidence": round(conf, 2),
            "evidence": str(u.get("evidence") or "")[:300],
        }


def _finalize(s: Session) -> Dict[str, Any]:
    s.finished = True
    result = recommender.best_match(s.slots)
    s.result = result
    place = result["place"]

    sb.log_recommendation(
        s.id, place["place_id"], result["fit_score"],
        {k: v for k, v in s.slots.items()},
        result["ranking"][:5],
    )

    hints = [c["label"].split(" / ")[0] for c in result["matched_axes"][:3]]
    embed = {
        "type": "recommendation",
        "place_id": place["place_id"],
        "fit_score": result["fit_score"],
        "title": "당신을 위한 포항 한 곳",
        "subtitle": f"취향 일치도 {result['fit_score']:.0f}%",
        "hints": hints,
        "cta": "결과 열어보기",
    }

    wrap = _wrap_up_text(s)
    msgs = [{"role": "assistant", "text": wrap}] if wrap else []
    msgs.append({"role": "assistant", "text": FINAL_QUESTION, "embed": embed})

    s.history.append({"role": "assistant", "content": FINAL_QUESTION})
    s.persist()
    return {"messages": msgs, "finished": True, "embed": embed,
            "progress": s.progress(), "session_id": s.id}


def _wrap_up_text(s: Session) -> str:
    axmap = repo.axis_map()
    parts = []
    for key, slot in s.slots.items():
        if float(slot.get("confidence") or 0) < MIN_CONFIDENCE:
            continue
        a = axmap.get(key)
        if not a:
            continue
        v = float(slot["value"])
        if v <= 3.5:
            side = a["low"].split(" (")[0]
        elif v >= 6.5:
            side = a["high"].split(" (")[0]
        else:
            continue
        parts.append(side)
    if not parts:
        return "말씀해 주신 내용 잘 정리했어요."
    picked = ", ".join(parts[:4])
    return f"말씀해 주신 걸 정리하면 — {picked} 쪽이시네요. 딱 맞는 곳이 하나 떠올랐어요."


async def process(s: Session, user_text: str) -> Dict[str, Any]:
    if s.finished:
        return {
            "messages": [{"role": "assistant", "text": FINAL_QUESTION,
                          "embed": (s.result or {}).get("embed")}],
            "finished": True, "progress": s.progress(), "session_id": s.id,
        }

    s.turns += 1
    s.history.append({"role": "user", "content": user_text})
    target_before = s.current_axis

    # ---- 1. 추출 ---------------------------------------------------------
    data = await _llm_turn(s, user_text) if llm.enabled() else None
    used_llm = data is not None

    if used_llm:
        _merge_updates(s, data.get("updates") or [])
    else:
        rule_updates = [
            {"axis": k, **v} for k, v in rule_extract_all(user_text, target_before).items()
        ]
        _merge_updates(s, rule_updates)

    # ---- 2. 다음에 무엇을 할지 백엔드가 확정 (LLM 판단을 검증) -----------
    mode, axis = _decide_next(s, target_before)

    if mode == "finish":
        return _finalize(s)

    # ---- 3. 메시지 확정 --------------------------------------------------
    ax = repo.axis_map()[axis]
    message = None
    if used_llm:
        cand = str(data.get("message") or "").strip()
        llm_mode = str(data.get("mode") or "").strip()
        llm_axis = str(data.get("target_axis") or "").strip()
        # LLM 이 백엔드와 같은 판단을 했을 때만 그 문장을 채택한다
        if cand and llm_axis == axis and llm_mode == mode:
            message = cand
    if message is None:
        message = ax["clarify"] if mode == "clarify" else ax["question"]

    s.current_axis = axis
    s.asked[axis] = s.asked.get(axis, 0) + 1
    s.history.append({"role": "assistant", "content": message})
    s.persist()

    return {
        "messages": [{"role": "assistant", "text": message, "axis": axis, "mode": mode}],
        "finished": False,
        "progress": s.progress(),
        "session_id": s.id,
        "debug": {
            "engine": "llm" if used_llm else "rule",
            "mode": mode,
            "axis": axis,
            "slots": s.slots,
        },
    }


def _decide_next(s: Session, target_before: Optional[str]) -> Tuple[str, Optional[str]]:
    """(mode, axis) 를 백엔드가 결정한다. mode ∈ ask | clarify | finish"""
    # 직전 질문 지표를 점수화하지 못했고 아직 되물을 기회가 남았으면 clarify
    if target_before:
        conf = float((s.slots.get(target_before) or {}).get("confidence") or 0)
        if conf < MIN_CONFIDENCE and s.asked.get(target_before, 0) < MAX_ASK_PER_AXIS:
            return "clarify", target_before

    if s.turns >= MAX_TURNS:
        return "finish", None

    pend = s.pending_axes()
    if not pend:
        return "finish", None
    return "ask", pend[0]["key"]
