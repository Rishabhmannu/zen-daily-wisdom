from __future__ import annotations

import hashlib
import hmac


def sign_payload(secret: str, payload: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def verify_payload(secret: str, payload: bytes, signature: str) -> bool:
    expected = sign_payload(secret, payload)
    return hmac.compare_digest(expected, signature)


def sign_text(secret: str, text: str) -> str:
    return sign_payload(secret, text.encode("utf-8"))


def verify_text(secret: str, text: str, signature: str) -> bool:
    return verify_payload(secret, text.encode("utf-8"), signature)

