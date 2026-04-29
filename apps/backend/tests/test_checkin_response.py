"""Tests for the per-submit Gemini observation + grounded passage orchestrator."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

import zen_backend.routes.checkin as checkin_route
import zen_backend.services.checkin_response as checkin_response
from zen_backend.main import create_app
from zen_backend.security.checkin_token import issue_checkin_token
from zen_backend.services.checkin_response import (
    _validate_message,
    build_checkin_response_bundle,
)


SECRET = "test-secret-32bytes-or-more-aaaaaaaaa"


# --- Validator unit tests ----------------------------------------------------


def test_validate_message_accepts_calm_two_sentences() -> None:
    text = (
        "The morning is here, and so are you. "
        "Let one steady breath be the first thing you give yourself today."
    )
    assert _validate_message(text) is True


def test_validate_message_rejects_forbidden_phrase() -> None:
    text = "You've got this — trust the journey and crush the day."
    assert _validate_message(text) is False


def test_validate_message_rejects_meta_opener() -> None:
    text = "Based on your answers, today seems heavy. Take it slow."
    assert _validate_message(text) is False


def test_validate_message_rejects_too_short() -> None:
    text = "Be calm."
    assert _validate_message(text) is False


def test_validate_message_rejects_too_long() -> None:
    text = ("word " * 120).strip()
    assert _validate_message(text) is False


# --- Orchestrator integration tests ------------------------------------------


def _stub_passage(monkeypatch: pytest.MonkeyPatch, passage: dict | None) -> None:
    """Stub retrieval to return a known passage (or None)."""
    monkeypatch.setattr(
        checkin_response,
        "fetch_ranked_passages",
        lambda *args, **kwargs: [passage] if passage else [],
    )
    monkeypatch.setattr(
        checkin_response,
        "fetch_candidate_passages",
        lambda *args, **kwargs: [passage] if passage else [],
    )
    monkeypatch.setattr(checkin_response, "get_supabase_client", lambda: object())


def test_bundle_uses_gemini_message_when_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(checkin_response.settings, "enable_checkin_gemini_response", True)
    monkeypatch.setattr(checkin_response.settings, "gemini_api_key", "fake-key")
    valid_text = (
        "The morning is here, and the body is asking for a slower start. "
        "Let one quiet minute mark the line between sleep and the day."
    )
    monkeypatch.setattr(
        checkin_response,
        "_gemini_with_timeout",
        lambda **kwargs: valid_text,
    )
    _stub_passage(
        monkeypatch,
        {
            "id": "p1",
            "tradition": "thoreau",
            "source": "Walden",
            "citation": "ch. 2",
            "text": "I went to the woods because I wished to live deliberately…",
        },
    )

    bundle = build_checkin_response_bundle(
        window="morning",
        on_date=date(2026, 4, 30),
        answers=[{"key": "sleep_quality", "score": 3}],
        mood_score_weighted=55.0,
        challenge_score=2.0,
        note=None,
    )

    assert bundle.message_source == "gemini"
    assert bundle.message == valid_text
    assert bundle.passage is not None
    assert bundle.passage_source == "retrieval"
    assert bundle.passage["source"] == "Walden"


def test_bundle_falls_back_when_gemini_returns_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(checkin_response.settings, "enable_checkin_gemini_response", True)
    monkeypatch.setattr(checkin_response.settings, "gemini_api_key", "fake-key")
    monkeypatch.setattr(
        checkin_response,
        "_gemini_with_timeout",
        lambda **kwargs: "You've got this. Trust the journey.",
    )
    _stub_passage(monkeypatch, None)

    bundle = build_checkin_response_bundle(
        window="evening",
        on_date=date(2026, 4, 30),
        answers=[],
        mood_score_weighted=30.0,
        challenge_score=4.5,
        note=None,
    )

    assert bundle.message_source == "fallback"
    assert "rest" in bundle.message.lower() or "quiet" in bundle.message.lower()
    assert bundle.passage is None
    assert bundle.passage_source == "none"


def test_bundle_falls_back_when_gemini_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(checkin_response.settings, "enable_checkin_gemini_response", True)
    monkeypatch.setattr(checkin_response.settings, "gemini_api_key", "fake-key")
    monkeypatch.setattr(checkin_response, "_gemini_with_timeout", lambda **kwargs: None)
    _stub_passage(monkeypatch, {"id": "p1", "text": "x", "source": "S", "citation": "C"})

    bundle = build_checkin_response_bundle(
        window="midday",
        on_date=date(2026, 4, 30),
        answers=[],
        mood_score_weighted=50.0,
        challenge_score=None,
        note=None,
    )
    assert bundle.message_source == "fallback"


def test_bundle_skips_gemini_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(checkin_response.settings, "enable_checkin_gemini_response", False)
    monkeypatch.setattr(checkin_response.settings, "gemini_api_key", "fake-key")
    called = {"count": 0}

    def spy(**kwargs):  # type: ignore[no-untyped-def]
        called["count"] += 1
        return "anything"

    monkeypatch.setattr(checkin_response, "_gemini_with_timeout", spy)
    _stub_passage(monkeypatch, None)

    bundle = build_checkin_response_bundle(
        window="morning",
        on_date=date(2026, 4, 30),
        answers=[],
        mood_score_weighted=70.0,
        challenge_score=None,
        note=None,
    )
    assert called["count"] == 0
    assert bundle.message_source == "fallback"


def test_bundle_uses_random_gold_when_retrieval_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(checkin_response.settings, "enable_checkin_gemini_response", False)
    monkeypatch.setattr(checkin_response.settings, "gemini_api_key", "")

    def failing_retrieval(*args, **kwargs):
        raise RuntimeError("pgvector unavailable")

    monkeypatch.setattr(checkin_response, "fetch_ranked_passages", failing_retrieval)
    monkeypatch.setattr(
        checkin_response,
        "fetch_candidate_passages",
        lambda *args, **kwargs: [{"id": "p2", "text": "fallback text", "source": "Aurelius", "citation": "IV.18"}],
    )
    monkeypatch.setattr(checkin_response, "get_supabase_client", lambda: object())

    bundle = build_checkin_response_bundle(
        window="evening",
        on_date=date(2026, 4, 30),
        answers=[],
        mood_score_weighted=40.0,
        challenge_score=3.0,
        note=None,
    )
    assert bundle.passage_source == "random_gold"
    assert bundle.passage is not None
    assert bundle.passage["source"] == "Aurelius"


# --- Endpoint integration ----------------------------------------------------


def test_submit_by_token_returns_response_field(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(checkin_route.settings, "checkin_link_secret", SECRET)
    monkeypatch.setattr(checkin_route.settings, "feedback_link_secret", "")
    monkeypatch.setattr(checkin_route, "get_supabase_client", lambda: object())
    monkeypatch.setattr(
        checkin_route,
        "insert_checkin_response",
        lambda client, payload: {"id": "row-1", **payload},
    )

    canned = checkin_response.CheckinResponseBundle(
        message="A quiet thing arrives. Hold it for one breath.",
        message_source="gemini",
        passage={"text": "p", "source": "s", "citation": "c", "tradition": "t"},
        passage_source="retrieval",
    )
    monkeypatch.setattr(
        checkin_route,
        "build_checkin_response_bundle",
        lambda **kwargs: canned,
    )

    token = issue_checkin_token(SECRET, "morning", date(2026, 4, 30))
    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/checkin/submit-by-token",
        json={
            "token": token,
            "channel": "email",
            "answers": [
                {"key": "sleep_quality", "score": 4},
                {"key": "morning_energy", "score": 4},
                {"key": "morning_calm", "score": 3},
                {"key": "body_readiness", "score": 4},
                {"key": "morning_clarity", "score": 5},
                {"key": "motivation", "score": 4},
                {"key": "anticipated_load", "score": 2},
            ],
            "note": None,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "response" in body
    assert body["response"]["message"].startswith("A quiet thing arrives")
    assert body["response"]["message_source"] == "gemini"
    assert body["response"]["passage"]["source"] == "s"
    assert body["response"]["passage_source"] == "retrieval"


def test_submit_by_token_does_not_500_when_orchestrator_blows_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(checkin_route.settings, "checkin_link_secret", SECRET)
    monkeypatch.setattr(checkin_route.settings, "feedback_link_secret", "")
    monkeypatch.setattr(checkin_route, "get_supabase_client", lambda: object())
    monkeypatch.setattr(
        checkin_route,
        "insert_checkin_response",
        lambda client, payload: {"id": "row-1", **payload},
    )

    def explode(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(checkin_route, "build_checkin_response_bundle", explode)

    token = issue_checkin_token(SECRET, "evening", date(2026, 4, 30))
    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/checkin/submit-by-token",
        json={
            "token": token,
            "channel": "email",
            "answers": [
                {"key": "day_satisfaction", "score": 4},
                {"key": "accomplishment", "score": 3},
            ],
            "note": None,
        },
    )
    assert response.status_code == 200
    body = response.json()
    # The response field is omitted when the orchestrator fails — but the
    # core persistence still succeeds.
    assert body["status"] == "ok"
    assert body["window"] == "evening"
    assert "response" not in body
