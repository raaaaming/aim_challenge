# -*- coding: utf-8 -*-
"""
무료로 사용 가능한 LLM 제공자 어댑터.

  gemini     — Google AI Studio 무료 등급 (gemini-2.0-flash). 키 발급 무료.
  groq       — Groq Cloud 무료 등급 (llama-3.3-70b-versatile).
  openrouter — OpenRouter 의 ':free' 접미사 모델 (과금 없음).
  rule       — 키가 아예 없을 때 쓰는 내장 규칙 엔진 (chat_engine 이 처리).

모두 OpenAI 호환 or REST 라 httpx 만으로 호출한다.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

import httpx

from .config import settings

log = logging.getLogger("pohang.llm")


class LLMUnavailable(RuntimeError):
    pass


def enabled() -> bool:
    return settings.llm_enabled


def info() -> Dict[str, Any]:
    return {
        "provider": settings.LLM_PROVIDER,
        "model": settings.default_model,
        "enabled": settings.llm_enabled,
        "free_tier": True,
        "note": "키가 없으면 내장 규칙 기반 엔진으로 자동 전환됩니다.",
    }


# ---------------------------------------------------------------------------
def _extract_json(text: str) -> Optional[dict]:
    text = (text or "").strip()
    if not text:
        return None
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    # 본문 안에 섞인 첫 JSON 오브젝트를 긁어낸다
    depth, start = 0, -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    return json.loads(text[start : i + 1])
                except Exception:
                    start = -1
    return None


# ---------------------------------------------------------------------------
async def _call_gemini(system: str, messages: List[Dict[str, str]], json_mode: bool,
                       temperature: float) -> str:
    model = settings.default_model
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    )
    contents = [
        {"role": "model" if m["role"] == "assistant" else "user",
         "parts": [{"text": m["content"]}]}
        for m in messages
    ]
    body: Dict[str, Any] = {
        "contents": contents,
        "systemInstruction": {"parts": [{"text": system}]},
        "generationConfig": {"temperature": temperature, "maxOutputTokens": 1400},
    }
    if json_mode:
        body["generationConfig"]["responseMimeType"] = "application/json"

    async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as cli:
        r = await cli.post(url, params={"key": settings.LLM_API_KEY}, json=body)
        if r.status_code >= 400:
            raise LLMUnavailable(f"gemini {r.status_code}: {r.text[:300]}")
        data = r.json()
    try:
        parts = data["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts)
    except Exception as e:
        raise LLMUnavailable(f"gemini 응답 파싱 실패: {e}") from e


async def _call_openai_compatible(base: str, system: str, messages: List[Dict[str, str]],
                                  json_mode: bool, temperature: float) -> str:
    body: Dict[str, Any] = {
        "model": settings.default_model,
        "messages": [{"role": "system", "content": system}] + messages,
        "temperature": temperature,
        "max_tokens": 1400,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}

    headers = {"Authorization": f"Bearer {settings.LLM_API_KEY}"}
    if "openrouter" in base:
        headers["HTTP-Referer"] = "http://localhost:5173"
        headers["X-Title"] = "Pohang-Hang"

    async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as cli:
        r = await cli.post(base, headers=headers, json=body)
        if r.status_code >= 400:
            raise LLMUnavailable(f"{base} {r.status_code}: {r.text[:300]}")
        data = r.json()
    try:
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        raise LLMUnavailable(f"응답 파싱 실패: {e}") from e


async def complete(system: str, messages: List[Dict[str, str]], *,
                   json_mode: bool = False, temperature: float = 0.7) -> str:
    if not settings.llm_enabled:
        raise LLMUnavailable("LLM 키가 설정되지 않았습니다")
    p = settings.LLM_PROVIDER
    if p == "gemini":
        return await _call_gemini(system, messages, json_mode, temperature)
    if p == "groq":
        return await _call_openai_compatible(
            "https://api.groq.com/openai/v1/chat/completions",
            system, messages, json_mode, temperature)
    if p == "openrouter":
        return await _call_openai_compatible(
            "https://openrouter.ai/api/v1/chat/completions",
            system, messages, json_mode, temperature)
    raise LLMUnavailable(f"알 수 없는 provider: {p}")


async def complete_json(system: str, messages: List[Dict[str, str]],
                        temperature: float = 0.4) -> dict:
    raw = await complete(system, messages, json_mode=True, temperature=temperature)
    obj = _extract_json(raw)
    if obj is None:
        raise LLMUnavailable(f"JSON 파싱 실패: {raw[:200]}")
    return obj
