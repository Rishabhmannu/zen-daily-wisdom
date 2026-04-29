"""Shared helpers for delivering check-in reminder emails + Telegram messages.

Centralizes link building, template rendering, and the localhost guard so the
dashboard and internal scheduler routes don't drift out of sync.
"""

from __future__ import annotations

from datetime import date as date_type
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from jinja2 import Environment, FileSystemLoader, select_autoescape

from zen_backend.config import settings
from zen_backend.security.checkin_token import issue_checkin_token

_TEMPLATE_ENV = Environment(
    loader=FileSystemLoader(str(Path(__file__).resolve().parents[1] / "templates")),
    autoescape=select_autoescape(["html", "xml"]),
)

_WINDOW_INTRO = {
    "morning": (
        "A small grounding before the day pulls you in every direction. "
        "Tell us how you're starting — it shapes tonight's reflection."
    ),
    "midday": (
        "A short pause in the middle of the day. "
        "How does this hour feel? Your answer steers tomorrow's message."
    ),
    "evening": (
        "Close out today with a steady look at what it actually felt like. "
        "Your answers shape tomorrow's reflection."
    ),
}


def resolve_window(window: str | None) -> str:
    """Resolve an explicit window or derive one from current IST time."""
    if window in {"morning", "midday", "evening"}:
        return window  # type: ignore[return-value]
    now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
    hour = now_ist.hour
    if hour < 12:
        return "morning"
    if hour < 17:
        return "midday"
    return "evening"


def require_public_frontend_url() -> str:
    """Return the configured frontend base URL, refusing localhost values
    (localhost links in emails sent from production are always broken)."""
    if settings.is_localhost_frontend:
        raise HTTPException(
            status_code=500,
            detail=(
                "NEXT_PUBLIC_FRONTEND_URL is set to localhost on the backend. "
                "Set it to the production frontend URL (e.g. your Vercel domain) "
                "so check-in emails contain a working link."
            ),
        )
    return settings.frontend_base_url.rstrip("/")


def build_signed_checkin_url(window: str, on_date: date_type) -> str:
    secret = settings.effective_checkin_link_secret
    if not secret:
        raise HTTPException(
            status_code=500,
            detail=(
                "Check-in link secret is not configured. "
                "Set CHECKIN_LINK_SECRET (or FEEDBACK_LINK_SECRET as a fallback)."
            ),
        )
    base = require_public_frontend_url()
    token = issue_checkin_token(secret=secret, window=window, on_date=on_date)
    return f"{base}/checkin?token={token}"


def render_checkin_email_html(window: str, checkin_url: str) -> str:
    template = _TEMPLATE_ENV.get_template("email_checkin.html.j2")
    return template.render(
        window=window,
        window_title=window.title(),
        intro_line=_WINDOW_INTRO.get(window, _WINDOW_INTRO["evening"]),
        checkin_url=checkin_url,
    )


def checkin_email_subject(window: str) -> str:
    return f"Zen Check-in ({window.title()})"
