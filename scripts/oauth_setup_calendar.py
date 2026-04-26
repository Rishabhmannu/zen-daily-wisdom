#!/usr/bin/env python3
"""
One-time Google Calendar OAuth (Desktop) flow.

Prints `GCAL_REFRESH_TOKEN` and helps choose/create `GCAL_CALENDAR_ID`.

Run from project root:
  .venv/bin/python scripts/oauth_setup_calendar.py
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

GCAL_API_SCOPES: list[str] = [
    "https://www.googleapis.com/auth/calendar",
]


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one-time Calendar OAuth and print env values."
    )
    parser.add_argument(
        "--create-calendar-name",
        default="",
        help=(
            "Optional: create a new secondary calendar with this name and print "
            "its id as GCAL_CALENDAR_ID."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    root = _project_root()
    load_dotenv(root / ".env")

    rel = os.environ.get("GCAL_OAUTH_SECRETS_FILE") or os.environ.get(
        "GMAIL_OAUTH_SECRETS_FILE", "secrets/gmail_oauth_client.json"
    )
    secrets_file = (root / rel).resolve()
    if not secrets_file.is_file():
        print(f"Expected OAuth client file at: {secrets_file}", file=sys.stderr)
        print(
            "Set GCAL_OAUTH_SECRETS_FILE (or GMAIL_OAUTH_SECRETS_FILE) in .env.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    flow = InstalledAppFlow.from_client_secrets_file(
        str(secrets_file), scopes=GCAL_API_SCOPES
    )
    creds = flow.run_local_server(
        port=0,
        open_browser=True,
        access_type="offline",
        prompt="consent",
    )
    if not creds.refresh_token:
        print(
            "No refresh token received. Revoke app access at "
            "https://myaccount.google.com/permissions and run again.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    service = build("calendar", "v3", credentials=creds)

    created_calendar_id = ""
    if args.create_calendar_name:
        body = {
            "summary": args.create_calendar_name,
            "description": "Calendar created by oauth_setup_calendar.py",
            "timeZone": "Asia/Kolkata",
        }
        created = service.calendars().insert(body=body).execute()
        created_calendar_id = created["id"]

    calendar_list = (
        service.calendarList().list(maxResults=20, showHidden=False).execute()
    )
    items = calendar_list.get("items", [])

    print()
    print("Add (or update) these in .env — do not commit .env:")
    print()
    print(f"GCAL_REFRESH_TOKEN={creds.refresh_token}")
    print()
    if created_calendar_id:
        print(f"GCAL_CALENDAR_ID={created_calendar_id}")
        print()
    print("Available calendars (pick one id for GCAL_CALENDAR_ID):")
    for item in items:
        print(f"- {item.get('summary', '(no name)')}: {item.get('id', '')}")
    print()
    print(
        "Tip: run with --create-calendar-name \"Daily Theme\" "
        "to create one and auto-print its id."
    )
    print()


if __name__ == "__main__":
    main()
