# -*- coding: utf-8 -*-
"""
취향 슬롯 → 여행지 추천 엔진.

fit_score = (1 − 가중평균거리/10) × 100
  가중치 w_k = 우선순위가중치(P0=1.0, P1=0.6) × 사용자 확신도 c_k
사용자가 답하지 않았거나 판단 유보한 축은 c_k=0 이 되어 계산에서 빠진다.
"""
from __future__ import annotations

from typing import Any, Dict, List

from . import repository as repo

PRIORITY_WEIGHT = {"P0": 1.0, "P1": 0.6}


def score_place(place: Dict[str, Any], slots: Dict[str, Dict[str, Any]],
                axmap: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    num = 0.0
    den = 0.0
    contributions: List[Dict[str, Any]] = []

    for key, slot in slots.items():
        ax = axmap.get(key)
        if ax is None:
            continue
        conf = float(slot.get("confidence") or 0.0)
        if conf <= 0:
            continue
        target = float(slot.get("value"))
        w = PRIORITY_WEIGHT.get(ax["priority"], 1.0) * conf
        gap = abs(float(place["scores"][key]) - target)
        num += w * gap
        den += w
        contributions.append(
            {
                "axis": key,
                "label": ax["label"],
                "priority": ax["priority"],
                "user_value": round(target, 1),
                "place_value": round(float(place["scores"][key]), 1),
                "gap": round(gap, 1),
                "weight": round(w, 3),
                "reason": place["score_reasons"].get(key, ""),
            }
        )

    distance = (num / den) if den else 5.0
    fit = max(0.0, min(100.0, (1 - distance / 10.0) * 100.0))
    contributions.sort(key=lambda c: (-c["weight"], c["gap"]))
    return {
        "place_id": place["place_id"],
        "place_name": place["place_name"],
        "fit_score": round(fit, 1),
        "distance": round(distance, 3),
        "contributions": contributions,
    }


def rank(slots: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    axmap = repo.axis_map()
    out = [score_place(p, slots, axmap) for p in repo.places()]
    out.sort(key=lambda r: (-r["fit_score"], r["place_id"]))
    return out


def best_match(slots: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    ranking = rank(slots)
    top = ranking[0]
    place = repo.get_place(top["place_id"])

    # 잘 맞은 축 / 아쉬운 축
    matched = [c for c in top["contributions"] if c["gap"] <= 2.5][:4]
    tradeoff = [c for c in top["contributions"] if c["gap"] > 4.0][:2]

    return {
        "place": place,
        "fit_score": top["fit_score"],
        "matched_axes": matched,
        "tradeoff_axes": tradeoff,
        "contributions": top["contributions"],
        "ranking": [
            {"place_id": r["place_id"], "place_name": r["place_name"],
             "fit_score": r["fit_score"]}
            for r in ranking
        ],
        "runner_ups": [
            {"place_id": r["place_id"], "place_name": r["place_name"],
             "fit_score": r["fit_score"]}
            for r in ranking[1:4]
        ],
    }
