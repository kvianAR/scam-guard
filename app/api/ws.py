"""WebSocket live feed — subscribe to a call's streaming segments.

The hub publishes one event per streamed transcript line plus a final
``analysis_completed`` event. Late subscribers get the current call state
replayed first.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.realtime.hub import get_hub, get_store

router = APIRouter(tags=["realtime"])


@router.websocket("/ws/calls/{call_id}")
async def ws_call_events(call_id: str, ws: WebSocket) -> None:
    await ws.accept()
    hub = get_hub()
    q = hub.subscribe(call_id)

    call = get_store().get(call_id)
    if call is not None:
        await ws.send_json({"event": "call_state", "call": call.summary_dict()})

    client_task = asyncio.create_task(ws.receive_json())
    try:
        while True:
            if q.empty():
                if client_task.done():
                    break
                await asyncio.sleep(0.4)
                continue

            ev = q.get_nowait()
            await ws.send_json(ev)
            if ev.get("event") == "analysis_completed":
                await ws.send_json({"event": "stream_done", "call_id": call_id})
                break
    except WebSocketDisconnect:
        pass
    finally:
        if not client_task.done():
            client_task.cancel()
        hub.unsubscribe(call_id, q)
