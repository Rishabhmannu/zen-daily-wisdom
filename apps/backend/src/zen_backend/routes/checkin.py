"""Check-in API.

Three time-of-day windows (morning, midday, evening) with their own question
sets, weights, and reverse-coded items. Mood Score is bounded 0-100 with a
goodness-normalization step (positive items: (s-1)/4; reverse items:
1-(s-1)/4) before applying the per-item weights. Both the weighted and the
equal-weight scores are persisted for ablation.

See `IMPLEMENTATION_PLAN.md` §12.5 for the full design rationale and citations.
"""

from __future__ import annotations

from datetime import date as date_type
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from zen_backend.config import settings
from zen_backend.db.client import get_supabase_client
from zen_backend.db.queries import insert_checkin_response
from zen_backend.security.checkin_token import (
    CheckinTokenError,
    verify_checkin_token,
)
from zen_backend.services.checkin_response import (
    CheckinResponseBundle,
    build_checkin_response_bundle,
)

router = APIRouter(prefix="/checkin", tags=["checkin"])

Window = Literal["morning", "midday", "evening"]
SCHEMA_VERSION = 2
SCORE_METHOD = "weighted_v1"


# --- Question sets per window -----------------------------------------------

_QUESTIONS_BY_WINDOW: dict[str, list[dict[str, object]]] = {
    "morning": [
        {"key": "sleep_quality", "label": "How would you rate last night's sleep?", "scale": [1, 5]},
        {"key": "morning_energy", "label": "How is your energy waking up?", "scale": [1, 5]},
        {"key": "morning_calm", "label": "How calm do you feel starting the day?", "scale": [1, 5]},
        {"key": "body_readiness", "label": "How easy does your body feel to move right now?", "scale": [1, 5]},
        {"key": "morning_clarity", "label": "How clear is your top priority for today?", "scale": [1, 5]},
        {"key": "motivation", "label": "How motivated are you to begin?", "scale": [1, 5]},
        {"key": "anticipated_load", "label": "How heavy does today look?", "scale": [1, 5]},
    ],
    "midday": [
        {"key": "current_focus", "label": "How focused do you feel right now?", "scale": [1, 5]},
        {"key": "current_energy", "label": "How is your energy at this point in the day?", "scale": [1, 5]},
        {"key": "current_calm", "label": "How calm do you feel right now?", "scale": [1, 5]},
        {"key": "progress_so_far", "label": "How much progress on today's priority?", "scale": [1, 5]},
        {"key": "current_pressure", "label": "How pressured does this hour feel?", "scale": [1, 5]},
        {"key": "social_drain", "label": "How socially depleted do you feel right now?", "scale": [1, 5]},
    ],
    "evening": [
        {"key": "day_satisfaction", "label": "How satisfied are you with how today went?", "scale": [1, 5]},
        {"key": "accomplishment", "label": "How fully did you do what mattered most today?", "scale": [1, 5]},
        {"key": "gratitude_moment", "label": "How present were you in the best moment of today?", "scale": [1, 5]},
        {"key": "evening_calm", "label": "How calm do you feel right now?", "scale": [1, 5]},
        {"key": "tomorrow_clarity", "label": "How clear is tomorrow's top priority?", "scale": [1, 5]},
        {"key": "body_tiredness", "label": "How tired/drained does your body feel?", "scale": [1, 5]},
        {"key": "evening_overwhelm", "label": "How overwhelmed do you feel about tomorrow?", "scale": [1, 5]},
    ],
}


# --- Weights per window (each set sums to 1.0) ------------------------------

_WEIGHTS_BY_WINDOW: dict[str, dict[str, float]] = {
    "morning": {
        "sleep_quality": 0.18,
        "morning_energy": 0.16,
        "morning_calm": 0.16,
        "motivation": 0.14,
        "morning_clarity": 0.14,
        "anticipated_load": 0.12,
        "body_readiness": 0.10,
    },
    "midday": {
        "current_focus": 0.20,
        "current_energy": 0.18,
        "current_calm": 0.18,
        "progress_so_far": 0.16,
        "current_pressure": 0.14,
        "social_drain": 0.14,
    },
    "evening": {
        "day_satisfaction": 0.22,
        "accomplishment": 0.16,
        "evening_calm": 0.14,
        "gratitude_moment": 0.12,
        "tomorrow_clarity": 0.12,
        "body_tiredness": 0.12,
        "evening_overwhelm": 0.12,
    },
}


# --- Reverse-coded items (5 = bad / high challenge) -------------------------

_REVERSE_KEYS_BY_WINDOW: dict[str, set[str]] = {
    "morning": {"anticipated_load"},
    "midday": {"current_pressure", "social_drain"},
    "evening": {"body_tiredness", "evening_overwhelm"},
}

# Legacy reverse keys from the v1 question set; included for back-compat
# scoring of historic answers without a window match.
_LEGACY_REVERSE_KEYS = {"day_load", "stress", "anxiety", "overwhelm", "pressure"}


def _validate_weights() -> None:
    """Sanity-check at import time so we don't silently ship a misweighted set."""
    for window, weights in _WEIGHTS_BY_WINDOW.items():
        total = sum(weights.values())
        if abs(total - 1.0) > 1e-6:
            raise RuntimeError(f"Weights for window '{window}' sum to {total}, expected 1.0")


_validate_weights()


# --- Pydantic models --------------------------------------------------------


class CheckinAnswer(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    score: int = Field(ge=1, le=5)


class CheckinSubmitRequest(BaseModel):
    window: Window
    channel: Literal["email", "telegram", "dashboard"] = "dashboard"
    answers: list[CheckinAnswer] = Field(min_length=1, max_length=12)
    note: str | None = Field(default=None, max_length=800)
    submitted_at: datetime | None = None


class CheckinSubmitByTokenRequest(BaseModel):
    token: str = Field(min_length=8, max_length=2048)
    answers: list[CheckinAnswer] = Field(min_length=1, max_length=12)
    note: str | None = Field(default=None, max_length=800)
    channel: Literal["email", "telegram", "dashboard"] = "email"


# --- Scoring ----------------------------------------------------------------


def compute_scores(window: str, answers: list[CheckinAnswer]) -> dict[str, float | None | str]:
    """Compute every score variant we persist.

    Returns:
        Dict with keys:
        - mood_score_legacy: raw mean of 1-5 (back-compat semantics)
        - mood_score_weighted: 0-100, window-weighted goodness sum
        - mood_score_equal: 0-100, equal-weighted goodness sum
        - challenge_score: mean of reverse-coded items on raw 1-5 scale, or None
        - score_method: tag identifying the algorithm version
    """
    weights = _WEIGHTS_BY_WINDOW.get(window, {})
    reverse_keys = _REVERSE_KEYS_BY_WINDOW.get(window, set()) | _LEGACY_REVERSE_KEYS

    n = len(answers)
    if n == 0:
        return {
            "mood_score_legacy": None,
            "mood_score_weighted": None,
            "mood_score_equal": None,
            "challenge_score": None,
            "score_method": SCORE_METHOD,
        }

    weighted_sum = 0.0
    equal_sum = 0.0
    legacy_sum = 0.0
    challenge_scores: list[int] = []

    for ans in answers:
        normalized = (ans.score - 1) / 4.0  # 0..1
        is_reverse = ans.key in reverse_keys
        goodness = 1.0 - normalized if is_reverse else normalized

        # Fallback to equal weight for any answer key missing from the
        # window's weight table (covers historic / unknown keys).
        weight = weights.get(ans.key, 1.0 / n)
        weighted_sum += weight * goodness
        equal_sum += goodness / n
        legacy_sum += ans.score / n

        if is_reverse:
            challenge_scores.append(ans.score)

    return {
        "mood_score_legacy": round(legacy_sum, 3),
        "mood_score_weighted": round(weighted_sum * 100, 2),
        "mood_score_equal": round(equal_sum * 100, 2),
        "challenge_score": round(sum(challenge_scores) / len(challenge_scores), 3) if challenge_scores else None,
        "score_method": SCORE_METHOD,
    }


def _persist_checkin(
    *,
    on_date: date_type,
    window: str,
    channel: str,
    answers: list[CheckinAnswer],
    note: str | None,
    submitted_at: datetime,
) -> dict:
    client = get_supabase_client()
    scores = compute_scores(window, answers)

    payload = {
        "checkin_date": on_date.isoformat(),
        "window": window,
        "channel": channel,
        "answers": [answer.model_dump() for answer in answers],
        "mood_score": scores["mood_score_legacy"],
        "mood_score_weighted": scores["mood_score_weighted"],
        "mood_score_equal": scores["mood_score_equal"],
        "mood_score_method": scores["score_method"],
        "challenge_score": scores["challenge_score"],
        "note": note,
        "submitted_at": submitted_at.isoformat(),
        "schema_version": SCHEMA_VERSION,
    }
    row = insert_checkin_response(client, payload)
    # Surface the computed scores back to the caller so the frontend can show
    # "Today's mood: NN / 100" without an extra round-trip.
    return {
        "row": row,
        "scores": {
            "mood_score_weighted": scores["mood_score_weighted"],
            "mood_score_equal": scores["mood_score_equal"],
            "challenge_score": scores["challenge_score"],
        },
    }


# --- Routes -----------------------------------------------------------------


@router.get("/questions")
def questions(window: Window | None = Query(default=None)) -> dict:
    """Return the question set for a window.

    If `window` is omitted, returns the full set of windows so a caller can
    cache them all at once. The `schema_version` is bumped to 2 to signal the
    new windowed layout to any client that previously cached v1.
    """
    if window is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "windows": _QUESTIONS_BY_WINDOW,
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "window": window,
        "questions": _QUESTIONS_BY_WINDOW[window],
    }


@router.get("/by-token")
def checkin_by_token(token: str = Query(..., min_length=8, max_length=2048)) -> dict:
    """Validate a signed token and return the question set + window/date.

    No auth — the signed token IS the auth (same model as feedback links).
    """
    secret = settings.effective_checkin_link_secret
    if not secret:
        raise HTTPException(status_code=500, detail="Check-in link secret is not configured.")
    try:
        payload = verify_checkin_token(secret, token)
    except CheckinTokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    window = str(payload["window"])
    return {
        "status": "ok",
        "window": window,
        "date": payload["date"],
        "questions": _QUESTIONS_BY_WINDOW.get(window, []),
        "schema_version": SCHEMA_VERSION,
    }


def _build_response_bundle_safely(
    *,
    window: str,
    on_date: date_type,
    answers: list[CheckinAnswer],
    mood_score_weighted: float | None,
    challenge_score: float | None,
    note: str | None,
) -> CheckinResponseBundle | None:
    """Wrap the orchestrator so the endpoint never 500s on a Gemini /
    retrieval blow-up — persistence already succeeded by this point."""
    try:
        return build_checkin_response_bundle(
            window=window,
            on_date=on_date,
            answers=[answer.model_dump() for answer in answers],
            mood_score_weighted=mood_score_weighted,
            challenge_score=challenge_score,
            note=note,
        )
    except Exception:  # noqa: BLE001
        return None


@router.post("/submit-by-token")
def submit_checkin_by_token(payload: CheckinSubmitByTokenRequest) -> dict:
    secret = settings.effective_checkin_link_secret
    if not secret:
        raise HTTPException(status_code=500, detail="Check-in link secret is not configured.")
    try:
        token_payload = verify_checkin_token(secret, payload.token)
    except CheckinTokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    try:
        on_date = date_type.fromisoformat(str(token_payload["date"]))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Token date is invalid.") from exc

    window = str(token_payload["window"])
    submitted_at = datetime.now(timezone.utc)
    result = _persist_checkin(
        on_date=on_date,
        window=window,
        channel=payload.channel,
        answers=payload.answers,
        note=payload.note,
        submitted_at=submitted_at,
    )

    bundle = _build_response_bundle_safely(
        window=window,
        on_date=on_date,
        answers=payload.answers,
        mood_score_weighted=(
            float(result["scores"]["mood_score_weighted"])
            if result["scores"].get("mood_score_weighted") is not None
            else None
        ),
        challenge_score=(
            float(result["scores"]["challenge_score"])
            if result["scores"].get("challenge_score") is not None
            else None
        ),
        note=payload.note,
    )

    response: dict[str, object] = {
        "status": "ok",
        "data": result["row"],
        "scores": result["scores"],
        "window": window,
        "date": token_payload["date"],
    }
    if bundle is not None:
        response["response"] = {
            "message": bundle.message,
            "message_source": bundle.message_source,
            "passage": bundle.passage,
            "passage_source": bundle.passage_source,
        }
    return response


@router.post("/submit")
def submit_checkin(payload: CheckinSubmitRequest) -> dict:
    """Legacy submit (still used by any direct dashboard form)."""
    submitted_at = payload.submitted_at or datetime.now(timezone.utc)
    result = _persist_checkin(
        on_date=submitted_at.date(),
        window=payload.window,
        channel=payload.channel,
        answers=payload.answers,
        note=payload.note,
        submitted_at=submitted_at,
    )
    return {"status": "ok", "data": result["row"], "scores": result["scores"]}
