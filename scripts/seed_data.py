"""Seed the database with realistic sample calls (benign + scam variants).

Run from the project root:
    python -m scripts.seed_data
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import get_settings
from app.models import Call, CallStatus, CallType, RiskLevel
from app.storage import CallStore

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def load_scenarios() -> list[dict]:
    out: list[dict] = []
    calls_dir = FIXTURES / "calls"
    if calls_dir.exists():
        for p in sorted(calls_dir.glob("*.json")):
            out.append(json.loads(p.read_text()))
    return out


def _parse_level(v: str | None) -> RiskLevel:
    try:
        return RiskLevel(v) if v else RiskLevel.unknown
    except ValueError:
        return RiskLevel.unknown


def seed() -> int:
    settings = get_settings()
    store = CallStore()
    scenarios = load_scenarios()
    now = datetime.now(timezone.utc)
    count = 0

    for i, sc in enumerate(scenarios):
        started = now - timedelta(minutes=sc.get("base_minutes_ago", i * 45))
        call = Call(
            id=f"seed-{i:03d}",
            source_number=sc.get("source_number", "+000-000-0000"),
            display_name=sc.get("display_name"),
            caller_id_name=sc.get("caller_id_name"),
            started_at=started,
            transcript=sc.get("transcript", []),
            status=_parse_level_status(sc.get("status", "analyzed")),
            risk_score=sc.get("risk_score"),
            risk_level=_parse_level(sc.get("risk_level")),
            engine=sc.get("engine", "heuristic"),
            verdict=sc.get("verdict"),
            summary=sc.get("summary"),
            category=sc.get("category"),
            red_flags=sc.get("red_flags", []),
            confidence=sc.get("confidence"),
            recommended_actions=sc.get("recommended_actions", []),
            call_type=CallType.simulated,
            created_at=started,
            updated_at=now,
        )
        store.upsert(call)
        count += 1

    print(f"Seeded {count} calls into {settings.db_path_resolved}")
    store.close()
    return count


def _parse_level_status(v: str) -> CallStatus:
    try:
        return CallStatus(v)
    except ValueError:
        return CallStatus.analyzed


if __name__ == "__main__":
    seed()
