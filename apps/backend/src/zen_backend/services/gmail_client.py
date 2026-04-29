from __future__ import annotations

import base64
import logging
from email.mime.text import MIMEText

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from zen_backend.config import settings

logger = logging.getLogger(__name__)

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def _gmail_credentials() -> Credentials:
    if not (settings.gmail_client_id and settings.gmail_client_secret and settings.gmail_refresh_token):
        raise RuntimeError(
            "Gmail is not configured. Set GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN."
        )
    return Credentials(
        token=None,
        refresh_token=settings.gmail_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.gmail_client_id,
        client_secret=settings.gmail_client_secret,
        scopes=GMAIL_SCOPES,
    )


def send_email(subject: str, html_body: str, to_address: str) -> dict:
    credentials = _gmail_credentials()
    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)

    message = MIMEText(html_body, "html", "utf-8")
    message["to"] = to_address
    message["from"] = settings.gmail_from_address or to_address
    message["subject"] = subject

    encoded = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    response = service.users().messages().send(userId="me", body={"raw": encoded}).execute()
    return response


def send_email_to_many(subject: str, html_body: str, to_addresses: list[str]) -> list[dict]:
    """Send the same email to a list of recipients, tolerating per-recipient
    failures. Returns a per-recipient delivery report so a single bad address
    does not crash the whole batch.
    """
    responses: list[dict] = []
    for to_address in to_addresses:
        try:
            response = send_email(subject, html_body, to_address)
            responses.append(
                {
                    "recipient": to_address,
                    "status": "ok",
                    "message_id": response.get("id"),
                }
            )
        except Exception as exc:  # noqa: BLE001 — we want to surface any error per-recipient
            logger.warning("Failed to send email to %s: %s", to_address, exc)
            responses.append(
                {
                    "recipient": to_address,
                    "status": "error",
                    "error": str(exc),
                }
            )
    return responses

