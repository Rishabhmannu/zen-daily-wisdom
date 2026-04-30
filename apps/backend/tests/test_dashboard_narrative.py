"""Tests for the dashboard weekly narrative orchestrator + routes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import zen_backend.routes.dashboard as dashboard_route
import zen_backend.services.dashboard_narrative as narrative_module
from zen_backend.main import create_app
from zen_backend.security.jwt_verify import verify_owner_user
from zen_backend.services.dashboard_narrative import (
    NarrativePayload,
    _summarize_rows,
    _validate,
    get_or_generate_weekly_narrative,
)


def _now_iso(offset_days: int = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=offset_days)).isoformat()


def _today_str() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _yday_str() -> str:
    return (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()


def _make_authed_client():
    app = create_app()
    app.dependency_overrides[verify_owner_user] = lambda: {
        "id": "owner",
        "email": "owner@example.com",
    }
    return app, TestClient(app)


# --- Validator ---------------------------------------------------------------


def test_validate_accepts_calm_three_sentences() -> None:
    text = (
        "There is a steadiness in the recent days that's worth holding loosely. "
        "Mornings have carried more of the weight than evenings, and the body is asking for a "
        "smaller pace. Notice the warmth of one quiet moment before the next thing arrives."
    )
    assert _validate(text) is True


def test_validate_rejects_clichés() -> None:
    text = (
        "This week has been wild. You've got this — trust the journey and keep grinding. "
        "Things will get better as you embrace the process and level up daily."
    )
    assert _validate(text) is False


def test_validate_rejects_meta_opener() -> None:
    text = "Based on your data, mornings are heavier than evenings. " * 3
    assert _validate(text) is False


def test_validate_rejects_too_short() -> None:
    assert _validate("Be calm. The days will pass.") is False


# --- Summarizer --------------------------------------------------------------


def test_summarize_rows_buckets_by_window_and_trend() -> None:
    rows = [
        {
            "checkin_date": _today_str(),
            "window": "morning",
            "mood_score_weighted": 80.0,
            "challenge_score": 2.0,
            "submitted_at": _now_iso(0),
            "note": "feeling settled",
        },
        {
            "checkin_date": _today_str(),
            "window": "evening",
            "mood_score_weighted": 60.0,
            "challenge_score": 3.0,
            "submitted_at": _now_iso(0),
            "note": None,
        },
        {
            "checkin_date": _yday_str(),
            "window": "morning",
            "mood_score_weighted": 50.0,
            "challenge_score": 4.0,
            "submitted_at": _now_iso(1),
            "note": None,
        },
        {
            "checkin_date": _yday_str(),
            "window": "morning",
            "mood_score_weighted": 55.0,
            "challenge_score": 4.0,
            "submitted_at": _now_iso(1),
            "note": None,
        },
    ]
    summary = _summarize_rows(rows)

    assert summary["submissions_total"] == 4
    assert summary["days_with_submission"] == 2
    assert summary["most_completed_window"] == "morning"
    # avg mood = (80 + 60 + 50 + 55) / 4 = 61.25
    assert abs(summary["avg_mood_0_100"] - 61.25) < 0.05
    assert abs(summary["avg_challenge"] - 3.25) < 0.05
    assert summary["recent_note"] == "feeling settled"
    assert summary["trend_summary"] in {
        "drifted upward in the second half",
        "softened in the second half",
        "held steady throughout",
    }


# --- Cache freshness --------------------------------------------------------


def test_returns_cached_row_when_fresh(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(narrative_module.settings, "dashboard_narrative_ttl_minutes", 360)
    fake_row = {
        "id": "weekly",
        "body": "A steady run of mornings with a softer afternoon load. Notice one quiet thing.",
        "source_method": "gemini",
        "generated_at": (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat(),
    }
    monkeypatch.setattr(narrative_module, "get_dashboard_narrative", lambda c, k: fake_row)
    called = {"generate": 0}

    def fake_generate(client):
        called["generate"] += 1
        return NarrativePayload(
            body="should not be used",
            source_method="gemini",
            generated_at=datetime.now(timezone.utc),
            age_minutes=0.0,
            is_fresh=True,
        )

    monkeypatch.setattr(narrative_module, "_generate_and_persist", fake_generate)

    payload = get_or_generate_weekly_narrative(object(), force_refresh=False)
    assert payload.body.startswith("A steady run")
    assert payload.is_fresh is True
    assert called["generate"] == 0


def test_regenerates_when_cache_is_stale(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(narrative_module.settings, "dashboard_narrative_ttl_minutes", 60)
    stale_row = {
        "id": "weekly",
        "body": "stale body",
        "source_method": "gemini",
        "generated_at": (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat(),
    }
    monkeypatch.setattr(narrative_module, "get_dashboard_narrative", lambda c, k: stale_row)

    fresh_payload = NarrativePayload(
        body="fresh body, written just now",
        source_method="gemini",
        generated_at=datetime.now(timezone.utc),
        age_minutes=0.0,
        is_fresh=True,
    )
    monkeypatch.setattr(
        narrative_module,
        "_generate_and_persist",
        lambda client: fresh_payload,
    )

    payload = get_or_generate_weekly_narrative(object(), force_refresh=False)
    assert payload.body == "fresh body, written just now"


def test_force_refresh_skips_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(narrative_module.settings, "dashboard_narrative_ttl_minutes", 360)
    fresh_row = {
        "id": "weekly",
        "body": "cached body",
        "source_method": "gemini",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    monkeypatch.setattr(narrative_module, "get_dashboard_narrative", lambda c, k: fresh_row)

    fresh_payload = NarrativePayload(
        body="forced regeneration body",
        source_method="gemini",
        generated_at=datetime.now(timezone.utc),
        age_minutes=0.0,
        is_fresh=True,
    )
    monkeypatch.setattr(
        narrative_module,
        "_generate_and_persist",
        lambda client: fresh_payload,
    )

    payload = get_or_generate_weekly_narrative(object(), force_refresh=True)
    assert payload.body == "forced regeneration body"


def test_falls_back_to_static_when_gemini_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(narrative_module.settings, "enable_dashboard_narrative", False)
    monkeypatch.setattr(narrative_module.settings, "gemini_api_key", "fake")
    monkeypatch.setattr(narrative_module, "get_dashboard_narrative", lambda c, k: None)
    monkeypatch.setattr(
        narrative_module,
        "get_recent_checkin_responses",
        lambda c, limit=120: [],
    )

    captured = {}

    def fake_upsert(client, **kwargs):
        captured.update(kwargs)
        return {
            "id": kwargs["kind"],
            "body": kwargs["body"],
            "source_method": kwargs["source_method"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    monkeypatch.setattr(narrative_module, "upsert_dashboard_narrative", fake_upsert)

    payload = get_or_generate_weekly_narrative(object(), force_refresh=True)
    assert payload.source_method == "fallback"
    assert captured["source_method"] == "fallback"
    assert "Nothing has been recorded yet" in payload.body


# --- Endpoint integration ----------------------------------------------------


def test_get_narrative_endpoint_returns_serialized_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canned = NarrativePayload(
        body="There is a steady rhythm to your mornings.",
        source_method="gemini",
        generated_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        age_minutes=10.0,
        is_fresh=True,
    )
    monkeypatch.setattr(dashboard_route, "get_supabase_client", lambda: object())
    monkeypatch.setattr(
        dashboard_route,
        "get_or_generate_weekly_narrative",
        lambda client, force_refresh=False: canned,
    )

    _, client = _make_authed_client()
    response = client.get("/dashboard/narrative")
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["body"] == "There is a steady rhythm to your mornings."
    assert body["source_method"] == "gemini"
    assert body["is_fresh"] is True


def test_refresh_endpoint_forces_regeneration(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_force: list[bool] = []

    def fake_get_or_generate(client, force_refresh=False):
        seen_force.append(force_refresh)
        return NarrativePayload(
            body="A regenerated body",
            source_method="gemini",
            generated_at=datetime.now(timezone.utc),
            age_minutes=0.0,
            is_fresh=True,
        )

    monkeypatch.setattr(dashboard_route, "get_supabase_client", lambda: object())
    monkeypatch.setattr(dashboard_route, "get_or_generate_weekly_narrative", fake_get_or_generate)

    _, client = _make_authed_client()
    response = client.post("/dashboard/narrative/refresh")
    assert response.status_code == 200
    assert seen_force == [True]
    assert response.json()["data"]["body"] == "A regenerated body"
