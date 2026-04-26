from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from zen_backend.config import settings
from zen_backend.security.hmac_sig import verify_payload
from zen_backend.services.generator import run_daily_generation

router = APIRouter(prefix="/internal", tags=["internal"])


class GenerateRequest(BaseModel):
    date: str | None = None
    force: bool = False


def _require_signature(raw_body: bytes, signature: str | None) -> None:
    if not settings.internal_hmac_secret:
        raise HTTPException(status_code=500, detail="INTERNAL_HMAC_SECRET not configured")
    if not signature or not verify_payload(settings.internal_hmac_secret, raw_body, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")


@router.post("/generate")
def generate(
    payload: GenerateRequest,
    x_internal_signature: str | None = Header(default=None, alias="X-Internal-Signature"),
) -> dict[str, object]:
    raw = json.dumps(payload.model_dump(mode="json"), separators=(",", ":"), sort_keys=True).encode("utf-8")
    _require_signature(raw, x_internal_signature)

    if payload.date:
        try:
            run_date = date.fromisoformat(payload.date)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD.") from exc
    else:
        run_date = date.today()
    return run_daily_generation(run_date=run_date, force=payload.force)

