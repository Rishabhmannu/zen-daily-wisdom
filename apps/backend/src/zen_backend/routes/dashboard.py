from __future__ import annotations

from datetime import date
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from zen_backend.config import settings
from zen_backend.db.client import get_supabase_client
from zen_backend.db.queries import (
    get_bandit_state,
    get_feedback_for_sent_ids,
    get_latest_sent_history,
    get_recent_checkin_responses,
    get_recent_sent_history,
)
from zen_backend.security.jwt_verify import verify_owner_user
from zen_backend.services.checkin_delivery import (
    build_signed_checkin_url,
    checkin_email_subject,
    render_checkin_email_html,
    resolve_window,
)
from zen_backend.services.dashboard_narrative import (
    NarrativePayload,
    get_or_generate_weekly_narrative,
)
from zen_backend.services.generator import run_daily_generation
from zen_backend.services.gmail_client import send_email_to_many
from zen_backend.services.telegram_client import send_checkin_reminder

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class SendNowRequest(BaseModel):
    force: bool = True


class SendCheckinNowRequest(BaseModel):
    window: str | None = None


def _with_style_key(row: dict | None) -> dict | None:
    if not row:
        return row
    item = dict(row)
    trace = item.get("retrieval_trace") or {}
    if isinstance(trace, dict):
        item["style_key"] = trace.get("style_key")
    else:
        item["style_key"] = None
    return item


@router.get("/today")
def today(_: dict = Depends(verify_owner_user)) -> dict:
    client = get_supabase_client()
    rows = get_latest_sent_history(client, limit=1)
    return {"data": _with_style_key(rows[0]) if rows else None}


@router.get("/history")
def history(limit: int = Query(default=30, ge=1, le=200), _: dict = Depends(verify_owner_user)) -> dict:
    client = get_supabase_client()
    sent_rows = get_recent_sent_history(client, limit=limit)
    sent_ids = [str(r.get("id")) for r in sent_rows if r.get("id")]
    feedback_rows = get_feedback_for_sent_ids(client, sent_ids)
    feedback_by_sent: dict[str, list[dict]] = {}
    for row in feedback_rows:
        sid = str(row.get("sent_id"))
        feedback_by_sent.setdefault(sid, []).append(row)

    enriched = []
    for row in sent_rows:
        sid = str(row.get("id"))
        item = _with_style_key(row) or {}
        item["feedback"] = feedback_by_sent.get(sid, [])
        enriched.append(item)
    return {"data": enriched}


@router.get("/bandit")
def bandit(limit: int = Query(default=200, ge=1, le=500), _: dict = Depends(verify_owner_user)) -> dict:
    client = get_supabase_client()
    rows = get_bandit_state(client, limit=limit)
    for row in rows:
        alpha = float(row.get("alpha", 1.0))
        beta = float(row.get("beta", 1.0))
        row["expected_value"] = alpha / (alpha + beta) if (alpha + beta) else 0.0
    rows.sort(key=lambda r: float(r.get("expected_value", 0.0)), reverse=True)
    return {"data": rows}


@router.post("/send-now")
def send_now(payload: SendNowRequest, _: dict = Depends(verify_owner_user)) -> dict:
    # Personal single-user project endpoint; intentionally simple.
    return run_daily_generation(run_date=date.today(), force=payload.force)


def _row_mood_to_0_100(row: dict) -> float | None:
    """Coerce whichever mood field a check-in row carries into a 0-100 float.

    Prefers the new weighted score; falls back to the legacy 1-5 mean and
    rescales it. Returns None if neither is present or parseable.
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
    if 1.0 <= legacy_f <= 5.0:
        return (legacy_f - 1.0) / 4.0 * 100.0
    return legacy_f


def _build_daily_series(
    rows: list[dict],
    dates_considered: list[str],
) -> list[dict]:
    """Per-day rollup for the 14-day mood line chart.

    For each date in `dates_considered` (newest -> oldest), emit a single
    point: the mean of all that day's mood_score_weighted values, plus the
    submission count and which windows were filled. Days with no
    submissions get `mood: None` so the line draws as a gap rather than a
    misleading zero.
    """
    by_date: dict[str, list[float]] = {}
    windows_by_date: dict[str, set[str]] = {}
    for row in rows:
        d = str(row.get("checkin_date") or "")
        if not d:
            continue
        m = _row_mood_to_0_100(row)
        if m is not None:
            by_date.setdefault(d, []).append(m)
        w = str(row.get("window") or "")
        if w in {"morning", "midday", "evening"}:
            windows_by_date.setdefault(d, set()).add(w)

    series: list[dict] = []
    # Render oldest -> newest so the chart's left-to-right axis is natural.
    for d in reversed(dates_considered):
        moods = by_date.get(d, [])
        windows = sorted(windows_by_date.get(d, set()))
        series.append(
            {
                "date": d,
                "mood": round(sum(moods) / len(moods), 2) if moods else None,
                "submissions": len(windows),
                "windows": windows,
            }
        )
    return series


@router.get("/checkins")
def checkins(
    limit: int = Query(default=60, ge=1, le=300),
    days: int = Query(default=14, ge=1, le=60),
    _: dict = Depends(verify_owner_user),
) -> dict:
    client = get_supabase_client()
    rows = get_recent_checkin_responses(client, limit=limit)

    expected_windows = {"morning", "midday", "evening"}
    window_hits_by_date: dict[str, set[str]] = {}
    for row in rows:
        row_date = str(row.get("checkin_date"))
        window = str(row.get("window"))
        if row_date and window in expected_windows:
            window_hits_by_date.setdefault(row_date, set()).add(window)

    today = datetime.utcnow().date()
    dates_considered = [(today - timedelta(days=offset)).isoformat() for offset in range(days)]
    observed = sum(len(window_hits_by_date.get(day, set())) for day in dates_considered)
    expected = len(dates_considered) * len(expected_windows)
    completion_rate = (observed / expected) if expected else 0.0

    mood_values_0_100 = [
        m for m in (_row_mood_to_0_100(row) for row in rows) if m is not None
    ]
    challenge_values = [
        float(row["challenge_score"])
        for row in rows
        if row.get("challenge_score") is not None
    ]
    legacy_mood_values = [
        float(row["mood_score"]) for row in rows if row.get("mood_score") is not None
    ]
    daily_series = _build_daily_series(rows, dates_considered)

    stats = {
        "completion_rate": completion_rate,
        "avg_mood_0_100": (
            sum(mood_values_0_100) / len(mood_values_0_100)
            if mood_values_0_100
            else None
        ),
        # Legacy 1-5 average kept for any consumer that hasn't migrated yet.
        "avg_mood_legacy_1to5": (
            sum(legacy_mood_values) / len(legacy_mood_values) if legacy_mood_values else None
        ),
        "avg_challenge": (
            sum(challenge_values) / len(challenge_values) if challenge_values else None
        ),
        "days_considered": days,
        "daily_series": daily_series,
    }
    return {"data": rows, "stats": stats}


def _serialize_narrative(payload: NarrativePayload) -> dict[str, object]:
    return {
        "body": payload.body,
        "source_method": payload.source_method,
        "generated_at": payload.generated_at.isoformat(),
        "age_minutes": round(payload.age_minutes, 2),
        "is_fresh": payload.is_fresh,
    }


@router.get("/narrative")
def get_narrative(_: dict = Depends(verify_owner_user)) -> dict[str, object]:
    """Return the cached weekly narrative card. Regenerates only if the
    cache is empty or older than the configured TTL."""
    client = get_supabase_client()
    payload = get_or_generate_weekly_narrative(client, force_refresh=False)
    return {"data": _serialize_narrative(payload)}


@router.post("/narrative/refresh")
def refresh_narrative(_: dict = Depends(verify_owner_user)) -> dict[str, object]:
    """Force a regeneration of the weekly narrative card. Used by the
    dashboard's manual refresh button."""
    client = get_supabase_client()
    payload = get_or_generate_weekly_narrative(client, force_refresh=True)
    return {"data": _serialize_narrative(payload)}


@router.post("/checkins/send-now")
def send_checkin_now(
    payload: SendCheckinNowRequest,
    _: dict = Depends(verify_owner_user),
) -> dict[str, object]:
    window = resolve_window(payload.window)
    on_date = date.today()

    gmail_enabled = (
        bool(settings.gmail_from_address)
        and bool(settings.gmail_client_id)
        and bool(settings.gmail_client_secret)
        and bool(settings.gmail_refresh_token)
    )
    telegram_enabled = bool(settings.telegram_bot_token) and bool(settings.telegram_chat_id)

    delivery: dict[str, object] = {"window": window, "date": on_date.isoformat()}
    checkin_url = (
        build_signed_checkin_url(window=window, on_date=on_date)
        if (gmail_enabled or telegram_enabled)
        else None
    )

    if gmail_enabled and checkin_url:
        email_html = render_checkin_email_html(window=window, checkin_url=checkin_url)
        recipients = settings.gmail_to_addresses or [settings.gmail_from_address]
        delivery["email"] = {
            "recipients": recipients,
            "messages": send_email_to_many(checkin_email_subject(window), email_html, recipients),
        }

    if telegram_enabled and checkin_url:
        try:
            delivery["telegram"] = send_checkin_reminder(window=window, checkin_url=checkin_url)
        except Exception as exc:  # noqa: BLE001 — surface error without crashing the whole batch
            delivery["telegram"] = {"status": "error", "error": str(exc)}

    return {"status": "sent", "delivery": delivery}

