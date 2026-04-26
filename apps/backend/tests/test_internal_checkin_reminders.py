import hashlib
import hmac
import json

from fastapi.testclient import TestClient

import zen_backend.routes.internal as internal_route
from zen_backend.main import create_app


def _signature(secret: str, payload: dict) -> str:
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def test_checkin_reminder_requires_signature(monkeypatch) -> None:
    monkeypatch.setattr(internal_route.settings, "internal_hmac_secret", "abc123")
    app = create_app()
    client = TestClient(app)
    response = client.post("/internal/checkin-reminders", json={"window": "morning"})
    assert response.status_code == 401


def test_checkin_reminder_accepts_signature(monkeypatch) -> None:
    monkeypatch.setattr(internal_route.settings, "internal_hmac_secret", "abc123")
    monkeypatch.setattr(internal_route.settings, "telegram_bot_token", "")
    monkeypatch.setattr(internal_route.settings, "telegram_chat_id", "")
    monkeypatch.setattr(internal_route.settings, "gmail_client_id", "")
    monkeypatch.setattr(internal_route.settings, "gmail_client_secret", "")
    monkeypatch.setattr(internal_route.settings, "gmail_refresh_token", "")
    monkeypatch.setattr(internal_route.settings, "gmail_from_address", "")

    app = create_app()
    client = TestClient(app)
    payload = {"window": "midday"}
    sig = _signature("abc123", payload)
    response = client.post(
        "/internal/checkin-reminders",
        json=payload,
        headers={"X-Internal-Signature": sig},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "sent"
    assert body["delivery"]["window"] == "midday"
