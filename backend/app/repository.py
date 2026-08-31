# -*- coding: utf-8 -*-
"""
데이터 접근 계층.

1순위: Supabase(places / preference_axes + Storage 이미지)
2순위: 로컬 data/places.json  ← Supabase 미설정 시에도 앱이 그대로 동작하도록

두 경로 모두 동일한 형태의 dict 를 돌려준다.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from . import supabase as sb
from .config import settings

log = logging.getLogger("pohang.repo")

AXIS_KEYS = [
    "transit", "participation", "nature_food", "companion", "barrier_free",
    "liveliness", "depth", "indoor", "budget", "duration",
]

_cache: Dict[str, Any] = {"axes": None, "places": None, "source": None}


# ---------------------------------------------------------------------------
def _load_local() -> Dict[str, Any]:
    with open(settings.DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_place_from_supabase(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "place_id": row["place_id"],
        "place_name": row["place_name"],
        "slug": row.get("slug") or row["place_id"].lower(),
        "summary": row.get("summary") or "",
        "embedding_text": row.get("embedding_text") or "",
        "evidence_texts": [row.get(f"evidence_text_{i}") or "" for i in range(1, 6)],
        "scores": {k: float(row.get(f"score_{k}") or 0.0) for k in AXIS_KEYS},
        "score_reasons": {k: row.get(f"reason_{k}") or "" for k in AXIS_KEYS},
        "image_path": row.get("image_path"),
        "image_url": sb.image_url(row.get("image_path")),
    }


def _normalize_axis_from_supabase(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "key": row["key"],
        "label": row["label"],
        "priority": row["priority"],
        "low": row.get("low_label") or "",
        "high": row.get("high_label") or "",
        "question": row.get("question") or "",
        "clarify": row.get("clarify") or row.get("question") or "",
    }


def load(force: bool = False) -> Dict[str, Any]:
    """축 + 여행지 데이터를 캐시해서 반환."""
    if _cache["places"] is not None and not force:
        return _cache

    places: Optional[List[Dict[str, Any]]] = None
    axes: Optional[List[Dict[str, Any]]] = None
    source = "local"

    rows = sb.fetch_places()
    if rows:
        try:
            places = [_normalize_place_from_supabase(r) for r in rows]
            source = "supabase"
        except Exception as e:
            log.warning("Supabase places 파싱 실패 → 로컬 폴백: %s", e)
            places = None

    arows = sb.fetch_axes()
    if arows:
        try:
            axes = [_normalize_axis_from_supabase(r) for r in arows]
        except Exception as e:
            log.warning("Supabase axes 파싱 실패: %s", e)
            axes = None

    local = _load_local()
    if places is None:
        places = []
        for p in local["places"]:
            q = dict(p)
            q["image_url"] = sb.image_url(p.get("image_path"))
            places.append(q)
    if axes is None:
        axes = local["axes"]

    # Supabase 에서 왔더라도 원문 텍스트가 비어 있으면 로컬로 메꾼다(안전장치)
    local_by_id = {p["place_id"]: p for p in local["places"]}
    for p in places:
        lp = local_by_id.get(p["place_id"])
        if not lp:
            continue
        if not p.get("summary"):
            p["summary"] = lp["summary"]
        if not any(p.get("evidence_texts") or []):
            p["evidence_texts"] = lp["evidence_texts"]
        if not p.get("image_path"):
            p["image_path"] = lp.get("image_path")

    _cache.update({"axes": axes, "places": places, "source": source})
    return _cache


def axes() -> List[Dict[str, Any]]:
    return load()["axes"]


def places() -> List[Dict[str, Any]]:
    return load()["places"]


def source() -> str:
    return load()["source"]


def get_place(place_id: str) -> Optional[Dict[str, Any]]:
    for p in places():
        if p["place_id"] == place_id:
            return p
    return None


def axis_map() -> Dict[str, Dict[str, Any]]:
    return {a["key"]: a for a in axes()}
