"""Scam Guard — central configuration loaded from environment / .env file."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_prefix="SCAMGUARD_",
        extra="ignore",
    )

    # LLM (any OpenAI-compatible provider)
    llm_provider: str = "openai"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str | None = None
    llm_temperature: float = 0.1
    llm_timeout: float = 30.0
    llm_max_tokens: int = 800

    # Hybrid heuristic + LLM scoring
    use_heuristics: bool = True
    hard_flag_threshold: int = 70

    # Fish Audio (S2.1 Pro TTS)
    fish_api_key: str = ""
    fish_model: str = "S2.1"
    fish_base_url: str = "https://api.fish.audio"
    fish_reference_id: str = ""
    fish_timeout: float = 90.0

    # Storage / behaviour
    db_path: str = "data/scamguard.db"
    seed_on_start: bool = True
    sim_segment_delay: float = 0.5
    cors_origins: str = "*"

    # ------------------------------------------------------------------
    @property
    def db_path_resolved(self) -> Path:
        p = Path(self.db_path)
        if not p.is_absolute():
            p = ROOT_DIR / p
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key or self.llm_base_url)

    @property
    def fish_configured(self) -> bool:
        return bool(self.fish_api_key)

    @property
    def default_llm_base_url(self) -> str | None:
        """Provider preset when no explicit base URL is given."""
        if self.llm_base_url:
            return self.llm_base_url
        presets = {
            "openai": "https://api.openai.com/v1",
            "groq": "https://api.groq.com/openai/v1",
            "google": "https://generativelanguage.googleapis.com/v1beta/openai",
            "xai": "https://api.x.ai/v1",
            "local": "http://localhost:11434/v1",
        }
        return presets.get(self.llm_provider.lower())


@lru_cache
def get_settings() -> Settings:
    return Settings()
