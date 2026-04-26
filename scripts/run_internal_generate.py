#!/usr/bin/env python3
"""Locally trigger backend /internal/generate with correct HMAC signature."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from datetime import date

import requests
from dotenv import load_dotenv


def main() -> int:
    parser = argparse.ArgumentParser(description="Trigger /internal/generate")
    parser.add_argument("--date", dest="run_date", default=None, help="YYYY-MM-DD (defaults to today)")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--backend-url", default=None)
    args = parser.parse_args()

    load_dotenv()
    backend_url = (args.backend_url or os.getenv("NEXT_PUBLIC_BACKEND_URL") or "http://localhost:8000").rstrip("/")
    secret = os.getenv("INTERNAL_HMAC_SECRET", "").strip()
    if not secret:
        raise SystemExit("INTERNAL_HMAC_SECRET is not set.")

    payload = {
        "date": args.run_date or date.today().isoformat(),
        "force": args.force,
    }
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

    response = requests.post(
        f"{backend_url}/internal/generate",
        data=body,
        headers={"Content-Type": "application/json", "X-Internal-Signature": sig},
        timeout=120,
    )
    print(f"status={response.status_code}")
    print(response.text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

