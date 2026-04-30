"""Tests for the GET /dashboard/checkins payload after the PR-C addition
of `daily_series` and the 0-100 mood scale."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import zen_backend.routes.dashboard as dashboard_route
from zen_backend.main import create_app
from zen_backend.security.jwt_verify import verify_owner_user


def _make_authed_client() -> tuple[FastAPI, TestClient]:
    """Build an app with the owner-auth dependency stubbed out so tests can
    exercise the route logic without a live Supabase Auth call."""
    app = create_app()
    app.dependency_overrides[verify_owner_user] = lambda: {
        "id": "owner",
        "email": "owner@example.com",
    }
    return app, TestClient(app)


def _patch_rows(monkeypatch: pytest.MonkeyPatch, rows: list[dict[str, Any]]) -> None:
    monkeypatch.setattr(dashboard_route, "get_supabase_client", lambda: object())
    monkeypatch.setattr(
        dashboard_route,
        "get_recent_checkin_responses",
        lambda client, limit=60: rows,
    )


def _today() -> str:
    return datetime.utcnow().date().isoformat()


def _yesterday() -> str:
    return (datetime.utcnow().date() - timedelta(days=1)).isoformat()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def test_checkins_returns_daily_series_with_14_points(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_rows(
        monkeypatch,
        [
            {
                "id": "r1",
                "checkin_date": _today(),
                "window": "morning",
                "channel": "email",
                "mood_score": 4.0,
                "mood_score_weighted": 75.0,
                "challenge_score": 2.0,
                "submitted_at": _now_iso(),
            },
            {
                "id": "r2",
                "checkin_date": _today(),
                "window": "evening",
                "channel": "email",
                "mood_score": 4.5,
                "mood_score_weighted": 65.0,
                "challenge_score": 3.0,
                "submitted_at": _now_iso(),
            },
            {
                "id": "r3",
                "checkin_date": _yesterday(),
                "window": "morning",
                "channel": "email",
                "mood_score": 3.0,
                "mood_score_weighted": 50.0,
                "challenge_score": 4.0,
                "submitted_at": _now_iso(),
            },
        ],
    )

    _, client = _make_authed_client()
    response = client.get("/dashboard/checkins?days=14")
    assert response.status_code == 200
    body = response.json()

    series = body["stats"]["daily_series"]
    assert isinstance(series, list)
    assert len(series) == 14

    # Series is rendered oldest -> newest, so today is the last point.
    today_point = series[-1]
    assert today_point["date"] == _today()
    assert today_point["submissions"] == 2
    # Mood for today is the mean of (75, 65) = 70.0
    assert abs(today_point["mood"] - 70.0) < 0.05
    assert today_point["windows"] == ["evening", "morning"]

    yesterday_point = series[-2]
    assert yesterday_point["date"] == _yesterday()
    assert yesterday_point["submissions"] == 1
    assert abs(yesterday_point["mood"] - 50.0) < 0.05

    # All other days should be gaps.
    older_days = series[:-2]
    assert all(p["mood"] is None and p["submissions"] == 0 for p in older_days)


def test_checkins_avg_mood_uses_0_100_scale(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_rows(
        monkeypatch,
        [
            {
                "checkin_date": _today(),
                "window": "morning",
                "mood_score": 4.0,  # legacy 1-5
                "mood_score_weighted": 80.0,  # 0-100
                "challenge_score": 2.0,
                "submitted_at": _now_iso(),
            },
            {
                "checkin_date": _today(),
                "window": "evening",
                "mood_score": 3.0,
                "mood_score_weighted": 60.0,
                "challenge_score": 3.5,
                "submitted_at": _now_iso(),
            },
        ],
    )

    _, client = _make_authed_client()
    response = client.get("/dashboard/checkins?days=14")
    assert response.status_code == 200
    stats = response.json()["stats"]

    assert "avg_mood_0_100" in stats
    assert abs(stats["avg_mood_0_100"] - 70.0) < 0.05
    assert "avg_mood_legacy_1to5" in stats
    assert abs(stats["avg_mood_legacy_1to5"] - 3.5) < 0.05


def test_checkins_falls_back_to_legacy_mood_when_weighted_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A pre-migration row only has mood_score (1-5). It should rescale to
    0-100 cleanly when computing avg_mood_0_100."""
    _patch_rows(
        monkeypatch,
        [
            {
                "checkin_date": _today(),
                "window": "evening",
                "mood_score": 5.0,
                "mood_score_weighted": None,
                "challenge_score": 1.0,
                "submitted_at": _now_iso(),
            },
        ],
    )

    _, client = _make_authed_client()
    response = client.get("/dashboard/checkins?days=14")
    stats = response.json()["stats"]
    # 5.0 on the legacy 1-5 scale => 100.0 on the 0-100 scale.
    assert abs(stats["avg_mood_0_100"] - 100.0) < 0.05
    today_point = stats["daily_series"][-1]
    assert abs(today_point["mood"] - 100.0) < 0.05


def test_checkins_empty_returns_safe_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_rows(monkeypatch, [])

    _, client = _make_authed_client()
    response = client.get("/dashboard/checkins?days=14")
    assert response.status_code == 200
    stats = response.json()["stats"]
    assert stats["completion_rate"] == 0.0
    assert stats["avg_mood_0_100"] is None
    assert stats["avg_challenge"] is None
    assert len(stats["daily_series"]) == 14
    assert all(p["mood"] is None for p in stats["daily_series"])
