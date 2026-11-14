"""API integration tests (no external LLM / Fish keys needed)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.realtime import hub as hub_mod


@pytest.fixture()
def client(store):
    app = create_app()
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["llm_configured"] is False
    assert body["fish_configured"] is False


def test_create_webhook_call_and_finalize(client):
    payload = {
        "source_number": "+1-212-555-9999",
        "caller_id_name": "Fake Bank",
        "transcript": [
            {"speaker": "caller", "text": "Your account is compromised. Read me the one time password now."},
            {"speaker": "user", "text": "What password?"},
        ],
    }
    r = client.post("/api/calls", json=payload)
    assert r.status_code == 201
    call_id = r.json()["id"]

    # Webhook finalises in a background task — poll until it settles
    import time

    for _ in range(50):
        c = client.get(f"/api/calls/{call_id}").json()
        if c["risk_score"] is not None:
            break
        time.sleep(0.1)
    else:
        pytest.fail("call never finalized")

    assert c["status"] == "flagged"
    assert c["risk_score"] >= 70
    assert c["engine"] == "heuristic"


def test_list_and_stats(client):
    assert client.get("/api/calls").status_code == 200
    s = client.get("/api/calls/stats").json()
    for k in ("total_calls", "flagged", "avg_risk", "risk_distribution"):
        assert k in s


def test_simulator_run_streams_then_finalizes(client, store):
    r = client.post(
        "/api/simulator/run",
        json={"transcript": [{"speaker": "caller", "text": "Pay a fee to release your funds."}], "source_number": "+99"},
    )
    assert r.status_code == 202
    call_id = r.json()["id"]
    runner = hub_mod.get_runner()

    import time

    deadline = time.time() + 20
    while time.time() < deadline:
        c = store.get(call_id)
        if c.risk_score is not None:
            break
        time.sleep(0.2)
    c = store.get(call_id)
    assert c.risk_score is not None
    assert c.risk_level.value in ("high", "critical")
    assert len(c.transcript) > 0


def test_update_status(client, store):
    call = store.create(source_number="+1-555-1234")
    r = client.patch(f"/api/calls/{call.id}", json={"status": "dismissed"})
    assert r.status_code == 200
    assert r.json()["status"] == "dismissed"


def test_404_on_unknown_call(client):
    assert client.get("/api/calls/nope").status_code == 404


def test_tts_briefing_degrades_gracefully(client, store):
    call = store.create(source_number="+1-555-0000")
    c2 = store.get(call.id)
    c2.risk_score = 80
    c2.risk_level = __import__("app.models", fromlist=["RiskLevel"]).RiskLevel.high
    c2.summary = "Test summary"
    c2.category = "banking_fraud"
    c2.recommended_actions = ["Hang up"]
    store.update(c2)
    r = client.post(f"/api/tts/briefing/{call.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("ready", "skipped")
    if body["status"] == "skipped":
        assert "Fish" in body["reason"]
