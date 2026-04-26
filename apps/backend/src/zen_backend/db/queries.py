from __future__ import annotations

from datetime import date
from typing import Any

from supabase import Client


def get_sent_history_by_date(client: Client, run_date: date) -> dict[str, Any] | None:
    result = (
        client.table("sent_history")
        .select("*")
        .eq("sent_date", run_date.isoformat())
        .limit(1)
        .execute()
    )
    rows = result.data or []
    return rows[0] if rows else None


def fetch_candidate_passages(
    client: Client,
    tradition: str | None = None,
    source_tier: str = "gold",
    limit: int = 20,
) -> list[dict[str, Any]]:
    query = client.table("passages").select(
        "id, tradition, source, citation, text, theme_tags, tone, length_bucket, source_tier"
    )
    if tradition:
        query = query.eq("tradition", tradition)
    if source_tier:
        query = query.eq("source_tier", source_tier)
    result = query.limit(limit).execute()
    return result.data or []


def insert_sent_history(client: Client, payload: dict[str, Any]) -> dict[str, Any]:
    result = client.table("sent_history").insert(payload).execute()
    rows = result.data or []
    return rows[0] if rows else {}


def update_sent_history(client: Client, sent_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    result = client.table("sent_history").update(payload).eq("id", sent_id).execute()
    rows = result.data or []
    return rows[0] if rows else {}


def insert_feedback(client: Client, payload: dict[str, Any]) -> dict[str, Any]:
    result = client.table("feedback").insert(payload).execute()
    rows = result.data or []
    return rows[0] if rows else {}


def get_sent_history_by_id(client: Client, sent_id: str) -> dict[str, Any] | None:
    result = client.table("sent_history").select("*").eq("id", sent_id).limit(1).execute()
    rows = result.data or []
    return rows[0] if rows else None


def get_latest_sent_history(client: Client, limit: int = 1) -> list[dict[str, Any]]:
    result = client.table("sent_history").select("*").order("sent_at", desc=True).limit(limit).execute()
    return result.data or []


def get_recent_sent_history(client: Client, limit: int = 30) -> list[dict[str, Any]]:
    result = (
        client.table("sent_history")
        .select("*")
        .order("sent_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


def get_feedback_for_sent_ids(client: Client, sent_ids: list[str]) -> list[dict[str, Any]]:
    if not sent_ids:
        return []
    result = client.table("feedback").select("*").in_("sent_id", sent_ids).execute()
    return result.data or []


def get_bandit_state(client: Client, limit: int = 200) -> list[dict[str, Any]]:
    result = client.table("bandit_state").select("*").order("last_updated", desc=True).limit(limit).execute()
    return result.data or []


def insert_mood_log(client: Client, payload: dict[str, Any]) -> dict[str, Any]:
    result = client.table("mood_log").insert(payload).execute()
    rows = result.data or []
    return rows[0] if rows else {}


def get_active_prompt(client: Client, kind: str) -> str | None:
    result = (
        client.table("prompt_versions")
        .select("body")
        .eq("kind", kind)
        .eq("is_active", True)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = result.data or []
    if not rows:
        return None
    return rows[0].get("body")


def insert_checkin_response(client: Client, payload: dict[str, Any]) -> dict[str, Any]:
    result = client.table("checkin_responses").insert(payload).execute()
    rows = result.data or []
    return rows[0] if rows else {}


def get_recent_checkin_responses(client: Client, limit: int = 90) -> list[dict[str, Any]]:
    result = (
        client.table("checkin_responses")
        .select("*")
        .order("submitted_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []

