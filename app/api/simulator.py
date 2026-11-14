"""Simulated live-call ingest.

Accepts a full transcript (list of segments) and streams it back over the
WebSocket hub with a configurable per-segment delay so the dashboard's
"live screening" feel is preserved even without a real telephony bridge.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.models import Call
from app.realtime.hub import get_runner, get_store
from app.models import CallType, TranscriptSegment

router = APIRouter(prefix="/api/simulator", tags=["simulator"])


@router.get("/scenarios")
def list_scenarios() -> list[dict[str, Any]]:
    """Return the bundled sample scenarios (benign + scam) for the dashboard."""
    from pathlib import Path
    import json

    root = Path(__file__).resolve().parents[2]
    fixtures = root / "tests" / "fixtures" / "calls"
    out: list[dict[str, Any]] = []
    if fixtures.exists():
        for p in sorted(fixtures.glob("*.json")):
            d = json.loads(p.read_text())
            out.append({
                "id": p.stem,
                "title": d.get("display_name") or d.get("caller_id_name") or p.stem,
                "category": d.get("category"),
                "source_number": d.get("source_number"),
                "caller_id_name": d.get("caller_id_name"),
                "transcript": d.get("transcript", []),
            })
    return out


@router.post("/run", response_model=Call, status_code=202)
def run_scenario(payload: dict[str, Any]) -> Call:
    """Kick off a simulated call. Response carries the call id for WebSocket
    subscription; the runner streams segments in the background.

    Body:
      {
        "scenario_id": "02-bank-otp-scam",   # optional
        "transcript": [{speaker, text}],      # optional (explicit transcript)
        "source_number": "+1-...",            # defaults to scenario's
        "caller_id_name": "..."
      }
    """
    store = get_store()
    runner = get_runner()

    scenario: dict[str, Any] | None = None
    scenario_id = payload.get("scenario_id")
    if scenario_id:
        for sc in list_scenarios():
            if sc["id"] == scenario_id:
                scenario = sc
                break

    transcript = [TranscriptSegment(**s) for s in (payload.get("transcript") or (scenario or {}).get("transcript") or [])]
    segments: list[dict[str, Any]] = [
        {"speaker": t.speaker, "text": t.text, "ts": t.ts} for t in transcript
    ]

    call = store.create(
        source_number=payload.get("source_number") or (scenario or {}).get("source_number", "+1-555-000-0000"),
        caller_id_name=payload.get("caller_id_name") or (scenario or {}).get("caller_id_name"),
        display_name=(scenario or {}).get("display_name"),
        call_type=CallType.simulated,
    )
    runner.start(call.id, segments)
    return call
