from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass
class CheckinSummary:
    has_data: bool
    mood_avg: float | None
    challenge_avg: float | None
    latest_window: str | None
    latest_note: str | None
    context_line: str


def build_checkin_summary(checkins: list[dict[str, Any]], run_date: date) -> CheckinSummary:
    todays = [row for row in checkins if str(row.get("checkin_date")) == run_date.isoformat()]
    if not todays:
        return CheckinSummary(
            has_data=False,
            mood_avg=None,
            challenge_avg=None,
            latest_window=None,
            latest_note=None,
            context_line="No same-day check-in responses yet.",
        )

    mood_values = [float(row["mood_score"]) for row in todays if row.get("mood_score") is not None]
    challenge_values = [
        float(row["challenge_score"]) for row in todays if row.get("challenge_score") is not None
    ]
    mood_avg = (sum(mood_values) / len(mood_values)) if mood_values else None
    challenge_avg = (sum(challenge_values) / len(challenge_values)) if challenge_values else None

    latest = todays[0]
    latest_window = str(latest.get("window")) if latest.get("window") else None
    latest_note = str(latest.get("note")) if latest.get("note") else None

    segments: list[str] = []
    if mood_avg is not None:
        segments.append(f"today mood={mood_avg:.1f}/5")
    if challenge_avg is not None:
        segments.append(f"challenge-load={challenge_avg:.1f}/5")
    if latest_window:
        segments.append(f"latest window={latest_window}")
    if latest_note:
        segments.append(f"latest note='{latest_note[:120]}'")

    context_line = "; ".join(segments) if segments else "Check-in submitted today."
    return CheckinSummary(
        has_data=True,
        mood_avg=mood_avg,
        challenge_avg=challenge_avg,
        latest_window=latest_window,
        latest_note=latest_note,
        context_line=context_line,
    )
