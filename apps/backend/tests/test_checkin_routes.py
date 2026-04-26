from __future__ import annotations

from fastapi.testclient import TestClient

from zen_backend.main import create_app
import zen_backend.routes.checkin as checkin_route


def test_checkin_questions_returns_schema() -> None:
    app = create_app()
    client = TestClient(app)
    response = client.get("/checkin/questions")
    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == 1
    assert len(body["questions"]) >= 6


def test_checkin_submit_persists_payload(monkeypatch) -> None:
    monkeypatch.setattr(checkin_route, "get_supabase_client", lambda: object())
    monkeypatch.setattr(
        checkin_route,
        "insert_checkin_response",
        lambda client, payload: {"id": "checkin-1", **payload},
    )

    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/checkin/submit",
        json={
            "window": "morning",
            "channel": "dashboard",
            "answers": [
                {"key": "sleep_quality", "score": 4},
                {"key": "stress", "score": 2},
                {"key": "motivation", "score": 5},
            ],
            "note": "Focus feels better today",
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["window"] == "morning"
    assert data["channel"] == "dashboard"
    assert round(float(data["mood_score"]), 3) == round((4 + 2 + 5) / 3, 3)
    assert float(data["challenge_score"]) == 2.0
