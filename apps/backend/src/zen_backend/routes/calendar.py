"""Add-to-Calendar redirect.

Receives a short, HMAC-signed link of the form
`/calendar/add?sent_id=<uuid>&sig=<hex>`, looks up the corresponding
`sent_history` row, builds the canonical Google Calendar `render?...`
deep link, and 302s the user there. This keeps the URL preview shown by
iOS Telegram (and any other client that previews destinations) short
and recognizable — it's our backend domain, not a 250-character Google
URL.
"""

from __future__ import annotations

from datetime import date, timedelta
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from zen_backend.config import settings
from zen_backend.db.client import get_supabase_client
from zen_backend.db.queries import get_sent_history_by_id
from zen_backend.security.calendar_link import verify_calendar_link

router = APIRouter(tags=["calendar"])


def _build_google_calendar_url(
    *,
    run_date: date,
    theme_of_day: str,
    description: str,
    citation: str,
) -> str:
    start = run_date.strftime("%Y%m%d")
    end_date = (run_date + timedelta(days=1)).strftime("%Y%m%d")
    text = quote(f"Theme of the Day: {theme_of_day}")
    details = quote(f"{description}\n\nSource: {citation}")
    return (
        "https://calendar.google.com/calendar/render?action=TEMPLATE"
        f"&text={text}&dates={start}/{end_date}&details={details}"
    )


@router.get("/calendar/add")
def add_to_calendar(
    sent_id: str = Query(..., min_length=8, max_length=128),
    sig: str = Query(..., min_length=8, max_length=256),
) -> RedirectResponse:
    secret = settings.feedback_link_secret
    if not secret:
        raise HTTPException(
            status_code=500,
            detail="FEEDBACK_LINK_SECRET is not configured.",
        )
    if not verify_calendar_link(secret, sent_id, sig):
        raise HTTPException(status_code=401, detail="Invalid calendar link signature.")

    client = get_supabase_client()
    sent = get_sent_history_by_id(client, sent_id)
    if not sent:
        raise HTTPException(status_code=404, detail="sent_id not found.")

    sent_date_raw = sent.get("sent_date")
    try:
        run_date = (
            date.fromisoformat(str(sent_date_raw))
            if sent_date_raw
            else date.today()
        )
    except ValueError:
        run_date = date.today()

    theme_of_day = str(sent.get("theme_of_day") or "Today's reflection")
    description_raw = str(sent.get("llm_output") or "")
    description = description_raw[:500]
    # Best-effort citation reconstruction. Daily emails store the citation
    # inside the LLM output / template render path rather than as a column,
    # so we degrade gracefully if it's missing.
    citation = "Zen Daily Wisdom"

    target = _build_google_calendar_url(
        run_date=run_date,
        theme_of_day=theme_of_day,
        description=description,
        citation=citation,
    )
    return RedirectResponse(url=target, status_code=302)
