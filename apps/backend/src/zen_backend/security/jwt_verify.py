from __future__ import annotations

from typing import Any

import requests
from fastapi import Header, HTTPException

from zen_backend.config import settings


def _get_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header.")
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization scheme.")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token.")
    return token


def verify_owner_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    token = _get_bearer_token(authorization)
    supabase_url = settings.supabase_url.strip().strip('"').strip("'")
    if not supabase_url or not settings.supabase_anon_key:
        raise HTTPException(status_code=500, detail="Supabase auth config missing.")

    response = requests.get(
        f"{supabase_url}/auth/v1/user",
        headers={
            "apikey": settings.supabase_anon_key,
            "Authorization": f"Bearer {token}",
        },
        timeout=20,
    )
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid auth token.")

    user = response.json()
    email = str(user.get("email", "")).lower().strip()
    if not email:
        raise HTTPException(status_code=403, detail="Authenticated user has no email.")

    allowed = settings.allowed_emails
    if allowed and email not in allowed:
        raise HTTPException(status_code=403, detail="Email is not allowlisted.")

    owner_uid = settings.owner_uid.strip()
    if owner_uid and str(user.get("id")) != owner_uid:
        raise HTTPException(status_code=403, detail="User is not owner.")
    return user

