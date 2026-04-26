from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from zen_backend.config import settings
from zen_backend.db.client import get_supabase_client
from zen_backend.db.queries import get_sent_history_by_id, insert_feedback
from zen_backend.security.hmac_sig import verify_text

router = APIRouter(tags=["feedback"])


@router.get("/feedback")
def feedback(
    sent_id: str = Query(...),
    rating: int = Query(..., ge=1, le=5),
    channel: str = Query(default="email"),
    sig: str = Query(default=""),
) -> RedirectResponse:
    if not settings.feedback_link_secret:
        raise HTTPException(status_code=500, detail="FEEDBACK_LINK_SECRET not configured.")

    base = f"{sent_id}|{rating}|{channel}"
    if not sig or not verify_text(settings.feedback_link_secret, base, sig):
        raise HTTPException(status_code=401, detail="Invalid feedback signature.")

    client = get_supabase_client()
    sent = get_sent_history_by_id(client, sent_id)
    if not sent:
        raise HTTPException(status_code=404, detail="sent_id not found.")

    insert_feedback(
        client,
        {
            "sent_id": sent_id,
            "channel": channel,
            "rating": rating,
            "tone_tag": "just_right" if rating >= 4 else "too_soft",
            "note": None,
        },
    )

    target = f"{settings.public_base_url.rstrip('/')}/feedback/thanks?sent_id={sent_id}&rating={rating}"
    return RedirectResponse(url=target, status_code=302)

