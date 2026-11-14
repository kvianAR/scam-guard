"""Shared pytest fixtures — isolated DB + LLM-off settings for tests."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Force tests to run without any external API keys
os.environ["SCAMGUARD_LLM_API_KEY"] = ""
os.environ["SCAMGUARD_LLM_BASE_URL"] = ""
os.environ["SCAMGUARD_SEED_ON_START"] = "0"
os.environ["SCAMGUARD_SIM_SEGMENT_DELAY"] = "0.01"


@pytest.fixture(autouse=True)
def reset_engine_globals(tmp_path: Path):
    """Point settings at a temp DB so tests never touch the real data file."""
    os.environ["SCAMGUARD_DB_PATH"] = str(tmp_path / "test.db")

    from app.config import get_settings

    get_settings.cache_clear()
    from app.realtime import hub

    hub.reset_globals()
    yield
    hub.reset_globals()


@pytest.fixture()
def store():
    from app.realtime.hub import get_store

    return get_store()
