import pytest
from fastapi.testclient import TestClient

from trading_bot.config import Settings
from trading_bot.server import create_app

SECRET = "test-secret"


@pytest.fixture
def client(tmp_path):
    settings = Settings(data_dir=tmp_path, webhook_secret=SECRET, symbol_whitelist=["MES"])
    return TestClient(create_app(settings))


def alert(**overrides):
    payload = {
        "symbol": "MES",
        "timeframe": "5",
        "indicator": "SMC",
        "signal": "BOS",
        "direction": "long",
        "price": 5000.0,
    }
    payload.update(overrides)
    return payload


def test_webhook_rejects_bad_secret(client):
    assert client.post("/webhook/wrong", json=alert()).status_code == 403


def test_webhook_stores_signal_and_flags_undefined(client):
    resp = client.post(f"/webhook/{SECRET}", json=alert())
    assert resp.status_code == 200
    assert resp.json() == {"stored": True, "signal_defined": False}
    signals = client.get("/signals").json()
    assert len(signals) == 1
    assert signals[0]["defined"] is False
    assert "observe and log only" in signals[0]["note"]


def test_defaults_to_paused_and_rejects_trades(client):
    client.post(f"/webhook/{SECRET}", json=alert())
    resp = client.post(
        "/trade",
        json={"direction": "long", "symbol": "MES", "size": 1, "stop": 4995.0, "reasoning": "x"},
    )
    assert resp.status_code == 409
    assert "PAUSED" in resp.json()["detail"]


def test_full_trade_lifecycle(client):
    client.post(f"/webhook/{SECRET}", json=alert())
    client.post("/control", json={"state": "ACTIVE", "reason": "test session"})

    resp = client.post(
        "/trade",
        json={
            "direction": "long",
            "symbol": "MES",
            "size": 1,
            "stop": 4995.0,
            "target": 5010.0,
            "reasoning": "5-min bullish CHoCH + FVG retrace + 1-min BOS (rules 2.2).",
        },
    )
    assert resp.status_code == 200, resp.text
    account = client.get("/account").json()
    assert account["open_position"]["entry_price"] == 5000.0

    # target hit via price tick
    client.post(f"/webhook/{SECRET}", json=alert(price=5011.0, signal="tick"))
    account = client.get("/account").json()
    assert account["open_position"] is None
    assert account["balance"] == 50_050.0

    kinds = [r["kind"] for r in client.get("/log").json()]
    assert "entry" in kinds and "exit" in kinds and "control" in kinds


def test_trade_without_stop_is_rejected(client):
    client.post(f"/webhook/{SECRET}", json=alert())
    client.post("/control", json={"state": "ACTIVE", "reason": "test"})
    resp = client.post(
        "/trade",
        json={"direction": "long", "symbol": "MES", "size": 1, "reasoning": "no stop"},
    )
    assert resp.status_code == 422  # stop is a required field


def test_kill_switch_flattens(client):
    client.post(f"/webhook/{SECRET}", json=alert())
    client.post("/control", json={"state": "ACTIVE", "reason": "test"})
    client.post(
        "/trade",
        json={"direction": "long", "symbol": "MES", "size": 1, "stop": 4995.0, "reasoning": "entry"},
    )
    resp = client.post("/control", json={"state": "STOPPED", "reason": "kill switch test"})
    assert resp.json()["flattened"] is not None
    assert client.get("/account").json()["open_position"] is None
    assert client.get("/status").json()["state"] == "STOPPED"


def test_skip_decision_logged(client):
    resp = client.post(
        "/decision",
        json={"reasoning": "Chop, no clear structure — sitting out per rule 2.4.", "symbol": "MES"},
    )
    assert resp.status_code == 200
    log = client.get("/log").json()
    assert log[0]["kind"] == "skip"
