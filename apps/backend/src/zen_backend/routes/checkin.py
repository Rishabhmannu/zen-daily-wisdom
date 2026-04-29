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

router = APIRouter(prefix="/checkin", tags=["checkin"])

_CHALLENGE_KEYS = {"day_load", "stress", "anxiety", "overwhelm", "pressure"}

_QUESTIONS: list[dict[str, object]] = [
    {"key": "sleep_quality", "label": "How was your sleep quality?", "scale": [1, 5]},
    {"key": "energy", "label": "How is your energy right now?", "scale": [1, 5]},
    {"key": "focus", "label": "How focused do you feel?", "scale": [1, 5]},
    {"key": "stress", "label": "How stressed do you feel?", "scale": [1, 5]},
    {"key": "day_load", "label": "How heavy does today feel?", "scale": [1, 5]},
    {"key": "motivation", "label": "How motivated do you feel?", "scale": [1, 5]},
    {"key": "positivity", "label": "How positive is your mindset?", "scale": [1, 5]},
    {"key": "clarity", "label": "How clear is your next step?", "scale": [1, 5]},
]


class CheckinAnswer(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    score: int = Field(ge=1, le=5)


class CheckinSubmitRequest(BaseModel):
    window: Literal["morning", "midday", "evening"]
    channel: Literal["email", "telegram", "dashboard"] = "dashboard"
    answers: list[CheckinAnswer] = Field(min_length=1, max_length=12)
    note: str | None = Field(default=None, max_length=800)
    submitted_at: datetime | None = None


class CheckinSubmitByTokenRequest(BaseModel):
    token: str = Field(min_length=8, max_length=2048)
    answers: list[CheckinAnswer] = Field(min_length=1, max_length=12)
    note: str | None = Field(default=None, max_length=800)
    channel: Literal["email", "telegram", "dashboard"] = "email"


def _derive_scores(answers: list[CheckinAnswer]) -> tuple[float, float | None]:
    mood_avg = sum(a.score for a in answers) / len(answers)
    challenge_scores = [a.score for a in answers if a.key.lower() in _CHALLENGE_KEYS]
    challenge_avg = (sum(challenge_scores) / len(challenge_scores)) if challenge_scores else None
    return mood_avg, challenge_avg


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
    mood_score, challenge_score = _derive_scores(answers)
    row = insert_checkin_response(
        client,
        {
            "checkin_date": on_date.isoformat(),
            "window": window,
            "channel": channel,
            "answers": [answer.model_dump() for answer in answers],
            "mood_score": round(mood_score, 3),
            "challenge_score": round(challenge_score, 3) if challenge_score is not None else None,
            "note": note,
            "submitted_at": submitted_at.isoformat(),
            "schema_version": 1,
        },
    )
    return row


@router.get("/questions")
def questions() -> dict:
    # Light-weight starter set; can be made dynamic via DB-backed prompt configs later.
    return {"schema_version": 1, "questions": _QUESTIONS}


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
    return {
        "status": "ok",
        "window": payload["window"],
        "date": payload["date"],
        "questions": _QUESTIONS,
        "schema_version": 1,
    }


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
        on_date = date_type.fromisoformat(token_payload["date"])
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Token date is invalid.") from exc

    submitted_at = datetime.now(timezone.utc)
    row = _persist_checkin(
        on_date=on_date,
        window=str(token_payload["window"]),
        channel=payload.channel,
        answers=payload.answers,
        note=payload.note,
        submitted_at=submitted_at,
    )
    return {"status": "ok", "data": row, "window": token_payload["window"], "date": token_payload["date"]}


@router.post("/submit")
def submit_checkin(payload: CheckinSubmitRequest) -> dict:
    submitted_at = payload.submitted_at or datetime.now(timezone.utc)
    row = _persist_checkin(
        on_date=submitted_at.date(),
        window=payload.window,
        channel=payload.channel,
        answers=payload.answers,
        note=payload.note,
        submitted_at=submitted_at,
    )
    return {"status": "ok", "data": row}
