# -*- coding: utf-8 -*-
"""
Supabase 연동 모듈 (기술 스택.txt: "FastAPI 백엔드에서 supabase.py를 통해 연동").

이 파일이 Supabase 와 이야기하는 **유일한** 지점이다.
  - places / preference_axes 조회
  - chat_sessions 생성·갱신
  - recommendations 로그 적재
  - Storage(place-images) 버킷에서 여행지 이미지 public URL 획득

SUPABASE_URL / SUPABASE_*_KEY 가 설정돼 있지 않으면 `available == False` 가 되고,
호출부(repository.py)가 자동으로 로컬 data/places.json 폴백으로 전환한다.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .config import settings

log = logging.getLogger("pohang.supabase")

_client = None
_init_error: Optional[str] = None


def _get_client():
    """supabase-py 클라이언트 싱글턴."""
    global _client, _init_error
    if _client is not None or _init_error is not None:
        return _client
    if not settings.supabase_enabled:
        _init_error = "SUPABASE_URL / SUPABASE_KEY 미설정"
        return None
    try:
        # 주의: 이 모듈 이름도 supabase 지만, 파이썬3 절대 임포트라
        #       아래 구문은 site-packages 의 supabase 패키지를 가리킨다.
        from supabase import create_client

        _client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        log.info("Supabase 연결됨: %s", settings.SUPABASE_URL)
    except Exception as e:  # pragma: no cover
        _init_error = f"{type(e).__name__}: {e}"
        log.warning("Supabase 연결 실패 → 로컬 데이터 폴백: %s", _init_error)
    return _client


def available() -> bool:
    return _get_client() is not None


def status() -> Dict[str, Any]:
    return {
        "configured": settings.supabase_enabled,
        "connected": available(),
        "url": settings.SUPABASE_URL or None,
        "bucket": settings.SUPABASE_BUCKET,
        "error": _init_error,
    }


# ---------------------------------------------------------------------------
# 조회
# ---------------------------------------------------------------------------
def fetch_places() -> Optional[List[Dict[str, Any]]]:
    """places 테이블 전체를 읽어온다. 실패 시 None."""
    c = _get_client()
    if c is None:
        return None
    try:
        res = c.table("places").select("*").order("place_id").execute()
        return res.data or None
    except Exception as e:
        log.warning("fetch_places 실패: %s", e)
        return None


def fetch_axes() -> Optional[List[Dict[str, Any]]]:
    c = _get_client()
    if c is None:
        return None
    try:
        res = c.table("preference_axes").select("*").order("sort_order").execute()
        return res.data or None
    except Exception as e:
        log.warning("fetch_axes 실패: %s", e)
        return None


# ---------------------------------------------------------------------------
# Storage — 여행지 이미지
# ---------------------------------------------------------------------------
def image_url(image_path: Optional[str]) -> Optional[str]:
    """place-images 버킷의 public URL 을 만든다."""
    if not image_path:
        return None
    c = _get_client()
    if c is None:
        return None
    try:
        return c.storage.from_(settings.SUPABASE_BUCKET).get_public_url(image_path)
    except Exception as e:
        log.warning("image_url 실패(%s): %s", image_path, e)
        return None


def upload_image(image_path: str, data: bytes, content_type: str = "image/jpeg") -> bool:
    c = _get_client()
    if c is None:
        return False
    try:
        c.storage.from_(settings.SUPABASE_BUCKET).upload(
            path=image_path,
            file=data,
            file_options={"content-type": content_type, "upsert": "true"},
        )
        return True
    except Exception as e:
        log.warning("upload_image 실패(%s): %s", image_path, e)
        return False


# ---------------------------------------------------------------------------
# 쓰기 — 세션 / 추천 로그
# ---------------------------------------------------------------------------
def upsert_session(session_id: str, payload: Dict[str, Any]) -> bool:
    c = _get_client()
    if c is None:
        return False
    try:
        c.table("chat_sessions").upsert({"id": session_id, **payload}).execute()
        return True
    except Exception as e:
        log.debug("upsert_session 실패: %s", e)
        return False


def log_recommendation(
    session_id: str, place_id: str, fit_score: float,
    user_vector: Dict[str, Any], ranking: List[Dict[str, Any]],
) -> bool:
    c = _get_client()
    if c is None:
        return False
    try:
        c.table("recommendations").insert(
            {
                "session_id": session_id,
                "place_id": place_id,
                "fit_score": round(fit_score, 2),
                "user_vector": user_vector,
                "ranking": ranking,
            }
        ).execute()
        return True
    except Exception as e:
        log.debug("log_recommendation 실패: %s", e)
        return False


def seed_places(records: List[Dict[str, Any]]) -> bool:
    c = _get_client()
    if c is None:
        return False
    c.table("places").upsert(records, on_conflict="place_id").execute()
    return True


def seed_axes(records: List[Dict[str, Any]]) -> bool:
    c = _get_client()
    if c is None:
        return False
    c.table("preference_axes").upsert(records, on_conflict="key").execute()
    return True
