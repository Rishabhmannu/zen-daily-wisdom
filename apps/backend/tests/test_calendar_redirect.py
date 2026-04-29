from __future__ import annotations

from fastapi.testclient import TestClient

import zen_backend.routes.calendar as calendar_route
from zen_backend.main import create_app
from zen_backend.security.calendar_link import (
    sign_calendar_link,
    verify_calendar_link,
)


SECRET = "calendar-redirect-test-secret-32bytes-or-more-aaaaaa"


def test_sign_and_verify_round_trip() -> None:
    sig = sign_calendar_link(SECRET, "abc-123")
    assert sig and len(sig) >= 32
    assert verify_calendar_link(SECRET, "abc-123", sig) is True


def test_verify_rejects_wrong_sent_id() -> None:
    sig = sign_calendar_link(SECRET, "abc-123")
    assert verify_calendar_link(SECRET, "different-id", sig) is False


def test_verify_rejects_wrong_signature() -> None:
    assert verify_calendar_link(SECRET, "abc-123", "deadbeef") is False


def test_verify_rejects_empty_inputs() -> None:
    assert verify_calendar_link("", "abc-123", "anysig") is False
    assert verify_calendar_link(SECRET, "abc-123", "") is False


def test_calendar_redirect_happy_path(monkeypatch) -> None:
    monkeypatch.setattr(calendar_route.settings, "feedback_link_secret", SECRET)
    monkeypatch.setattr(calendar_route, "get_supabase_client", lambda: object())

    def fake_get(client, sent_id):
        assert sent_id == "uuid-123"
        return {
            "id": "uuid-123",
            "sent_date": "2026-04-29",
            "theme_of_day": "Patience",
            "llm_output": "Pause for one steady breath before the day pulls you in every direction.",
        }

    monkeypatch.setattr(calendar_route, "get_sent_history_by_id", fake_get)

    sig = sign_calendar_link(SECRET, "uuid-123")
    app = create_app()
    client = TestClient(app)
    response = client.get(f"/calendar/add?sent_id=uuid-123&sig={sig}", follow_redirects=False)

    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("https://calendar.google.com/calendar/render?action=TEMPLATE")
    # The theme should be url-encoded into the redirect target.
    assert "Patience" in location.replace("%20", " ").replace("%2520", " ")


def test_calendar_redirect_rejects_bad_signature(monkeypatch) -> None:
    monkeypatch.setattr(calendar_route.settings, "feedback_link_secret", SECRET)
    monkeypatch.setattr(calendar_route, "get_supabase_client", lambda: object())
    monkeypatch.setattr(
        calendar_route,
        "get_sent_history_by_id",
        lambda client, sent_id: {"id": sent_id, "sent_date": "2026-04-29", "theme_of_day": "x"},
    )

    app = create_app()
    client = TestClient(app)
    response = client.get(
        "/calendar/add?sent_id=uuid-123&sig=00000000000000000000000000000000",
        follow_redirects=False,
    )
    assert response.status_code == 401


def test_calendar_redirect_404_when_sent_id_missing(monkeypatch) -> None:
    monkeypatch.setattr(calendar_route.settings, "feedback_link_secret", SECRET)
    monkeypatch.setattr(calendar_route, "get_supabase_client", lambda: object())
    monkeypatch.setattr(calendar_route, "get_sent_history_by_id", lambda client, sent_id: None)

    sig = sign_calendar_link(SECRET, "uuid-missing")
    app = create_app()
    client = TestClient(app)
    response = client.get(
        f"/calendar/add?sent_id=uuid-missing&sig={sig}", follow_redirects=False
    )
    assert response.status_code == 404


def test_calendar_redirect_500_when_secret_missing(monkeypatch) -> None:
    monkeypatch.setattr(calendar_route.settings, "feedback_link_secret", "")

    app = create_app()
    client = TestClient(app)
    sig = "anything"
    response = client.get(
        f"/calendar/add?sent_id=uuid-123&sig={sig}", follow_redirects=False
    )
    assert response.status_code == 500
