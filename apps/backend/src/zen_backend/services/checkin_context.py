from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass
class CheckinSummary:
    has_data: bool
    mood_avg: float | None  # 0-100 if available, else legacy 1-5 mean
    mood_avg_weighted: float | None  # 0-100, only when weighted_v1 rows exist
    challenge_avg: float | None
    latest_window: str | None
    latest_note: str | None
    context_line: str


def _row_mood_0_100(row: dict[str, Any]) -> float | None:
    """Coerce whatever mood representation the row has into a 0-100 float.

    Prefers `mood_score_weighted` (the new headline number). Falls back to
    `mood_score` interpreted as the legacy raw 1-5 mean and rescaled to 0-100.
    """
    weighted = row.get("mood_score_weighted")
    if weighted is not None:
        try:
            return float(weighted)
        except (TypeError, ValueError):
            pass
    legacy = row.get("mood_score")
    if legacy is None:
        return None
    try:
        legacy_f = float(legacy)
    except (TypeError, ValueError):
        return None
    # Heuristic: legacy values are in [1, 5]. New equal/weighted rows are
    # 0-100. If the value is suspiciously small treat as legacy and rescale.
    if 1.0 <= legacy_f <= 5.0:
        return (legacy_f - 1.0) / 4.0 * 100.0
    return legacy_f


def build_checkin_summary(checkins: list[dict[str, Any]], run_date: date) -> CheckinSummary:
    todays = [row for row in checkins if str(row.get("checkin_date")) == run_date.isoformat()]
    if not todays:
        return CheckinSummary(
            has_data=False,
            mood_avg=None,
            mood_avg_weighted=None,
            challenge_avg=None,
            latest_window=None,
            latest_note=None,
            context_line="No same-day check-in responses yet.",
        )

    mood_values_0_100: list[float] = []
    weighted_values: list[float] = []
    for row in todays:
        m = _row_mood_0_100(row)
        if m is not None:
            mood_values_0_100.append(m)
        if row.get("mood_score_weighted") is not None:
            try:
                weighted_values.append(float(row["mood_score_weighted"]))
            except (TypeError, ValueError):
                pass

    challenge_values = [
        float(row["challenge_score"]) for row in todays if row.get("challenge_score") is not None
    ]
    mood_avg = (sum(mood_values_0_100) / len(mood_values_0_100)) if mood_values_0_100 else None
    mood_avg_weighted = (sum(weighted_values) / len(weighted_values)) if weighted_values else None
    challenge_avg = (sum(challenge_values) / len(challenge_values)) if challenge_values else None

    latest = todays[0]
    latest_window = str(latest.get("window")) if latest.get("window") else None
    latest_note = str(latest.get("note")) if latest.get("note") else None

    segments: list[str] = []
    if mood_avg is not None:
        segments.append(f"today mood={mood_avg:.0f}/100")
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
        mood_avg_weighted=mood_avg_weighted,
        challenge_avg=challenge_avg,
        latest_window=latest_window,
        latest_note=latest_note,
        context_line=context_line,
    )
