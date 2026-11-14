"""RiskEngine — the main entry point that combines heuristics and LLM."""
from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings
from app.engine import heuristics, llm, rubric

log = logging.getLogger("scamguard.risk")


class RiskEngine:
    """Analyse a transcript.

    - When SCAMGUARD_LLM_API_KEY is set, runs the LLM for deep analysis.
    - Heuristics always run (as a pre-screen + floor).
    - The final result is a hybrid: LLM result is preferred, but the score is
      never downgraded below the heuristic floor (conservative flagging).
    """

    def analyze(self, transcript_text: str) -> dict[str, Any]:
        s = get_settings()

        # Heuristics always run when enabled — they double as the LLM fallback
        heur = heuristics.score_transcript(transcript_text) if s.use_heuristics else {}
        base: dict[str, Any] = dict(heur)

        llm_used = False
        llm_error: str | None = None
        if s.llm_configured:
            try:
                result = llm.analyze_with_llm(transcript_text)
                llm_used = True
                base = result
            except llm.LLMError as e:
                log.warning("LLM analysis failed, falling back to heuristics: %s", e)
                llm_error = str(e)
                base = dict(heur)

        # Apply conservative floor: LLM can't lower the score below heuristics
        if s.use_heuristics and llm_used:
            floor = heur["risk_score"]
            if floor >= s.hard_flag_threshold and base["risk_score"] < floor:
                base["risk_score"] = floor
                base["risk_level"] = rubric.level_for(floor)
                base["analysis_note"] = (
                    "Heuristic floor applied: LLM score was lower than the "
                    "deterministic red-flag ceiling."
                )

        base["engine"] = "hybrid" if (s.use_heuristics and llm_used) else ("llm" if llm_used else "heuristic")
        base["llm_error"] = llm_error
        # Merge LLM red flags with heuristic red flags (deduplicate by id)
        base["red_flags"] = _merge_flags(heur.get("red_flags", []), base.get("red_flags", []))
        return base


def _merge_flags(
    heur_flags: list[dict[str, Any]], llm_flags: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Union of heuristic + LLM red flags, deduplicated by id, weighted by max."""
    by_id: dict[str, dict[str, Any]] = {}
    for f in heur_flags + llm_flags:
        fid = f.get("id", f.get("label", "?"))
        existing = by_id.get(fid)
        if not existing or int(f.get("weight", 0)) > int(existing.get("weight", 0)):
            by_id[fid] = f
    return sorted(by_id.values(), key=lambda f: int(f.get("weight", 0)), reverse=True)
