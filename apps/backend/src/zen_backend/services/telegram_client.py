from __future__ import annotations

import json

import requests

from zen_backend.config import settings
from zen_backend.services.telegram_card import build_telegram_card_image


def _base_url() -> str:
    if not settings.telegram_bot_token:
        raise RuntimeError("Telegram is not configured. Set TELEGRAM_BOT_TOKEN.")
    return f"https://api.telegram.org/bot{settings.telegram_bot_token}"


def _post(method: str, payload: dict) -> dict:
    response = requests.post(f"{_base_url()}/{method}", json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def _post_multipart(method: str, data: dict, files: dict) -> dict:
    response = requests.post(f"{_base_url()}/{method}", data=data, files=files, timeout=30)
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


def send_card_message(
    thought_of_day: str,
    theme_of_day: str,
    citation: str,
    calendar_add_link: str,
    sent_id: str | None = None,
) -> dict:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        raise RuntimeError("Telegram is not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.")

    caption = (
        f"Theme: {theme_of_day}\n\n"
        f"Source: {citation}\n"
        f"Add to Calendar: {calendar_add_link}"
    )
    reply_markup = None
    if sent_id:
        reply_markup = {
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
    payload = {
        "chat_id": settings.telegram_chat_id,
        "caption": caption,
        "disable_notification": False,
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)

    image_bytes = build_telegram_card_image(thought_of_day=thought_of_day, theme_of_day=theme_of_day)
    files = {"photo": ("zen-card.png", image_bytes, "image/png")}
    return _post_multipart("sendPhoto", payload, files)


def send_checkin_reminder(window: str, checkin_url: str) -> dict:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        raise RuntimeError("Telegram is not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.")
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": (
            f"🌿 {window.title()} check-in\n"
            "60 seconds. 8 quick questions (1-5).\n"
            "We use this to personalize your next message."
        ),
        "reply_markup": {
            "inline_keyboard": [[{"text": "Open Check-in", "url": checkin_url}]]
        },
        "disable_web_page_preview": True,
    }
    return _post("sendMessage", payload)


def answer_callback_query(callback_query_id: str, text: str = "Saved") -> dict:
    return _post("answerCallbackQuery", {"callback_query_id": callback_query_id, "text": text})


def set_webhook(webhook_url: str, secret_token: str) -> dict:
    payload = {"url": webhook_url, "secret_token": secret_token}
    return _post("setWebhook", payload)

