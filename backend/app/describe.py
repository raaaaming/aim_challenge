# -*- coding: utf-8 -*-
"""
최종 결과 화면용 여행지 설명 '재생성'.

입력으로 허용되는 자료는 오직 CSV 의
    summary, embedding_text, evidence_text_1 ~ evidence_text_5
7개 필드뿐이다. 그 밖의 외부 지식·창작은 금지한다.
(여행지 이름은 CSV 의 place_name 을 그대로 쓴다.)

LLM 이 있으면 위 7개 필드만 넘겨 자연스러운 소개글로 재구성하고,
없거나 실패하면 동일 필드만으로 결정론적으로 조립한다.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from . import llm

log = logging.getLogger("pohang.describe")

SYSTEM = """당신은 여행지 소개 문안을 다시 쓰는 에디터입니다.

절대 규칙:
- 아래에 주어진 자료(summary / embedding_text / evidence_text_1~5) **안에 있는 정보만** 사용합니다.
- 자료에 없는 사실, 숫자, 지명, 영업시간, 요금, 평가를 새로 지어내면 안 됩니다.
- 자료 문장을 그대로 복사하지 말고, 자연스러운 새 문장으로 다시 씁니다.
- 존댓말, 담백하고 따뜻한 여행 매거진 톤. 과장된 감탄사는 쓰지 않습니다.

아래 JSON 형식으로만 출력합니다.
{
  "headline": "<12자 내외의 짧은 한 줄 카피>",
  "intro": "<2~3문장. 이곳이 어떤 곳인지>",
  "highlights": [
    {"title": "<6자 내외 소제목>", "body": "<1~2문장>"},
    {"title": "...", "body": "..."},
    {"title": "...", "body": "..."}
  ],
  "good_for": "<'이런 분께 잘 맞아요' 한 문장>",
  "keywords": ["<embedding_text 에서 뽑은 키워드>", "..."]
}"""


def _material(place: Dict[str, Any]) -> str:
    evs = place.get("evidence_texts") or []
    lines = [
        f"place_name: {place['place_name']}",
        f"summary: {place.get('summary','')}",
        f"embedding_text: {place.get('embedding_text','')}",
    ]
    for i, ev in enumerate(evs, 1):
        lines.append(f"evidence_text_{i}: {ev}")
    return "\n".join(lines)


def _keywords(place: Dict[str, Any]) -> List[str]:
    raw = (place.get("embedding_text") or "").split()
    name = re.sub(r"\s+", "", place["place_name"])
    out = []
    for w in raw:
        if re.sub(r"\s+", "", w) == name:
            continue
        if w and w not in out:
            out.append(w)
    return out[:5]


# ---------------------------------------------------------------------------
def fallback(place: Dict[str, Any]) -> Dict[str, Any]:
    """LLM 없이, 같은 7개 필드만으로 조립하는 결정론적 설명."""
    evs = [e for e in (place.get("evidence_texts") or []) if e]
    ev = (evs + [""] * 5)[:5]
    summary = place.get("summary", "")

    head = re.sub(r"(입니다|습니다)\.?$", "", summary).strip()
    head = head.split(",")[0].split(" 이자")[0]
    headline = (head[:22] + "…") if len(head) > 22 else head

    intro_parts = [summary]
    if ev[0]:
        intro_parts.append(ev[0])
    intro = " ".join(intro_parts)

    highlights = []
    if ev[1]:
        highlights.append({"title": "이런 분위기", "body": ev[1]})
    if ev[3]:
        highlights.append({"title": "대표 볼거리", "body": ev[3]})
    if ev[2]:
        highlights.append({"title": "이렇게 즐겨요", "body": ev[2]})

    return {
        "headline": headline or place["place_name"],
        "intro": intro,
        "highlights": highlights,
        "good_for": ev[4] or "",
        "keywords": _keywords(place),
        "generated_by": "template",
    }


def _validate(obj: Any, place: Dict[str, Any]) -> Dict[str, Any] | None:
    if not isinstance(obj, dict):
        return None
    hl = obj.get("highlights")
    if not isinstance(hl, list) or not hl:
        return None
    clean = []
    for h in hl[:4]:
        if isinstance(h, dict) and h.get("body"):
            clean.append({"title": str(h.get("title") or "")[:20],
                          "body": str(h["body"])[:400]})
    if not clean:
        return None
    intro = str(obj.get("intro") or "").strip()
    if len(intro) < 10:
        return None
    kws = obj.get("keywords")
    if not isinstance(kws, list) or not kws:
        kws = _keywords(place)
    return {
        "headline": str(obj.get("headline") or place["place_name"])[:40],
        "intro": intro[:800],
        "highlights": clean,
        "good_for": str(obj.get("good_for") or "")[:300],
        "keywords": [str(k)[:20] for k in kws][:6],
        "generated_by": "llm",
    }


async def regenerate(place: Dict[str, Any]) -> Dict[str, Any]:
    if not llm.enabled():
        return fallback(place)
    try:
        obj = await llm.complete_json(
            SYSTEM,
            [{"role": "user", "content": "[자료]\n" + _material(place)}],
            temperature=0.6,
        )
        got = _validate(obj, place)
        if got:
            return got
        log.warning("설명 재생성 검증 실패 → 템플릿 폴백 (%s)", place["place_id"])
    except Exception as e:
        log.warning("설명 재생성 실패 → 템플릿 폴백: %s", e)
    return fallback(place)
