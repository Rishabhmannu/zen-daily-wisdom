"""HMAC-signed redirect tokens for the Add-to-Calendar deep link.

Goal: don't ship a 250-character Google Calendar URL into Telegram/Gmail
(iOS Telegram in particular shows the full URL in a confirmation dialog,
which looks alarming). Instead, ship a short backend URL like
`https://<backend>/calendar/add?sent_id=<uuid>&sig=<hmac>` that 302s to
the real Google Calendar render URL, built on the fly from the
`sent_history` row.

Same trust model as feedback links: a signed query is the auth. We
namespace this signature with the literal `calendar:` prefix so a
feedback signature can never be replayed as a calendar signature.
"""

from __future__ import annotations

from zen_backend.security.hmac_sig import sign_text, verify_text

_NAMESPACE = "calendar"


def sign_calendar_link(secret: str, sent_id: str) -> str:
    if not secret:
        raise ValueError("Calendar link secret is not configured.")
    return sign_text(secret, f"{_NAMESPACE}:{sent_id}")


def verify_calendar_link(secret: str, sent_id: str, signature: str) -> bool:
    if not secret or not signature:
        return False
    return verify_text(secret, f"{_NAMESPACE}:{sent_id}", signature)
