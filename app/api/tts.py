"""Voice incident briefings via Fish Audio S2.1 Pro."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from app.models import TTSRequest
from app.voice import fish

router = APIRouter(prefix="/api/tts", tags=["tts"])


@router.post("/briefing/{call_id}")
async def briefing_for_call(call_id: str) -> JSONResponse:
    """Generate a spoken briefing for a stored call."""
    from app.realtime.hub import get_store
    from app.engine.rubric import BRIEFING_TEMPLATE, CATEGORY_LABELS

    call = get_store().get(call_id)
    if call is None:
        raise HTTPException(404, "Call not found")
    if call.risk_score is None:
        raise HTTPException(409, "Call has no analysis yet")

    actions = "\n".join(f"- {a}" for a in call.recommended_actions) or "- No further action"
    text = BRIEFING_TEMPLATE.format(
        category=CATEGORY_LABELS.get(call.category or "generic_suspicion", call.category or "unknown"),
        risk_level=call.risk_level.value,
        summary=call.summary or "No detailed summary available.",
        actions=actions,
    )

    audio_dir = _audio_dir()
    loop = asyncio.get_running_loop()
    path = await loop.run_in_executor(None, fish.synthesize, text, audio_dir)

    if path is None:
        return JSONResponse(
            {
                "status": "skipped",
                "reason": "Fish Audio not configured (set SCAMGUARD_FISH_API_KEY)",
                "text": text,
            }
        )

    # Remember the briefing on the call record
    store = get_store()
    c = store.get(call_id)
    if c is not None:
        c.analysis_meta["briefing_file"] = path.name
        c.voice_briefing_url = f"/api/tts/briefing/{call_id}/audio"
        store.update(c)
        return JSONResponse({"status": "ready", "audio_url": c.voice_briefing_url, "text": text})
    return JSONResponse({"status": "ready", "text": text})


@router.get("/briefing/{call_id}/audio")
def briefing_audio(call_id: str) -> FileResponse:
    store = get_store()
    call = store.get(call_id)
    if call is None or not call.voice_briefing_url:
        raise HTTPException(404, "No briefing generated for this call yet")
    audio_dir = _audio_dir()
    fname = call.analysis_meta.get("briefing_file")
    target = audio_dir / fname if fname else None
    if target is None or not target.exists():
        candidates = sorted(audio_dir.glob("*.wav"))
        if not candidates:
            raise HTTPException(404, "Briefing audio not found on disk")
        target = candidates[-1]
    return FileResponse(target, media_type="audio/wav", filename="briefing.wav")


@router.post("/synthesize")
async def synthesize(payload: TTSRequest) -> JSONResponse:
    """Free-form TTS — useful for testing Fish Audio connectivity."""
    audio_dir = _audio_dir()
    loop = asyncio.get_running_loop()
    path = await loop.run_in_executor(None, fish.synthesize, payload.text, audio_dir)
    if path is None:
        return JSONResponse(
            {"status": "skipped", "reason": "Fish Audio not configured"},
            status_code=202,
        )
    return JSONResponse({"status": "ready", "audio_path": str(path.name)})


def _audio_dir():
    from pathlib import Path

    from app.config import get_settings

    p = get_settings().db_path_resolved.parent / "audio" / "briefings"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_store():
    from app.realtime.hub import get_store as _gs
    return _gs()
