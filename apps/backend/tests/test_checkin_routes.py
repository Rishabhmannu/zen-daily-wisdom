from __future__ import annotations

from fastapi.testclient import TestClient

from zen_backend.main import create_app
import zen_backend.routes.checkin as checkin_route


def test_checkin_questions_returns_all_windows_when_unspecified() -> None:
    app = create_app()
    client = TestClient(app)
    response = client.get("/checkin/questions")
    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == 2
    assert set(body["windows"].keys()) == {"morning", "midday", "evening"}
    assert len(body["windows"]["morning"]) == 7
    assert len(body["windows"]["midday"]) == 6
    assert len(body["windows"]["evening"]) == 7


def test_checkin_questions_returns_specific_window() -> None:
    app = create_app()
    client = TestClient(app)
    response = client.get("/checkin/questions?window=evening")
    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == 2
    assert body["window"] == "evening"
    assert len(body["questions"]) == 7
    keys = {q["key"] for q in body["questions"]}
    assert "day_satisfaction" in keys
    assert "tomorrow_clarity" in keys


def test_checkin_submit_persists_payload(monkeypatch) -> None:
    captured: dict = {}

    def fake_insert(client, payload):
        captured.update(payload)
        return {"id": "checkin-1", **payload}

    monkeypatch.setattr(checkin_route, "get_supabase_client", lambda: object())
    monkeypatch.setattr(checkin_route, "insert_checkin_response", fake_insert)

    app = create_app()
    client = TestClient(app)
    # All 4s on morning's 7 items except the reverse-coded `anticipated_load`
    # at 2. By construction (see test_mood_score.py) this yields a uniform
    # goodness of 0.75 across every item, so mood_score_weighted == 75.0.
    response = client.post(
        "/checkin/submit",
        json={
            "window": "morning",
            "channel": "dashboard",
            "answers": [
                {"key": "sleep_quality", "score": 4},
                {"key": "morning_energy", "score": 4},
                {"key": "morning_calm", "score": 4},
                {"key": "motivation", "score": 4},
                {"key": "morning_clarity", "score": 4},
                {"key": "body_readiness", "score": 4},
                {"key": "anticipated_load", "score": 2},
            ],
            "note": "Focus feels better today",
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["window"] == "morning"
    assert data["channel"] == "dashboard"
    assert data["schema_version"] == 2
    assert data["mood_score_method"] == "weighted_v1"
    assert abs(float(data["mood_score_weighted"]) - 75.0) < 0.05
    assert abs(float(data["mood_score_equal"]) - 75.0) < 0.05
    # Legacy mood_score = raw mean = (6*4 + 2)/7 ~= 3.714
    assert abs(float(data["mood_score"]) - 26 / 7) < 0.05
    # Challenge: only `anticipated_load` is reverse-coded -> raw 2.0
    assert float(data["challenge_score"]) == 2.0
    # Same payload should have been written through to the DB layer.
    assert captured["mood_score_method"] == "weighted_v1"
    assert "mood_score_weighted" in captured
    assert "mood_score_equal" in captured
