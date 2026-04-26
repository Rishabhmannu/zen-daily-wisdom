#!/usr/bin/env python3
"""Register Telegram webhook URL using configured bot token + secret."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

from zen_backend.config import settings
from zen_backend.services.telegram_client import set_webhook

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    load_dotenv(ROOT / ".env")
    base = settings.public_base_url.rstrip("/")
    if not base.startswith("https://"):
        raise SystemExit("NEXT_PUBLIC_BACKEND_URL must be https for Telegram webhook registration.")
    if not settings.telegram_webhook_secret:
        raise SystemExit("Set TELEGRAM_WEBHOOK_SECRET before registering webhook.")
    response = set_webhook(f"{base}/telegram/webhook", settings.telegram_webhook_secret)
    print(response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

