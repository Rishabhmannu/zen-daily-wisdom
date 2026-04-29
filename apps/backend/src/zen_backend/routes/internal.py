from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from zen_backend.config import settings
from zen_backend.security.hmac_sig import verify_payload
from zen_backend.services.checkin_delivery import (
    build_signed_checkin_url,
    checkin_email_subject,
    render_checkin_email_html,
    resolve_window,
)
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


@router.post("/checkin-reminders")
def checkin_reminders(
    payload: CheckinReminderRequest,
    x_internal_signature: str | None = Header(default=None, alias="X-Internal-Signature"),
) -> dict[str, object]:
    raw = json.dumps(payload.model_dump(mode="json"), separators=(",", ":"), sort_keys=True).encode("utf-8")
    _require_signature(raw, x_internal_signature)

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
    # Build the signed URL lazily — only when at least one channel will use it.
    # This way, calling the endpoint with no delivery channels configured (e.g.
    # in tests) doesn't trip the localhost guard.
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

