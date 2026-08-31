# -*- coding: utf-8 -*-
"""포항항(Pohang-Hang) FastAPI 백엔드."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import chat_engine, describe, llm, recommender, repository as repo
from . import supabase as sb
from .config import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s | %(message)s")
log = logging.getLogger("pohang")

app = FastAPI(title="포항항 API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS or ["*"],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
class ChatIn(BaseModel):
    session_id: str
    message: str = Field(min_length=1, max_length=1000)


# ---------------------------------------------------------------------------
@app.on_event("startup")
def _startup():
    data = repo.load(force=True)
    log.info(
        "데이터 소스=%s | 여행지 %d곳 | 축 %d개 | LLM=%s(%s) | Supabase=%s",
        data["source"], len(data["places"]), len(data["axes"]),
        settings.LLM_PROVIDER, "on" if llm.enabled() else "off(규칙엔진)",
        "on" if sb.available() else "off(로컬 폴백)",
    )


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "data_source": repo.source(),
        "places": len(repo.places()),
        "axes": len(repo.axes()),
        "llm": llm.info(),
        "supabase": sb.status(),
    }


@app.get("/api/axes")
def get_axes():
    return {"axes": repo.axes()}


@app.get("/api/places")
def get_places():
    return {
        "source": repo.source(),
        "places": [
            {
                "place_id": p["place_id"],
                "place_name": p["place_name"],
                "summary": p["summary"],
                "scores": p["scores"],
                "image_url": p.get("image_url"),
            }
            for p in repo.places()
        ],
    }


@app.get("/api/places/{place_id}")
def get_place(place_id: str):
    p = repo.get_place(place_id)
    if not p:
        raise HTTPException(404, "여행지를 찾을 수 없습니다")
    return p


# ---------------------------------------------------------------------------
@app.post("/api/chat/start")
def chat_start():
    s, msgs = chat_engine.start_session()
    return {
        "session_id": s.id,
        "messages": msgs,
        "progress": s.progress(),
        "finished": False,
        "engine": "llm" if llm.enabled() else "rule",
    }


@app.post("/api/chat")
async def chat(body: ChatIn):
    s = chat_engine.get_session(body.session_id)
    if s is None:
        raise HTTPException(404, "세션이 만료되었습니다. 새로고침해 주세요.")
    return await chat_engine.process(s, body.message.strip())


# ---------------------------------------------------------------------------
@app.get("/api/result/{session_id}")
async def result(session_id: str):
    s = chat_engine.get_session(session_id)
    if s is None or not s.result:
        raise HTTPException(404, "아직 추천 결과가 없습니다")
    return await _build_result(s.result, s.slots)


@app.get("/api/result/preview/{place_id}")
async def result_preview(place_id: str):
    """세션 없이 특정 여행지 결과 화면을 보고 싶을 때(공유 링크/디버그)."""
    p = repo.get_place(place_id)
    if not p:
        raise HTTPException(404, "여행지를 찾을 수 없습니다")
    fake = {
        "place": p, "fit_score": 0.0, "matched_axes": [],
        "tradeoff_axes": [], "contributions": [], "ranking": [], "runner_ups": [],
    }
    return await _build_result(fake, {})


async def _build_result(result: Dict[str, Any], slots: Dict[str, Any]):
    place = result["place"]
    desc = await describe.regenerate(place)
    axmap = repo.axis_map()
    return {
        # 최종 결과 화면 — 이름은 CSV 원문 그대로
        "place_id": place["place_id"],
        "place_name": place["place_name"],
        "image_url": place.get("image_url"),
        "image_path": place.get("image_path"),
        "fit_score": result["fit_score"],
        "description": desc,          # summary/embedding_text/evidence 1~5 로만 재생성
        "source_fields": {            # 재생성 근거 원문 (화면에서 펼쳐 볼 수 있게)
            "summary": place["summary"],
            "embedding_text": place["embedding_text"],
            "evidence_texts": place["evidence_texts"],
        },
        "scores": place["scores"],
        "score_reasons": place["score_reasons"],
        "axes": repo.axes(),
        "matched_axes": result["matched_axes"],
        "tradeoff_axes": result["tradeoff_axes"],
        "user_slots": {
            k: {**v, "label": axmap.get(k, {}).get("label", k)}
            for k, v in (slots or {}).items()
        },
        "runner_ups": result["runner_ups"],
    }


@app.get("/")
def root():
    return {"service": "포항항", "docs": "/docs", "health": "/api/health"}
