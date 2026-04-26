from fastapi.testclient import TestClient

import zen_backend.routes.feedback as feedback_route
from zen_backend.main import create_app


def test_feedback_rejects_invalid_signature(monkeypatch) -> None:
    monkeypatch.setattr(feedback_route.settings, "feedback_link_secret", "test-secret")
    app = create_app()
    client = TestClient(app)
    response = client.get("/feedback", params={"sent_id": "abc", "rating": 4, "channel": "email", "sig": "bad"})
    assert response.status_code == 401

