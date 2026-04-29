from __future__ import annotations

from datetime import date, timedelta
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

import zen_backend.routes.checkin as checkin_route
from zen_backend.main import create_app
from zen_backend.security.checkin_token import (
    CheckinTokenError,
    issue_checkin_token,
    verify_checkin_token,
)


SECRET = "test-checkin-secret-32bytes-or-more-aaaaaaaa"


def test_issue_and_verify_round_trip() -> None:
    token = issue_checkin_token(SECRET, "morning", date(2026, 4, 29))
    payload = verify_checkin_token(SECRET, token)
    assert payload["window"] == "morning"
    assert payload["date"] == "2026-04-29"
    assert int(payload["exp"]) > 0


def test_verify_rejects_tampered_signature() -> None:
    token = issue_checkin_token(SECRET, "evening", date(2026, 4, 29))
    head, _, _sig = token.partition(".")
    tampered = f"{head}.{'0' * 64}"
    with pytest.raises(CheckinTokenError):
        verify_checkin_token(SECRET, tampered)


def test_verify_rejects_expired_token() -> None:
    token = issue_checkin_token(SECRET, "morning", date(2026, 4, 29), ttl_seconds=-10)
    with pytest.raises(CheckinTokenError):
        verify_checkin_token(SECRET, token)


def test_by_token_endpoint_returns_questions(monkeypatch) -> None:
    monkeypatch.setattr(checkin_route.settings, "checkin_link_secret", SECRET)
    monkeypatch.setattr(checkin_route.settings, "feedback_link_secret", "")

    token = issue_checkin_token(SECRET, "midday", date(2026, 4, 29))
    app = create_app()
    client = TestClient(app)
    response = client.get(f"/checkin/by-token?token={token}")
    assert response.status_code == 200
    body = response.json()
    assert body["window"] == "midday"
    assert body["date"] == "2026-04-29"
    assert len(body["questions"]) == 8


def test_by_token_endpoint_rejects_invalid(monkeypatch) -> None:
    monkeypatch.setattr(checkin_route.settings, "checkin_link_secret", SECRET)
    monkeypatch.setattr(checkin_route.settings, "feedback_link_secret", "")

    app = create_app()
    client = TestClient(app)
    response = client.get("/checkin/by-token?token=not-a-real-token")
    assert response.status_code == 401


def test_submit_by_token_persists_payload(monkeypatch) -> None:
    monkeypatch.setattr(checkin_route.settings, "checkin_link_secret", SECRET)
    monkeypatch.setattr(checkin_route.settings, "feedback_link_secret", "")
    monkeypatch.setattr(checkin_route, "get_supabase_client", lambda: object())
    captured: dict[str, object] = {}

    def fake_insert(client, payload):
        captured.update(payload)
        return {"id": "checkin-1", **payload}

    monkeypatch.setattr(checkin_route, "insert_checkin_response", fake_insert)

    token = issue_checkin_token(SECRET, "evening", date(2026, 4, 29))
    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/checkin/submit-by-token",
        json={
            "token": token,
            "channel": "email",
            "answers": [
                {"key": "sleep_quality", "score": 4},
                {"key": "stress", "score": 3},
            ],
            "note": "fine",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["window"] == "evening"
    assert body["date"] == "2026-04-29"
    assert captured["window"] == "evening"
    assert captured["channel"] == "email"
    assert captured["checkin_date"] == "2026-04-29"
