"""Orchestrator for the dashboard's "this week" Gemini narrative card.

Reads the last N days of check-in rollups, summarizes them into the
shape Gemini needs, calls Gemini with a wall-clock timeout, validates
the output against the same forbidden-phrase guard used elsewhere, and
either persists a `gemini` row or a `fallback` row in
`dashboard_narrative_cache`. The DB row is the source of truth — every
read of the dashboard hits the cache, never Gemini, unless the row is
stale or a refresh was explicitly requested.
"""

from __future__ import annotations

import concurrent.futures
import logging
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from supabase import Client

from zen_backend.config import settings
from zen_backend.db.queries import (
    get_dashboard_narrative,
    get_recent_checkin_responses,
    upsert_dashboard_narrative,
)
from zen_backend.services.gemini_client import generate_dashboard_narrative

logger = logging.getLogger(__name__)

NARRATIVE_KIND = "weekly"
WINDOW_DAYS = 14


_FORBIDDEN_PHRASES: tuple[str, ...] = (
    "you've got this",
    "trust the journey",
    "embrace",
    "manifest",
    "hustle",
    "grind",
    "level up",
    "remember that,",
    "based on your",
    "i see that",
    "this week",
    "this period",
    "your data",
    "the data",
)

_FORBIDDEN_OPENERS: tuple[str, ...] = (
    "i see",
    "it looks like",
    "based on",
    "your answers",
    "the data",
    "your check-in",
    "this week",
    "this period",
)


@dataclass
class NarrativePayload:
    body: str
    source_method: str  # "gemini" or "fallback"
    generated_at: datetime
    age_minutes: float
    is_fresh: bool


def _validate(text: str) -> bool:
    if not text or not text.strip():
        return False
    lowered = text.strip().lower()
    if any(lowered.startswith(opener) for opener in _FORBIDDEN_OPENERS):
        return False
    if any(phrase in lowered for phrase in _FORBIDDEN_PHRASES):
        return False
    word_count = len(re.findall(r"\b\w+\b", text))
    if word_count < 30 or word_count > 130:
        return False
    return True


def _coerce_mood_to_0_100(row: dict[str, Any]) -> float | None:
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
    if 1.0 <= legacy_f <= 5.0:
        return (legacy_f - 1.0) / 4.0 * 100.0
    return legacy_f


def _summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Roll a flat list of check-in rows into the structured fields the
    Gemini prompt expects."""
    today = datetime.now(timezone.utc).date()
    cutoff = today - timedelta(days=WINDOW_DAYS - 1)
    in_window = [
        r for r in rows
        if r.get("checkin_date")
        and datetime.fromisoformat(str(r["checkin_date"])).date() >= cutoff
    ]

    submissions_total = len(in_window)
    days_with_submission = len({str(r.get("checkin_date")) for r in in_window})

    moods = [m for m in (_coerce_mood_to_0_100(r) for r in in_window) if m is not None]
    avg_mood = sum(moods) / len(moods) if moods else None

    challenges = [
        float(r["challenge_score"]) for r in in_window if r.get("challenge_score") is not None
    ]
    avg_challenge = sum(challenges) / len(challenges) if challenges else None

    window_counter: Counter[str] = Counter()
    for r in in_window:
        w = str(r.get("window") or "")
        if w in {"morning", "midday", "evening"}:
            window_counter[w] += 1
    most_completed_window = window_counter.most_common(1)[0][0] if window_counter else None

    # Mood trend: ordered first-half mean vs second-half mean of submissions
    # within the window. "Held steady", "drifted up", "softened down".
    chronological = sorted(
        [r for r in in_window if r.get("submitted_at") and r.get("checkin_date")],
        key=lambda r: str(r.get("submitted_at")),
    )
    chronological_moods = [
        m for m in (_coerce_mood_to_0_100(r) for r in chronological) if m is not None
    ]
    if len(chronological_moods) >= 4:
        half = len(chronological_moods) // 2
        first_avg = sum(chronological_moods[:half]) / half
        second_avg = sum(chronological_moods[half:]) / (len(chronological_moods) - half)
        delta = second_avg - first_avg
        if delta >= 8:
            trend_summary = "drifted upward in the second half"
        elif delta <= -8:
            trend_summary = "softened in the second half"
        else:
            trend_summary = "held steady throughout"
    elif chronological_moods:
        trend_summary = "too few entries to read a trend"
    else:
        trend_summary = "no mood data yet"

    # Most recent user note, truncated.
    recent_note: str | None = None
    for r in chronological[::-1]:
        n = r.get("note")
        if isinstance(n, str) and n.strip():
            recent_note = n.strip()[:140]
            break

    return {
        "days_considered": WINDOW_DAYS,
        "submissions_total": submissions_total,
        "days_with_submission": days_with_submission,
        "avg_mood_0_100": avg_mood,
        "avg_challenge": avg_challenge,
        "most_completed_window": most_completed_window,
        "trend_summary": trend_summary,
        "recent_note": recent_note,
    }


def _fallback_text(summary: dict[str, Any]) -> str:
    """Static fallback used when Gemini is disabled, fails, times out, or
    returns invalid output. Aimed at being calm, never wrong."""
    if summary["submissions_total"] == 0:
        return (
            "Nothing has been recorded yet. Open the next check-in email when it arrives "
            "and answer at the speed it asks for. The fortnight will draw itself in."
        )
    avg_mood = summary["avg_mood_0_100"]
    if avg_mood is None:
        steadiness_line = "There is enough here to begin reading a shape, even if the picture is still rough."
    elif avg_mood >= 65:
        steadiness_line = "There is a steadiness in the recent answers worth holding loosely."
    elif avg_mood <= 40:
        steadiness_line = "The recent answers are carrying weight; let the small days remain small."
    else:
        steadiness_line = "The recent answers sit in the middle band — neither bright nor heavy."
    return (
        f"You have logged {summary['submissions_total']} check-ins across "
        f"{summary['days_with_submission']} days of the last {WINDOW_DAYS}. {steadiness_line} "
        "Notice one quiet thing in the next hour and let the rest pass by."
    )


def _gemini_with_timeout(summary: dict[str, Any], timeout_s: float) -> str | None:
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(generate_dashboard_narrative, **summary)
        try:
            return future.result(timeout=timeout_s)
        except concurrent.futures.TimeoutError:
            logger.warning(
                "Dashboard narrative Gemini call timed out after %.1fs", timeout_s
            )
            return None
        except Exception as exc:  # noqa: BLE001
            logger.warning("Dashboard narrative Gemini call failed: %s", exc)
            return None


def _payload_from_row(row: dict[str, Any]) -> NarrativePayload:
    raw = row.get("generated_at")
    if isinstance(raw, datetime):
        generated_at = raw.astimezone(timezone.utc) if raw.tzinfo else raw.replace(
            tzinfo=timezone.utc
        )
    else:
        try:
            generated_at = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if generated_at.tzinfo is None:
                generated_at = generated_at.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            generated_at = datetime.now(timezone.utc)
    age = datetime.now(timezone.utc) - generated_at
    age_minutes = max(0.0, age.total_seconds() / 60.0)
    is_fresh = age_minutes <= settings.dashboard_narrative_ttl_minutes
    return NarrativePayload(
        body=str(row.get("body", "")),
        source_method=str(row.get("source_method", "fallback")),
        generated_at=generated_at,
        age_minutes=age_minutes,
        is_fresh=is_fresh,
    )


def _generate_and_persist(client: Client) -> NarrativePayload:
    rows = get_recent_checkin_responses(client, limit=120)
    summary = _summarize_rows(rows)

    if not settings.enable_dashboard_narrative or not settings.gemini_api_key:
        body = _fallback_text(summary)
        source_method = "fallback"
    else:
        raw = _gemini_with_timeout(summary, settings.dashboard_narrative_timeout_s)
        if raw is not None and _validate(raw):
            body = raw.strip()
            source_method = "gemini"
        else:
            if raw is not None:
                logger.info(
                    "Dashboard narrative Gemini output rejected by validator: %r",
                    raw[:160],
                )
            body = _fallback_text(summary)
            source_method = "fallback"

    saved = upsert_dashboard_narrative(
        client,
        kind=NARRATIVE_KIND,
        body=body,
        source_method=source_method,
    )
    return _payload_from_row(saved)


def get_or_generate_weekly_narrative(
    client: Client, *, force_refresh: bool = False
) -> NarrativePayload:
    """Public entry point used by the dashboard routes.

    - If `force_refresh=True`, always regenerate.
    - Otherwise, return the cached row if it's within the TTL.
    - On any internal failure during regeneration, fall back to whatever
      cached row exists (even if stale) so the dashboard is never empty.
    """
    if not force_refresh:
        try:
            existing = get_dashboard_narrative(client, NARRATIVE_KIND)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to read dashboard_narrative_cache: %s", exc)
            existing = None
        if existing:
            payload = _payload_from_row(existing)
            if payload.is_fresh:
                return payload

    try:
        return _generate_and_persist(client)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to regenerate dashboard narrative: %s", exc)
        existing = None
        try:
            existing = get_dashboard_narrative(client, NARRATIVE_KIND)
        except Exception:  # noqa: BLE001
            pass
        if existing:
            return _payload_from_row(existing)
        # Nothing in cache and we couldn't generate. Synthesize a one-shot
        # fallback in memory so the route still returns 200.
        rows: list[dict[str, Any]] = []
        try:
            rows = get_recent_checkin_responses(client, limit=120)
        except Exception:  # noqa: BLE001
            pass
        body = _fallback_text(_summarize_rows(rows))
        return NarrativePayload(
            body=body,
            source_method="fallback",
            generated_at=datetime.now(timezone.utc),
            age_minutes=0.0,
            is_fresh=True,
        )
