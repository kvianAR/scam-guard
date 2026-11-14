"""In-memory pub/sub hub used by the WebSocket live feed.

For a single-node deployment, an in-memory hub is sufficient. To scale to
multiple workers, swap this class for a Redis / MQTT backed implementation.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx

from app.config import get_settings
from app.engine import heuristics
from app.storage import CallStore

log = logging.getLogger("scamguard.hub")


class EventHub:
    def __init__(self, store: CallStore) -> None:
        self._store = store
        self._subscribers: dict[str, set[asyncio.Queue]] = {}

    def subscribe(self, call_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.setdefault(call_id, set()).add(q)
        return q

    def unsubscribe(self, call_id: str, q: asyncio.Queue) -> None:
        subs = self._subscribers.get(call_id)
        if subs:
            subs.discard(q)
            if not subs:
                self._subscribers.pop(call_id, None)

    def publish(self, call_id: str, event: dict[str, Any]) -> None:
        for q in self._subscribers.get(call_id, ()):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                log.warning("Event queue full for call %s — dropping event", call_id)

    # ------------------------------------------------------------------
    async def run_call(
        self,
        call_id: str,
        segments: list[dict[str, Any]],
        analyze_at_end: bool = True,
    ) -> None:
        """Stream segments into the call, then finalize with LLM analysis."""
        s = get_settings()
        delay = s.sim_segment_delay
        call = self._store.get(call_id)
        if call is None:
            return

        for seg in segments:
            await asyncio.sleep(delay)
            call.transcript.append(seg)
            self._store.update(call)
            # Live provisional score so the dashboard can update in real time
            provisional = heuristics.score_transcript(call.plain_transcript)
            self.publish(call_id, {
                "event": "segment",
                "segment": seg,
                "provisional_score": provisional["risk_score"],
                "provisional_level": provisional["risk_level"],
                "ts": call.updated_at.isoformat(),
            })

        if analyze_at_end:
            self.publish(call_id, {"event": "analysis_started"})
            from app.api.calls import finalize_call  # local import to avoid cycles
            await finalize_call(call_id)


class CallRunner:
    """Spawn and track background call tasks."""

    def __init__(self, hub: EventHub, store: CallStore) -> None:
        self._hub = hub
        self._store = store
        self._tasks: dict[str, asyncio.Task] = {}

    def start(self, call_id: str, segments: list[dict[str, Any]]) -> None:
        task = asyncio.create_task(self._hub.run_call(call_id, segments))
        self._tasks[call_id] = task
        task.add_done_callback(lambda _t, cid=call_id: self._tasks.pop(cid, None))

    @property
    def active_call_ids(self) -> list[str]:
        return [cid for cid, t in self._tasks.items() if not t.done()]


# Module-level singletons (lazy, so tests can create their own instances)
_hub: EventHub | None = None
_runner: CallRunner | None = None
_store: CallStore | None = None


def get_hub() -> EventHub:
    global _hub
    if _hub is None:
        _hub = EventHub(get_store())
    return _hub


def get_runner() -> CallRunner:
    global _runner
    if _runner is None:
        _runner = CallRunner(get_hub(), get_store())
    return _runner


def get_store() -> CallStore:
    global _store
    if _store is None:
        _store = CallStore()
    return _store


def reset_globals() -> None:
    """Used by tests to reset singleton state between runs."""
    global _hub, _runner, _store
    if _store is not None:
        _store.close()
    _hub = _runner = _store = None
