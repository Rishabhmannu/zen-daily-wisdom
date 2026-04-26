#!/usr/bin/env python3
"""
One-time Gmail OAuth (Desktop) flow: prints a refresh token for GMAIL_REFRESH_TOKEN in .env.

Prerequisites:
- Gmail API enabled; OAuth consent screen configured; you are a test user if the app is in Testing.
- secrets/gmail_oauth_client.json (or GMAIL_OAUTH_SECRETS_FILE) present.
- Add the same scopes in Cloud Console (OAuth consent → Scopes) that you use below.

Run from the project root:
  .venv/bin/python scripts/oauth_setup_gmail.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow

# Must match what you add under OAuth consent → Scopes. Narrow: send only.
# Add https://www.googleapis.com/auth/gmail.readonly (etc.) if your app needs it.
GMAIL_API_SCOPES: list[str] = [
    "https://www.googleapis.com/auth/gmail.send",
]


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main() -> None:
    root = _project_root()
    load_dotenv(root / ".env")
    rel = os.environ.get("GMAIL_OAUTH_SECRETS_FILE", "secrets/gmail_oauth_client.json")
    secrets_file = (root / rel).resolve()
    if not secrets_file.is_file():
        print(f"Expected OAuth client file at: {secrets_file}", file=sys.stderr)
        print("Set GMAIL_OAUTH_SECRETS_FILE in .env or add the JSON from Google Cloud.", file=sys.stderr)
        raise SystemExit(1)

    flow = InstalledAppFlow.from_client_secrets_file(
        str(secrets_file), scopes=GMAIL_API_SCOPES
    )
    # access_type + prompt so Google returns a refresh token (re-consent if you ran before without it).
    creds = flow.run_local_server(
        port=0,
        open_browser=True,
        access_type="offline",
        prompt="consent",
    )
    if not creds.refresh_token:
        print(
            "No refresh token received. Revoke the app's access at "
            "https://myaccount.google.com/permissions and run this script again, "
            "or ensure prompt=consent is in effect.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    print()
    print("Add (or update) these in .env — do not commit .env:")
    print()
    print(f"GMAIL_REFRESH_TOKEN={creds.refresh_token}")
    print()
    print("Also set GMAIL_FROM_ADDRESS= to the Gmail you signed in with (e.g. you@gmail.com).")
    print()


if __name__ == "__main__":
    main()
