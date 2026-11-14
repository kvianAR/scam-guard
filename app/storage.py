"""SQLite persistence layer (synchronous — safe for this deployment size)."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from app.config import get_settings
from app.models import Call, CallStatus, CallType, RiskLevel

SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    id TEXT PRIMARY KEY,
    source_number TEXT NOT NULL,
    display_name TEXT,
    caller_id_name TEXT,
    started_at TEXT NOT NULL,
    transcript TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'screening',
    risk_score INTEGER,
    risk_level TEXT NOT NULL DEFAULT 'unknown',
    engine TEXT,
    verdict TEXT,
    summary TEXT,
    category TEXT,
    red_flags TEXT NOT NULL DEFAULT '[]',
    confidence REAL,
    recommended_actions TEXT NOT NULL DEFAULT '[]',
    voice_briefing_url TEXT,
    analysis_meta TEXT NOT NULL DEFAULT '{}',
    call_type TEXT NOT NULL DEFAULT 'simulated',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_calls_status ON calls(status);
CREATE INDEX IF NOT EXISTS idx_calls_risk ON calls(risk_score);
"""


class CallStore:
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or str(get_settings().db_path_resolved)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    # ------------------------------------------------------------------
    def _row_to_call(self, row: sqlite3.Row) -> Call:
        def dt(v: str | None) -> datetime:
            if not v:
                return datetime.now(timezone.utc)
            try:
                return datetime.fromisoformat(v)
            except ValueError:
                return datetime.now(timezone.utc)

        return Call(
            id=row["id"],
            source_number=row["source_number"],
            display_name=row["display_name"],
            caller_id_name=row["caller_id_name"],
            started_at=dt(row["started_at"]),
            transcript=json.loads(row["transcript"] or "[]"),
            status=CallStatus(row["status"]),
            risk_score=row["risk_score"],
            risk_level=RiskLevel(row["risk_level"]),
            engine=row["engine"],
            verdict=row["verdict"],
            summary=row["summary"],
            category=row["category"],
            red_flags=json.loads(row["red_flags"] or "[]"),
            confidence=row["confidence"],
            recommended_actions=json.loads(row["recommended_actions"] or "[]"),
            voice_briefing_url=row["voice_briefing_url"],
            analysis_meta=json.loads(row["analysis_meta"] or "{}"),
            call_type=CallType(row["call_type"] or "simulated"),
            created_at=dt(row["created_at"]),
            updated_at=dt(row["updated_at"]),
        )

    def create(
        self,
        *,
        source_number: str = "+000-0000-0000",
        caller_id_name: str | None = None,
        display_name: str | None = None,
        transcript: list[dict[str, Any]] | None = None,
        call_type: CallType = CallType.simulated,
    ) -> Call:
        c = Call(
            id=uuid.uuid4().hex,
            source_number=source_number,
            display_name=display_name,
            caller_id_name=caller_id_name,
            started_at=datetime.now(timezone.utc),
            transcript=list(transscript or []),
            status=CallStatus.screening,
            call_type=call_type,
        )
        self._upsert(c)
        return self.get(c.id)  # type: ignore[return-value]

    def _upsert(self, c: Call) -> None:
        c.updated_at = datetime.now(timezone.utc)
        self._conn.execute(
            """INSERT INTO calls (id, source_number, display_name, caller_id_name, started_at,
               transcript, status, risk_score, risk_level, engine, verdict, summary, category,
               red_flags, confidence, recommended_actions, voice_briefing_url, analysis_meta,
               call_type, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 source_number=excluded.source_number, display_name=excluded.display_name,
                 caller_id_name=excluded.caller_id_name, transcript=excluded.transcript,
                 status=excluded.status, risk_score=excluded.risk_score,
                 risk_level=excluded.risk_level, engine=excluded.engine,
                 verdict=excluded.verdict, summary=excluded.summary,
                 category=excluded.category, red_flags=excluded.red_flags,
                 confidence=excluded.confidence,
                 recommended_actions=excluded.recommended_actions,
                 voice_briefing_url=excluded.voice_briefing_url,
                 analysis_meta=excluded.analysis_meta, call_type=excluded.call_type,
                 updated_at=excluded.updated_at""",
            (
                c.id, c.source_number, c.display_name, c.caller_id_name,
                c.started_at.isoformat(), json.dumps(c.transcript), c.status.value,
                c.risk_score, c.risk_level.value, c.engine, c.verdict, c.summary,
                c.category, json.dumps(c.red_flags), c.confidence,
                json.dumps(c.recommended_actions), c.voice_briefing_url,
                json.dumps(c.analysis_meta), c.call_type.value,
                c.created_at.isoformat(), c.updated_at.isoformat(),
            ),
        )
        self._conn.commit()

    def upsert(self, c: Call) -> Call:
        """Insert or overwrite a fully-specified Call (used by seeder/tests)."""
        self._upsert(c)
        return self.get(c.id)  # type: ignore[return-value]

    def update(self, call: Call) -> Call:
        self._upsert(call)
        return self.get(call.id)  # type: ignore[return-value]

    def get(self, call_id: str) -> Call | None:
        row = self._conn.execute("SELECT * FROM calls WHERE id = ?", (call_id,)).fetchone()
        return self._row_to_call(row) if row else None

    def list(
        self,
        limit: int = 100,
        offset: int = 0,
        status: CallStatus | None = None,
        min_risk: int | None = None,
    ) -> list[Call]:
        q = "SELECT * FROM calls"
        args: list[Any] = []
        conds = []
        if status:
            conds.append("status = ?")
            args.append(status.value)
        if min_risk is not None:
            conds.append("risk_score >= ?")
            args.append(min_risk)
        if conds:
            q += " WHERE " + " AND ".join(conds)
        q += " ORDER BY started_at DESC LIMIT ? OFFSET ?"
        args += [limit, offset]
        rows = self._conn.execute(q, args).fetchall()
        return [self._row_to_call(r) for r in rows]

    def stats(self) -> dict[str, Any]:
        total = self._conn.execute("SELECT COUNT(*) c FROM calls").fetchone()["c"]
        flagged = self._conn.execute(
            "SELECT COUNT(*) c FROM calls WHERE status IN ('flagged','confirmed_scam')"
        ).fetchone()["c"]
        confirmed = self._conn.execute(
            "SELECT COUNT(*) c FROM calls WHERE status = 'confirmed_scam'"
        ).fetchone()["c"]
        dismissed = self._conn.execute(
            "SELECT COUNT(*) c FROM calls WHERE status = 'dismissed'"
        ).fetchone()["c"]
        avg = self._conn.execute(
            "SELECT AVG(risk_score) a FROM calls WHERE risk_score IS NOT NULL"
        ).fetchone()["a"]
        last = self._conn.execute(
            "SELECT MAX(started_at) m FROM calls"
        ).fetchone()["m"]
        dist_rows = self._conn.execute(
            "SELECT risk_level, COUNT(*) c FROM calls GROUP BY risk_level"
        ).fetchall()
        cat_rows = self._conn.execute(
            "SELECT category, COUNT(*) c FROM calls WHERE category IS NOT NULL GROUP BY category"
        ).fetchall()
        return {
            "total_calls": total,
            "flagged": flagged,
            "confirmed_scam": confirmed,
            "dismissed": dismissed,
            "avg_risk": round(float(avg), 1) if avg is not None else 0.0,
            "last_call_at": datetime.fromisoformat(last).isoformat() if last else None,
            "risk_distribution": {r["risk_level"]: r["c"] for r in dist_rows},
            "category_distribution": {r["category"]: r["c"] for r in cat_rows},
        }

    def delete(self, call_id: str) -> bool:
        cur = self._conn.execute("DELETE FROM calls WHERE id = ?", (call_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def close(self) -> None:
        self._conn.close()
