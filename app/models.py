"""Pydantic models shared across API, engine and storage."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RiskLevel(str, Enum):
    safe = "safe"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"
    unknown = "unknown"


class EngineType(str, Enum):
    heuristic = "heuristic"
    llm = "llm"
    hybrid = "hybrid"


class CallStatus(str, Enum):
    screening = "screening"   # transcript streaming in
    analyzed = "analyzed"      # final analysis done
    flagged = "flagged"       # analyzed with high/critical risk
    dismissed = "dismissed"   # user marked as false positive
    confirmed_scam = "confirmed_scam"  # user confirmed it was a scam


class CallType(str, Enum):
    simulated = "simulated"
    webhook = "webhook"
    manual = "manual"


class Call(BaseModel):
    id: str
    source_number: str
    display_name: str | None = None
    caller_id_name: str | None = None   # name shown on the caller ID
    started_at: datetime
    transcript: list[dict[str, Any]] = Field(default_factory=list)
    status: CallStatus = CallStatus.screening
    risk_score: int | None = None
    risk_level: RiskLevel = RiskLevel.unknown
    engine: EngineType | None = None
    verdict: str | None = None
    summary: str | None = None
    category: str | None = None
    red_flags: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float | None = None
    recommended_actions: list[str] = Field(default_factory=list)
    voice_briefing_url: str | None = None
    analysis_meta: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    call_type: CallType = CallType.simulated

    @property
    def plain_transcript(self) -> str:
        return "\n".join(
            f"{seg.get('speaker', '?')}: {seg.get('text', '')}" for seg in self.transcript
        )

    def summary_dict(self) -> dict[str, Any]:
        return self.model_dump()


class CallCreate(BaseModel):
    source_number: str
    display_name: str | None = None
    caller_id_name: str | None = None
    transcript: list[dict[str, Any]] = Field(default_factory=list)
    call_type: CallType = CallType.webhook


class CallUpdate(BaseModel):
    status: CallStatus | None = None
    risk_score: int | None = None
    risk_level: RiskLevel | None = None
    verdict: str | None = None
    category: str | None = None
    summary: str | None = None


class TranscriptSegment(BaseModel):
    speaker: str
    text: str
    ts: float | None = None


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class RiskEvent(BaseModel):
    event: str
    ts: datetime


class AnalysisEvent(BaseModel):
    call_id: str
    stage: str
    progress: str | None = None
    risk_score: int | None = None
    risk_level: RiskLevel | None = None


class IncidentStats(BaseModel):
    total_calls: int
    flagged: int
    confirmed_scam: int
    dismissed: int
    avg_risk: float
    last_call_at: datetime | None
    risk_distribution: dict[str, int]
    category_distribution: dict[str, int]
