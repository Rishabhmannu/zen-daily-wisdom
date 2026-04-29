from __future__ import annotations

import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from zen_backend.config import settings
from zen_backend.security.hmac_sig import verify_payload
from zen_backend.services.generator import run_daily_generation
from zen_backend.services.gmail_client import send_email_to_many
from zen_backend.services.telegram_client import send_checkin_reminder

router = APIRouter(prefix="/internal", tags=["internal"])


class GenerateRequest(BaseModel):
    date: str | None = None
    force: bool = False


class CheckinReminderRequest(BaseModel):
    window: str | None = None


def _require_signature(raw_body: bytes, signature: str | None) -> None:
    if not settings.internal_hmac_secret:
        raise HTTPException(status_code=500, detail="INTERNAL_HMAC_SECRET not configured")
    if not signature or not verify_payload(settings.internal_hmac_secret, raw_body, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")


@router.post("/generate")
def generate(
    payload: GenerateRequest,
    x_internal_signature: str | None = Header(default=None, alias="X-Internal-Signature"),
) -> dict[str, object]:
    raw = json.dumps(payload.model_dump(mode="json"), separators=(",", ":"), sort_keys=True).encode("utf-8")
    _require_signature(raw, x_internal_signature)

    if payload.date:
        try:
            run_date = date.fromisoformat(payload.date)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD.") from exc
    else:
        run_date = date.today()
    return run_daily_generation(run_date=run_date, force=payload.force)


def _resolve_window(window: str | None) -> str:
    if window in {"morning", "midday", "evening"}:
        return window
    now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
    hour = now_ist.hour
    if hour < 12:
        return "morning"
    if hour < 17:
        return "midday"
    return "evening"


@router.post("/checkin-reminders")
def checkin_reminders(
    payload: CheckinReminderRequest,
    x_internal_signature: str | None = Header(default=None, alias="X-Internal-Signature"),
) -> dict[str, object]:
    raw = json.dumps(payload.model_dump(mode="json"), separators=(",", ":"), sort_keys=True).encode("utf-8")
    _require_signature(raw, x_internal_signature)

    window = _resolve_window(payload.window)
    frontend_url = settings.frontend_base_url.rstrip("/")
    checkin_url = f"{frontend_url}/dashboard"

    delivery: dict[str, object] = {"window": window}
    if (
        settings.gmail_from_address
        and settings.gmail_client_id
        and settings.gmail_client_secret
        and settings.gmail_refresh_token
    ):
        email_html = (
            f"<p>Check-in reminder for <strong>{window}</strong>.</p>"
            "<p>Please submit today's quick check-in (8 questions, 1-5 scale).</p>"
            f'<p><a href="{checkin_url}">Open Dashboard Check-in</a></p>'
        )
        recipients = settings.gmail_to_addresses or [settings.gmail_from_address]
        delivery["email"] = {
            "recipients": recipients,
            "messages": send_email_to_many(f"Zen Check-in ({window.title()})", email_html, recipients),
        }

    if settings.telegram_bot_token and settings.telegram_chat_id:
        delivery["telegram"] = send_checkin_reminder(window=window, checkin_url=checkin_url)

    return {"status": "sent", "delivery": delivery}

