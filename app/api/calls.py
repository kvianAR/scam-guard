"""Call management API — create / list / analyze / webhook ingest."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.engine import RiskEngine
from app.models import Call, CallCreate, CallStatus, CallType, CallUpdate, RiskLevel
from app.realtime.hub import get_hub, get_runner, get_store

log = logging.getLogger("scamguard.api")
router = APIRouter(prefix="/api", tags=["calls"])


async def finalize_call(call_id: str) -> Call:
    """Run the full risk engine on a call and persist the result.

    Exposed here (rather than in hub.py) so both the simulator and webhook
    flows share the same finalisation logic.
    """
    store = get_store()
    hub = get_hub()
    call = store.get(call_id)
    if call is None:
        raise HTTPException(404, f"Call {call_id} not found")

    engine = RiskEngine()
    result = engine.analyze(call.plain_transcript)

    call.risk_score = int(result["risk_score"])
    call.risk_level = RiskLevel(result["risk_level"])
    call.engine = result["engine"]
    call.verdict = result.get("verdict")
    call.summary = result.get("summary")
    call.category = result.get("category")
    call.red_flags = result.get("red_flags", [])
    call.confidence = result.get("confidence")
    call.recommended_actions = result.get("recommended_actions", [])
    call.analysis_meta = {
        "category_label": result.get("category_label"),
        "llm_error": result.get("llm_error"),
        "analysis_note": result.get("analysis_note"),
    }
    call.status = CallStatus.flagged if call.risk_level in (RiskLevel.high, RiskLevel.critical) else CallStatus.analyzed
    store.update(call)

    hub.publish(call_id, {
        "event": "analysis_completed",
        "risk_score": call.risk_score,
        "risk_level": call.risk_level.value,
        "category": call.category,
        "verdict": call.verdict,
        "summary": call.summary,
        "red_flags": call.red_flags,
        "confidence": call.confidence,
        "recommended_actions": call.recommended_actions,
        "engine": call.engine,
    })
    return call


# ---------------------------------------------------------------------------
@router.get("/calls", response_model=list[Call])
def list_calls(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status: CallStatus | None = None,
    min_risk: int | None = Query(None, ge=0, le=100),
) -> list[Call]:
    return get_store().list(limit=limit, offset=offset, status=status, min_risk=min_risk)


@router.get("/calls/stats")
def call_stats() -> dict[str, Any]:
    return get_store().stats()


@router.get("/calls/{call_id}", response_model=Call)
def get_call(call_id: str) -> Call:
    call = get_store().get(call_id)
    if call is None:
        raise HTTPException(404, "Call not found")
    return call


@router.post("/calls", response_model=Call, status_code=201)
async def create_call(payload: CallCreate) -> Call:
    """Ingest a call from a webhook (e.g. Twilio transcription webhook)."""
    store = get_store()
    call = store.create(
        source_number=payload.source_number,
        caller_id_name=payload.caller_id_name,
        display_name=payload.display_name,
        transcript=[s.model_dump() for s in payload.transcript],
        call_type=payload.call_type,
    )
    if payload.transcript:
        # Webhook calls arrive with a complete transcript — analyse in background
        import asyncio

        asyncio.create_task(finalize_call(call.id))
    return call


@router.post("/calls/{call_id}/analyze", response_model=Call)
async def analyze_call(call_id: str) -> Call:
    return await finalize_call(call_id)


@router.patch("/calls/{call_id}", response_model=Call)
def update_call(call_id: str, payload: CallUpdate) -> Call:
    store = get_store()
    call = store.get(call_id)
    if call is None:
        raise HTTPException(404, "Call not found")
    if payload.status is not None:
        call.status = payload.status
    if payload.risk_score is not None:
        call.risk_score = payload.risk_score
    if payload.risk_level is not None:
        call.risk_level = payload.risk_level
    if payload.verdict is not None:
        call.verdict = payload.verdict
    if payload.category is not None:
        call.category = payload.category
    if payload.summary is not None:
        call.summary = payload.summary
    return store.update(call)


@router.delete("/calls/{call_id}", status_code=204)
def delete_call(call_id: str) -> None:
    if not get_store().delete(call_id):
        raise HTTPException(404, "Call not found")
