from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from zen_backend.db.client import get_supabase_client
from zen_backend.db.queries import (
    get_bandit_state,
    get_feedback_for_sent_ids,
    get_latest_sent_history,
    get_recent_sent_history,
)
from zen_backend.security.jwt_verify import verify_owner_user
from zen_backend.services.generator import run_daily_generation

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class SendNowRequest(BaseModel):
    force: bool = True


def _with_style_key(row: dict | None) -> dict | None:
    if not row:
        return row
    item = dict(row)
    trace = item.get("retrieval_trace") or {}
    if isinstance(trace, dict):
        item["style_key"] = trace.get("style_key")
    else:
        item["style_key"] = None
    return item


@router.get("/today")
def today(_: dict = Depends(verify_owner_user)) -> dict:
    client = get_supabase_client()
    rows = get_latest_sent_history(client, limit=1)
    return {"data": _with_style_key(rows[0]) if rows else None}


@router.get("/history")
def history(limit: int = Query(default=30, ge=1, le=200), _: dict = Depends(verify_owner_user)) -> dict:
    client = get_supabase_client()
    sent_rows = get_recent_sent_history(client, limit=limit)
    sent_ids = [str(r.get("id")) for r in sent_rows if r.get("id")]
    feedback_rows = get_feedback_for_sent_ids(client, sent_ids)
    feedback_by_sent: dict[str, list[dict]] = {}
    for row in feedback_rows:
        sid = str(row.get("sent_id"))
        feedback_by_sent.setdefault(sid, []).append(row)

    enriched = []
    for row in sent_rows:
        sid = str(row.get("id"))
        item = _with_style_key(row) or {}
        item["feedback"] = feedback_by_sent.get(sid, [])
        enriched.append(item)
    return {"data": enriched}


@router.get("/bandit")
def bandit(limit: int = Query(default=200, ge=1, le=500), _: dict = Depends(verify_owner_user)) -> dict:
    client = get_supabase_client()
    rows = get_bandit_state(client, limit=limit)
    for row in rows:
        alpha = float(row.get("alpha", 1.0))
        beta = float(row.get("beta", 1.0))
        row["expected_value"] = alpha / (alpha + beta) if (alpha + beta) else 0.0
    rows.sort(key=lambda r: float(r.get("expected_value", 0.0)), reverse=True)
    return {"data": rows}


@router.post("/send-now")
def send_now(payload: SendNowRequest, _: dict = Depends(verify_owner_user)) -> dict:
    # Personal single-user project endpoint; intentionally simple.
    return run_daily_generation(run_date=date.today(), force=payload.force)

