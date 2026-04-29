"""HMAC-signed tokens for the email-driven public check-in flow.

The token grants short-lived, single-purpose access to one specific check-in
window/date for the personal user. Possession of the email it was sent to is
the implicit identity proof; the HMAC makes the link unforgeable. This is the
same trust model used for daily-email rating links (`feedback_link_secret`).

Token format: `<urlsafe_b64(payload_json)>.<hex_sha256_hmac>` where payload is
`{"window": str, "date": "YYYY-MM-DD", "exp": int(unix_seconds)}`.
"""

from __future__ import annotations

import base64
import json
import time
from datetime import date
from typing import Literal

from zen_backend.security.hmac_sig import sign_text, verify_text

Window = Literal["morning", "midday", "evening"]

DEFAULT_TTL_SECONDS = 60 * 60 * 36  # 36 hours — covers same-day + grace


class CheckinTokenError(ValueError):
    """Raised when a check-in token is malformed, tampered, or expired."""


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def issue_checkin_token(
    secret: str,
    window: str,
    on_date: date,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> str:
    if not secret:
        raise CheckinTokenError("Check-in link secret is not configured.")
    payload = {
        "window": window,
        "date": on_date.isoformat(),
        "exp": int(time.time()) + ttl_seconds,
    }
    raw = _b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    sig = sign_text(secret, raw)
    return f"{raw}.{sig}"


def verify_checkin_token(secret: str, token: str) -> dict:
    if not secret:
        raise CheckinTokenError("Check-in link secret is not configured.")
    if not token or "." not in token:
        raise CheckinTokenError("Invalid token format.")
    raw, _, sig = token.partition(".")
    if not raw or not sig:
        raise CheckinTokenError("Invalid token format.")
    if not verify_text(secret, raw, sig):
        raise CheckinTokenError("Invalid token signature.")
    try:
        payload = json.loads(_b64decode(raw).decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise CheckinTokenError("Token payload is corrupted.") from exc
    if not isinstance(payload, dict):
        raise CheckinTokenError("Token payload is not an object.")
    expiry = payload.get("exp")
    if not isinstance(expiry, (int, float)) or int(expiry) < int(time.time()):
        raise CheckinTokenError("Token has expired. Request a new check-in link.")
    if payload.get("window") not in {"morning", "midday", "evening"}:
        raise CheckinTokenError("Token window is invalid.")
    if not isinstance(payload.get("date"), str):
        raise CheckinTokenError("Token date is invalid.")
    return payload
