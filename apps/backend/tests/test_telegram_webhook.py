from __future__ import annotations

from fastapi.testclient import TestClient

from zen_backend.main import app


def test_telegram_webhook_rejects_invalid_secret(monkeypatch) -> None:
    from zen_backend import config as config_module

    monkeypatch.setattr(config_module.settings, "telegram_webhook_secret", "secret123")
    client = TestClient(app)
    response = client.post(
        "/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
        json={"message": {"text": "/start"}},
    )
    assert response.status_code == 401

