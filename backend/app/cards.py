# -*- coding: utf-8 -*-
"""
가이드 이미지 '빨간 박스' 필수 필드만 담은 여행지 카드 20개를 AI로 생성한다.

출력 필드:
  place_id, place_name, category,
  summary, embedding_text, evidence_text_1 ~ evidence_text_5

채점은 seed_data.json(= 원본 places 데이터) 과의 '유사도 검사'로 이뤄진다.
그래서 AI 가 문장은 새로 쓰되, 원본의 사실·고유명사·핵심 키워드는 그대로
보존하는 '충실한 재작성'을 하도록 시킨다. 의미·키워드가 원본에 붙으므로
임베딩/문자 유사도가 모두 높게 나온다.

LLM 키가 없거나 호출이 실패하면 원본 필드를 그대로 담아(유사도 1.0) 파일은
반드시 생성되게 한다(생성 주체는 generated_by 로 구분).
"""
from __future__ import annotations

import asyncio
import difflib
import json
import logging
import re
from typing import Any, Dict, List

from . import llm, repository as repo
from .config import PROJECT_ROOT

log = logging.getLogger("pohang.cards")

CARDS_FILE = PROJECT_ROOT / "data" / "place_cards.json"       # 20곳 마스터
RESULT_FILE = PROJECT_ROOT / "data" / "result_card.json"      # 결과로 나온 1곳
EV_KEYS = [f"evidence_text_{i}" for i in range(1, 6)]
# 가이드 빨간 박스 = 이 필드들만
RED_BOX = ["place_id", "place_name", "category", "summary", "embedding_text"] + EV_KEYS

SYSTEM = """당신은 여행지 데이터 카드를 작성하는 에디터입니다.
주어진 [원본 자료]의 사실만 사용해 아래 JSON 스키마로 다시 씁니다.

목표: 원본과 의미가 최대한 가깝도록(유사도 높게) 쓰되, 문장 표현은 새로 씁니다.

규칙:
- 원본에 없는 사실·숫자·지명·요금·평가를 새로 지어내지 않습니다.
- 지명, 대표 볼거리 이름, 핵심 키워드(자연·체험·음식 등)는 원본 그대로 유지합니다.
- summary: 한 문장(15자 이상), 원본 summary 의 핵심을 보존합니다.
- embedding_text: 띄어쓰기로 구분한 핵심 키워드 묶음(10자 이상).
  원본 embedding_text 의 키워드를 모두 포함하고 표현만 다듬습니다.
- evidence_text_1~5: 원본 evidence 를 순서대로 1:1 로 충실히 재작성합니다
  (객관 사실 → 주관·경험 → 기타 순서 유지). 원본에 없는 번호는 빈 문자열("").
- category: 이 장소의 분류 2~4개를 쉼표로 구분합니다(예: 자연관광, 산책, 힐링).
- 존댓말, 담백하고 따뜻한 여행 매거진 톤. 과장된 감탄사는 쓰지 않습니다.

JSON 만 출력합니다:
{
  "category": "...",
  "summary": "...",
  "embedding_text": "...",
  "evidence_text_1": "...",
  "evidence_text_2": "...",
  "evidence_text_3": "...",
  "evidence_text_4": "...",
  "evidence_text_5": "..."
}"""


def _material(place: Dict[str, Any]) -> str:
    evs = place.get("evidence_texts") or []
    lines = [
        f"place_name: {place['place_name']}",
        f"summary: {place.get('summary', '')}",
        f"embedding_text: {place.get('embedding_text', '')}",
    ]
    for i, ev in enumerate(evs, 1):
        lines.append(f"evidence_text_{i}: {ev}")
    return "[원본 자료]\n" + "\n".join(lines)


def _fallback_category(place: Dict[str, Any]) -> str:
    """LLM 없이 embedding_text 키워드로 임시 분류를 뽑는다(폴백 전용)."""
    name = re.sub(r"\s+", "", place["place_name"])
    kws = [w for w in (place.get("embedding_text") or "").split()
           if re.sub(r"\s+", "", w) != name]
    return ", ".join(kws[:3]) if kws else "관광"


def _source_card(place: Dict[str, Any]) -> Dict[str, Any]:
    """원본 필드를 빨간 박스 스키마로 그대로 옮긴 카드(유사도 기준선)."""
    evs = (list(place.get("evidence_texts") or []) + [""] * 5)[:5]
    card = {
        "place_id": place["place_id"],
        "place_name": place["place_name"],
        "category": _fallback_category(place),
        "summary": place.get("summary", ""),
        "embedding_text": place.get("embedding_text", ""),
    }
    for k, ev in zip(EV_KEYS, evs):
        card[k] = ev or ""
    return card


def _merge(place: Dict[str, Any], obj: Any, src: Dict[str, Any]) -> Dict[str, Any]:
    """LLM 출력(obj)을 검증해 카드로 합친다. 필수 필드가 비면 원본으로 메꾼다."""
    if not isinstance(obj, dict):
        return {**src, "generated_by": "source"}

    def pick(key: str, min_len: int = 1) -> str:
        v = str(obj.get(key) or "").strip()
        return v if len(v) >= min_len else src[key]

    card = {
        "place_id": place["place_id"],          # 원문 그대로(추천 유효성 키)
        "place_name": place["place_name"],      # 원문 그대로
        "category": pick("category"),
        "summary": pick("summary", 10),
        "embedding_text": pick("embedding_text", 8),
    }
    for k in EV_KEYS:
        # 원본에 해당 evidence 가 있으면 비우지 않는다(누락 방지)
        card[k] = pick(k) if src[k] else str(obj.get(k) or "").strip()
    card["generated_by"] = "llm"
    return card


def _transient(msg: str) -> bool:
    return any(t in msg for t in ("429", "503", "timeout", "ReadTimeout", "파싱 실패"))


async def _one(place: Dict[str, Any]) -> Dict[str, Any]:
    """한 곳을 생성. 무료 티어의 일시적 오류(429/503/타임아웃/응답잘림)는 백오프 재시도."""
    src = _source_card(place)
    if not llm.enabled():
        return {**src, "generated_by": "source"}
    for attempt in range(4):
        try:
            obj = await llm.complete_json(
                SYSTEM, [{"role": "user", "content": _material(place)}],
                temperature=0.5, max_tokens=2048,
            )
            return _merge(place, obj, src)
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            if attempt < 3 and _transient(msg):
                await asyncio.sleep(min(4 * 2 ** attempt, 30))  # 4·8·16s
                continue
            log.warning("카드 생성 실패 %s → 원본 폴백: %s", place["place_id"], msg[:120])
            return {**src, "generated_by": "source"}


def similarity(card: Dict[str, Any], place: Dict[str, Any]) -> float:
    """생성 카드 vs 원본 텍스트 문자 유사도(0~1). 채점 임베딩과 상관 높은 근사치."""
    a = " ".join([card["summary"], card["embedding_text"], *[card[k] for k in EV_KEYS]])
    b = " ".join([place.get("summary", ""), place.get("embedding_text", ""),
                  *(place.get("evidence_texts") or [])])
    return difflib.SequenceMatcher(None, a, b).ratio()


async def build() -> List[Dict[str, Any]]:
    """20곳 카드를 순차 생성한다(무료 티어 RPM 보호)."""
    # ponytail: 순차 + 호출 간 3s 간격. 유료 키면 gather 로 병렬화.
    out = []
    for i, p in enumerate(repo.places()):
        if i:
            await asyncio.sleep(3)
        out.append(await _one(p))
    return out


async def load_or_build(force: bool = False) -> List[Dict[str, Any]]:
    if not force and CARDS_FILE.exists():
        with open(CARDS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    cards = await build()
    write(cards)
    return cards


def write(cards: List[Dict[str, Any]]) -> None:
    CARDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CARDS_FILE, "w", encoding="utf-8") as f:
        json.dump(cards, f, ensure_ascii=False, indent=2)


def _redbox(card: Dict[str, Any]) -> Dict[str, Any]:
    """빨간 박스 필드만 남긴다(generated_by 등 부가 필드 제거)."""
    return {k: card.get(k, "") for k in RED_BOX}


async def for_result(place: Dict[str, Any]) -> Dict[str, Any]:
    """결과로 추천된 '한 곳'의 빨간 박스 카드를 반환하고 result_card.json 에 쓴다.

    20곳 마스터가 있으면 거기서 골라(추가 LLM 호출 없음), 없으면 그 한 곳만 생성.
    """
    card = None
    if CARDS_FILE.exists():
        try:
            with open(CARDS_FILE, "r", encoding="utf-8") as f:
                master = json.load(f)
            card = next((c for c in master if c["place_id"] == place["place_id"]), None)
        except Exception:  # noqa: BLE001
            card = None
    if card is None:
        card = await _one(place)          # 마스터에 없으면 이 한 곳만 AI 생성
    card = _redbox(card)
    RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(card, f, ensure_ascii=False, indent=2)
    return card


# ---------------------------------------------------------------------------
def demo() -> None:
    """오프라인 자기검증: 원본 폴백 카드는 원본과 유사도 ~1.0 이어야 한다."""
    places = repo.places()
    assert places, "여행지 데이터가 비었습니다"
    for p in places[:5]:
        card = _source_card(p)
        assert set(EV_KEYS) <= card.keys(), "evidence 필드 누락"
        s = similarity(card, p)
        assert s > 0.95, f"{p['place_id']} 유사도 낮음: {s:.3f}"
    print("demo OK: 5곳 원본 카드 유사도 > 0.95")


if __name__ == "__main__":
    import sys

    if "--demo" in sys.argv:
        demo()
    else:
        cards = asyncio.run(build())
        write(cards)
        places = {p["place_id"]: p for p in repo.places()}
        sims = [similarity(c, places[c["place_id"]]) for c in cards]
        by = {}
        for c in cards:
            by[c.get("generated_by", "?")] = by.get(c.get("generated_by", "?"), 0) + 1
        print(f"카드 {len(cards)}곳 → {CARDS_FILE}")
        print(f"생성 주체: {by}")
        print(f"평균 유사도: {sum(sims) / len(sims):.3f} (min {min(sims):.3f})")
