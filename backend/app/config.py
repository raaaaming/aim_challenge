# -*- coding: utf-8 -*-
"""환경설정 로더."""
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent

load_dotenv(BACKEND_DIR / ".env")


class Settings:
    # ---- Supabase -----------------------------------------------------
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "").strip()
    SUPABASE_KEY: str = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.getenv("SUPABASE_ANON_KEY", "").strip()
    )
    SUPABASE_BUCKET: str = os.getenv("SUPABASE_BUCKET", "place-images").strip()

    # ---- LLM (무료로 쓸 수 있는 제공자만) -------------------------------
    #   gemini     : Google AI Studio 무료 등급 (https://aistudio.google.com/apikey)
    #   groq       : Groq Cloud 무료 등급      (https://console.groq.com/keys)
    #   openrouter : OpenRouter ':free' 모델   (https://openrouter.ai/keys)
    #   rule       : 키 없이 동작하는 내장 규칙 기반 엔진
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
    LLM_API_KEY: str = (
        os.getenv("LLM_API_KEY", "").strip()
        or os.getenv("GEMINI_API_KEY", "").strip()
        or os.getenv("GOOGLE_API_KEY", "").strip()
        or os.getenv("GROQ_API_KEY", "").strip()
        or os.getenv("OPENROUTER_API_KEY", "").strip()
    )
    LLM_MODEL: str = os.getenv("LLM_MODEL", "").strip()
    LLM_TIMEOUT: float = float(os.getenv("LLM_TIMEOUT", "25"))

    # ---- 서버 ----------------------------------------------------------
    CORS_ORIGINS: list = [
        o.strip()
        for o in os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if o.strip()
    ]
    DATA_FILE: Path = PROJECT_ROOT / "data" / "places.json"

    @property
    def supabase_enabled(self) -> bool:
        return bool(self.SUPABASE_URL and self.SUPABASE_KEY)

    @property
    def llm_enabled(self) -> bool:
        return self.LLM_PROVIDER != "rule" and bool(self.LLM_API_KEY)

    @property
    def default_model(self) -> str:
        if self.LLM_MODEL:
            return self.LLM_MODEL
        return {
            "gemini": "gemini-2.0-flash",
            "groq": "llama-3.3-70b-versatile",
            "openrouter": "meta-llama/llama-3.3-70b-instruct:free",
        }.get(self.LLM_PROVIDER, "gemini-2.0-flash")


settings = Settings()
