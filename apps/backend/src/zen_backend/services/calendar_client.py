from __future__ import annotations

from datetime import date, timedelta

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from zen_backend.config import settings

GCAL_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def _calendar_credentials() -> Credentials:
    if not (settings.gcal_client_id and settings.gcal_client_secret and settings.gcal_refresh_token):
        raise RuntimeError(
            "Calendar is not configured. Set GCAL_CLIENT_ID, GCAL_CLIENT_SECRET, GCAL_REFRESH_TOKEN."
        )
    return Credentials(
        token=None,
        refresh_token=settings.gcal_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.gcal_client_id,
        client_secret=settings.gcal_client_secret,
        scopes=GCAL_SCOPES,
    )


def upsert_theme_of_day_event(run_date: date, theme_of_day: str, description: str) -> dict:
    credentials = _calendar_credentials()
    service = build("calendar", "v3", credentials=credentials, cache_discovery=False)

    event_id = f"zen-{run_date.isoformat()}".replace("-", "")
    body = {
        "summary": f"Theme of the Day: {theme_of_day}",
        "description": description,
        "start": {"date": run_date.isoformat()},
        "end": {"date": (run_date + timedelta(days=1)).isoformat()},
        "transparency": "transparent",
    }

    try:
        return (
            service.events()
            .update(calendarId=settings.gcal_calendar_id, eventId=event_id, body=body)
            .execute()
        )
    except HttpError as exc:
        status = getattr(getattr(exc, "resp", None), "status", None)
        if status == 404:
            return (
                service.events()
                .insert(calendarId=settings.gcal_calendar_id, body={"id": event_id, **body})
                .execute()
            )
        raise

