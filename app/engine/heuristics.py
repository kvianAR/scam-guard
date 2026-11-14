"""Deterministic, zero-dependency pre-screen.

Runs before (and after) the LLM so the product works with no API key, and so
the final score is never downgraded below the heuristic floor.
"""
from __future__ import annotations

import re
from typing import Any

from app.engine.rubric import ALL_PATTERNS, level_for, CATEGORY_LABELS


def score_transcript(transcript_text: str) -> dict[str, Any]:
    """Return a rubric-style result dict from pure regex matching."""
    text_lower = transcript_text.lower()
    found: list[dict[str, Any]] = []
    scores_by_category: dict[str, int] = {}

    for p in ALL_PATTERNS:
        rx = re.compile(p["regex"], re.IGNORECASE | re.DOTALL)
        if rx.search(text_lower):
            found.append(
                {
                    "id": p["id"],
                    "label": p["label"],
                    "weight": int(p["weight"]),
                    "category": p.get("category", "generic_suspicion"),
                    "why": p.get("why"),
                }
            )
            cat = p.get("category", "generic_suspicion")
            scores_by_category[cat] = scores_by_category.get(cat, 0) + int(p["weight"])

    # Top category drives the label
    top_cat = max(scores_by_category.items(), key=lambda kv: kv[1])[0] if scores_by_category else "legitimate"

    if found:
        score = min(100, sum(f["weight"] for f in found))
    else:
        score = 0

    result = {
        "risk_score": score,
        "risk_level": level_for(score),
        "category": top_cat if found else "legitimate",
        "verdict": "Multiple scam indicators detected." if found else "No clear scam indicators detected.",
        "confidence": min(0.95, 0.5 + 0.08 * len(found)) if found else 0.5,
        "red_flags": found,
        "recommended_actions": _default_actions(score, top_cat),
        "summary": _default_summary(found, top_cat, score),
    }
    result["category_label"] = CATEGORY_LABELS.get(result["category"], result["category"])
    return result


def _default_actions(score: int, category: str) -> list[str]:
    actions: list[str] = [
        "Stay calm and keep your side of the conversation neutral",
        "Do NOT share OTP, PIN, CVV, passwords, or ID documents",
    ]
    if score >= 70:
        actions.insert(0, "End the call and re-dial the organisation on its published official number")
        actions.append("Report the incident in the dashboard so your team can review it")
    if category == "banking_fraud":
        actions.append("Call your bank on the number printed on your card, not one the caller gives you")
    if category == "advance_fee" or category == "tax_refund":
        actions.append("Never pay an upfront fee to 'release' a refund, prize, or compensation")
    return actions


def _default_summary(found: list[dict[str, Any]], category: str, score: int) -> str:
    if not found:
        return "Caller's requests matched no known scam patterns in this analysis window."
    names = ", ".join(f["label"] for f in found[:4])
    return (
        f"Heuristics flagged {len(found)} indicator(s) — {names}. "
        f"Likely {CATEGORY_LABELS.get(category, category)} (score {score}/100)."
    )
