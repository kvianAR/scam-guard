"""Tests for the hybrid RiskEngine (no LLM key needed — heuristic path)."""
from __future__ import annotations

from app.engine import RiskEngine
from app.engine.rubric import parse_llm_json


def test_engine_falls_back_to_heuristics_without_llm():
    engine = RiskEngine()
    result = engine.analyze("Your account is compromised, read me that one time password now.")
    assert result["engine"] == "heuristic"
    assert result["risk_level"] in ("high", "critical")
    assert result["red_flags"]
    assert result["recommended_actions"]


def test_parse_llm_json_handles_fenced_output():
    raw = '''Here is my analysis:
    ```json
    {"risk_score": 88, "risk_level": "high", "category": "tax_refund",
     "verdict": "Fake IRS refund scam", "confidence": 0.9,
     "red_flags": [{"id": "tax_refund", "label": "Tax refund", "weight": 85}],
     "recommended_actions": ["Do not pay"], "summary": "Fake IRS."}
    ```'''
    obj = parse_llm_json(raw)
    assert obj["risk_score"] == 88
    assert obj["category"] == "tax_refund"
    assert obj["recommended_actions"] == ["Do not pay"]


def test_parse_llm_json_clamps_and_defaults():
    obj = parse_llm_json('{"risk_score": 150}')
    assert obj["risk_score"] == 100
    assert obj["risk_level"] == "critical"
    assert obj["category"] == "generic_suspicion"
    assert "recommended_actions" in obj


def test_parse_llm_json_rejects_garbage():
    import pytest

    with pytest.raises(ValueError):
        parse_llm_json("I cannot comply.")
