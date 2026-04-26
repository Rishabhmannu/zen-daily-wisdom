from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request

from zen_backend.config import settings
from zen_backend.db.client import get_supabase_client
from zen_backend.db.queries import insert_feedback, insert_mood_log
from zen_backend.services.telegram_client import answer_callback_query, send_message

router = APIRouter(prefix="/telegram", tags=["telegram"])


def _safe_answer_callback(callback_id: str, text: str) -> None:
    if not callback_id:
        return
    try:
        answer_callback_query(callback_id, text=text)
    except Exception:
        # Webhook should stay durable even when Telegram API is temporarily unavailable.
        return


def _safe_send_message(text: str) -> None:
    try:
        send_message(text)
    except Exception:
        # Avoid failing webhook processing due to network/API transient errors.
        return


def _verify_secret(header_value: str | None) -> None:
    expected = settings.telegram_webhook_secret.strip()
    if expected and header_value != expected:
        raise HTTPException(status_code=401, detail="Invalid telegram webhook secret.")


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(
        default=None, alias="X-Telegram-Bot-Api-Secret-Token"
    ),
) -> dict:
    _verify_secret(x_telegram_bot_api_secret_token)
    update = await request.json()
    client = get_supabase_client()

    callback = update.get("callback_query")
    if callback:
        callback_id = str(callback.get("id", ""))
        data = str(callback.get("data", ""))
        # Expected format: rate:<sent_id>:<rating>
        if data.startswith("rate:"):
            try:
                _, sent_id, rating_raw = data.split(":", 2)
                rating = int(rating_raw)
            except (ValueError, TypeError):
                rating = 0
                sent_id = ""
            if sent_id and 1 <= rating <= 5:
                insert_feedback(
                    client,
                    {
                        "sent_id": sent_id,
                        "channel": "telegram",
                        "rating": rating,
                        "tone_tag": "just_right" if rating >= 4 else "too_soft",
                        "note": None,
                    },
                )
                _safe_answer_callback(callback_id, text=f"Saved rating {rating}")
        return {"ok": True}

    message = update.get("message")
    if message:
        text = str(message.get("text", "")).strip()
        if text.lower().startswith("/mood"):
            parts = text.split()
            if len(parts) >= 2 and parts[1].isdigit():
                score = int(parts[1])
                if 1 <= score <= 5:
                    insert_mood_log(client, {"score": score, "note": "telegram /mood"})
                    _safe_send_message(f"Mood {score}/5 recorded.")
                    return {"ok": True}
            _safe_send_message("Usage: /mood <1-5>")
            return {"ok": True}
        if text.lower().startswith("/start"):
            _safe_send_message("Bot is active. Use /mood <1-5> to log mood.")
            return {"ok": True}

    return {"ok": True}

