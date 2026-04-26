from __future__ import annotations

import requests

from zen_backend.config import settings


def _base_url() -> str:
    if not settings.telegram_bot_token:
        raise RuntimeError("Telegram is not configured. Set TELEGRAM_BOT_TOKEN.")
    return f"https://api.telegram.org/bot{settings.telegram_bot_token}"


def _post(method: str, payload: dict) -> dict:
    response = requests.post(f"{_base_url()}/{method}", json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def send_message(text: str, sent_id: str | None = None) -> dict:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        raise RuntimeError("Telegram is not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.")

    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    if sent_id:
        payload["reply_markup"] = {
            "inline_keyboard": [
                [
                    {"text": "1", "callback_data": f"rate:{sent_id}:1"},
                    {"text": "2", "callback_data": f"rate:{sent_id}:2"},
                    {"text": "3", "callback_data": f"rate:{sent_id}:3"},
                    {"text": "4", "callback_data": f"rate:{sent_id}:4"},
                    {"text": "5", "callback_data": f"rate:{sent_id}:5"},
                ]
            ]
        }
    return _post("sendMessage", payload)


def answer_callback_query(callback_query_id: str, text: str = "Saved") -> dict:
    return _post("answerCallbackQuery", {"callback_query_id": callback_query_id, "text": text})


def set_webhook(webhook_url: str, secret_token: str) -> dict:
    payload = {"url": webhook_url, "secret_token": secret_token}
    return _post("setWebhook", payload)

