from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from zen_backend.db.client import get_supabase_client
from zen_backend.db.queries import insert_checkin_response

router = APIRouter(prefix="/checkin", tags=["checkin"])

_CHALLENGE_KEYS = {"day_load", "stress", "anxiety", "overwhelm", "pressure"}


class CheckinAnswer(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    score: int = Field(ge=1, le=5)


class CheckinSubmitRequest(BaseModel):
    window: Literal["morning", "midday", "evening"]
    channel: Literal["email", "telegram", "dashboard"] = "dashboard"
    answers: list[CheckinAnswer] = Field(min_length=1, max_length=12)
    note: str | None = Field(default=None, max_length=800)
    submitted_at: datetime | None = None


def _derive_scores(answers: list[CheckinAnswer]) -> tuple[float, float | None]:
    mood_avg = sum(a.score for a in answers) / len(answers)
    challenge_scores = [a.score for a in answers if a.key.lower() in _CHALLENGE_KEYS]
    challenge_avg = (sum(challenge_scores) / len(challenge_scores)) if challenge_scores else None
    return mood_avg, challenge_avg


@router.get("/questions")
def questions() -> dict:
    # Light-weight starter set; can be made dynamic via DB-backed prompt configs later.
    return {
        "schema_version": 1,
        "questions": [
            {"key": "sleep_quality", "label": "How was your sleep quality?", "scale": [1, 5]},
            {"key": "energy", "label": "How is your energy right now?", "scale": [1, 5]},
            {"key": "focus", "label": "How focused do you feel?", "scale": [1, 5]},
            {"key": "stress", "label": "How stressed do you feel?", "scale": [1, 5]},
            {"key": "day_load", "label": "How heavy does today feel?", "scale": [1, 5]},
            {"key": "motivation", "label": "How motivated do you feel?", "scale": [1, 5]},
            {"key": "positivity", "label": "How positive is your mindset?", "scale": [1, 5]},
            {"key": "clarity", "label": "How clear is your next step?", "scale": [1, 5]},
        ],
    }


@router.post("/submit")
def submit_checkin(payload: CheckinSubmitRequest) -> dict:
    client = get_supabase_client()
    submitted_at = payload.submitted_at or datetime.now(timezone.utc)
    mood_score, challenge_score = _derive_scores(payload.answers)

    row = insert_checkin_response(
        client,
        {
            "checkin_date": submitted_at.date().isoformat(),
            "window": payload.window,
            "channel": payload.channel,
            "answers": [answer.model_dump() for answer in payload.answers],
            "mood_score": round(mood_score, 3),
            "challenge_score": round(challenge_score, 3) if challenge_score is not None else None,
            "note": payload.note,
            "submitted_at": submitted_at.isoformat(),
            "schema_version": 1,
        },
    )
    return {"status": "ok", "data": row}
