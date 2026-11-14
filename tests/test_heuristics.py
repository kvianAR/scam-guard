"""Unit tests for the deterministic heuristic scorer."""
from __future__ import annotations

from app.engine import heuristics


def test_clean_transcript_scores_low():
    result = heuristics.score_transcript("Hello, is this Dr. Patel? Just confirming your appointment.")
    assert result["risk_score"] == 0
    assert result["risk_level"] == "safe"
    assert result["category"] == "legitimate"


def test_otp_scam_scores_critical():
    text = (
        "This is the bank fraud department. Your account is compromised. "
        "I sent an OTP to your phone, read me that one time password now. "
        "Don't tell anyone about this."
    )
    result = heuristics.score_transcript(text)
    assert result["risk_level"] in ("high", "critical")
    assert result["risk_score"] >= 90
    ids = {f["id"] for f in result["red_flags"]}
    assert "password_credential" in ids
    assert "secrecy_demand" in ids


def test_advance_fee_pattern():
    result = heuristics.score_transcript(
        "Congratulations, you have been selected to win a prize. Pay a fee to release your funds."
    )
    assert result["category"] == "advance_fee"
    assert result["risk_score"] >= 80


def test_giftcard_pattern():
    result = heuristics.score_transcript("Pay me with gift cards or a bitcoin wallet, please.")
    ids = {f["id"] for f in result["red_flags"]}
    assert "cash_or_giftcard" in ids


def test_unknown_patterns_stay_low():
    result = heuristics.score_transcript("Hi, how are you? The weather is nice.")
    assert result["risk_score"] == 0


def test_level_mapping():
    from app.engine.rubric import level_for

    assert level_for(0) == "safe"
    assert level_for(20) == "low"
    assert level_for(55) == "medium"
    assert level_for(80) == "high"
    assert level_for(95) == "critical"
