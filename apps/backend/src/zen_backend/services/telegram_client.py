from __future__ import annotations

import html

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


def _rating_keyboard(sent_id: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "1 ★", "callback_data": f"rate:{sent_id}:1"},
                {"text": "2 ★", "callback_data": f"rate:{sent_id}:2"},
                {"text": "3 ★", "callback_data": f"rate:{sent_id}:3"},
                {"text": "4 ★", "callback_data": f"rate:{sent_id}:4"},
                {"text": "5 ★", "callback_data": f"rate:{sent_id}:5"},
            ]
        ]
    }


def send_message(text: str, sent_id: str | None = None) -> dict:
    """Send a plain-text Telegram message (no parse_mode)."""
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        raise RuntimeError("Telegram is not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.")

    payload: dict = {
        "chat_id": settings.telegram_chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    if sent_id:
        payload["reply_markup"] = _rating_keyboard(sent_id)
    return _post("sendMessage", payload)


def send_html_message(html_text: str, sent_id: str | None = None) -> dict:
    """Send an HTML-formatted Telegram message.

    Telegram's HTML parse_mode is the most readable + lowest-risk way to do
    typography in a chat message; only `<`, `>`, and `&` need escaping in
    the body (use `escape_html_for_telegram`). Compared to MarkdownV2 it
    requires far less defensive escaping while supporting <b>, <i>, <u>,
    <s>, <code>, <pre>, and <a href="">.
    """
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        raise RuntimeError("Telegram is not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.")

    payload: dict = {
        "chat_id": settings.telegram_chat_id,
        "text": html_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if sent_id:
        payload["reply_markup"] = _rating_keyboard(sent_id)
    return _post("sendMessage", payload)


def escape_html_for_telegram(text: str) -> str:
    """Escape only the three characters Telegram's HTML parse_mode requires."""
    return html.escape(text, quote=False)


def build_daily_html(
    *,
    thought_of_day: str,
    theme_of_day: str,
    citation: str,
    calendar_add_link: str,
) -> str:
    """Compose the daily reflection message in Telegram-flavoured HTML.

    Layout intentionally mirrors the email's literary register: an eyebrow
    line, a theme, the thought as italic body, a citation in bold, and a
    single calendar link. Emoji ornaments give it a tiny visual identity
    without leaving the chat font.
    """
    safe_thought = escape_html_for_telegram(thought_of_day.strip())
    safe_theme = escape_html_for_telegram(theme_of_day.strip())
    safe_citation = escape_html_for_telegram(citation.strip())
    safe_link = escape_html_for_telegram(calendar_add_link.strip())
    return (
        "🌿 <b>Zen Daily Wisdom</b>\n"
        f"<i>Theme: {safe_theme}</i>\n"
        "\n"
        f"<i>{safe_thought}</i>\n"
        "\n"
        f"— <b>{safe_citation}</b>\n"
        "\n"
        f"🪷 <a href=\"{safe_link}\">Add to Calendar</a>"
    )


def send_daily_text(
    *,
    thought_of_day: str,
    theme_of_day: str,
    citation: str,
    calendar_add_link: str,
    sent_id: str | None = None,
) -> dict:
    """Send the daily reflection as a typographically clean text message
    with optional inline 1-5 rating buttons. Replaces the PIL-rendered
    image card (see ADR-016)."""
    body = build_daily_html(
        thought_of_day=thought_of_day,
        theme_of_day=theme_of_day,
        citation=citation,
        calendar_add_link=calendar_add_link,
    )
    return send_html_message(body, sent_id=sent_id)


_CHECKIN_QUESTION_COUNTS: dict[str, int] = {"morning": 7, "midday": 6, "evening": 7}


def send_checkin_reminder(window: str, checkin_url: str) -> dict:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        raise RuntimeError("Telegram is not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.")
    n = _CHECKIN_QUESTION_COUNTS.get(window, 7)
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": (
            f"🌿 {window.title()} check-in\n"
            f"60 seconds. {n} quick questions (1–5).\n"
            "Your answers shape tomorrow's reflection."
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

