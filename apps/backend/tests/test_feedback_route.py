from fastapi.testclient import TestClient

import zen_backend.routes.feedback as feedback_route
from zen_backend.main import create_app
from zen_backend.security.hmac_sig import sign_text


SECRET = "test-feedback-secret-32bytes-or-more-aaaaaaaa"


def test_feedback_rejects_invalid_signature(monkeypatch) -> None:
    monkeypatch.setattr(feedback_route.settings, "feedback_link_secret", "test-secret")
    app = create_app()
    client = TestClient(app)
    response = client.get(
        "/feedback",
        params={"sent_id": "abc", "rating": 4, "channel": "email", "sig": "bad"},
    )
    assert response.status_code == 401


def test_feedback_redirects_to_frontend_thanks_page(monkeypatch) -> None:
    """Regression: clicking a rating in the email used to redirect to the
    backend's `/feedback/thanks` (which doesn't exist) and surface a
    `{"detail":"Not Found"}` JSON 404. The redirect target must point at
    the frontend host (Vercel), where the actual Next.js thanks page lives.
    """
    monkeypatch.setattr(feedback_route.settings, "feedback_link_secret", SECRET)
    monkeypatch.setattr(
        feedback_route.settings,
        "frontend_base_url",
        "https://example-frontend.vercel.app",
    )
    monkeypatch.setattr(
        feedback_route.settings,
        "public_base_url",
        "https://example-backend.code.run",
    )

    monkeypatch.setattr(feedback_route, "get_supabase_client", lambda: object())
    monkeypatch.setattr(
        feedback_route,
        "get_sent_history_by_id",
        lambda client, sent_id: {"id": sent_id, "sent_date": "2026-04-30"},
    )
    captured: dict = {}
    monkeypatch.setattr(
        feedback_route,
        "insert_feedback",
        lambda client, payload: captured.update(payload) or {"id": "f1", **payload},
    )

    sent_id = "uuid-123"
    rating = 4
    channel = "email"
    sig = sign_text(SECRET, f"{sent_id}|{rating}|{channel}")

    app = create_app()
    client = TestClient(app)
    response = client.get(
        "/feedback",
        params={"sent_id": sent_id, "rating": rating, "channel": channel, "sig": sig},
        follow_redirects=False,
    )

    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("https://example-frontend.vercel.app/feedback/thanks")
    assert "example-backend.code.run" not in location
    assert f"sent_id={sent_id}" in location
    assert f"rating={rating}" in location

    # Feedback row was still persisted before the redirect.
    assert captured["sent_id"] == sent_id
    assert captured["rating"] == rating
