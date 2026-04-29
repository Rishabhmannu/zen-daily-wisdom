from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote
import re

from jinja2 import Environment, FileSystemLoader, select_autoescape

from zen_backend.config import settings
from zen_backend.db.client import get_supabase_client
from zen_backend.db.queries import (
    fetch_candidate_passages,
    get_sent_history_by_date,
    get_active_prompt,
    get_recent_checkin_responses,
    insert_sent_history,
    update_sent_history,
)
from zen_backend.services.checkin_context import build_checkin_summary
from zen_backend.services.gemini_client import generate_reflection
from zen_backend.services.gmail_client import send_email_to_many
from zen_backend.services.calendar_client import upsert_theme_of_day_event
from zen_backend.services.retrieval import choose_passage, fetch_ranked_passages
from zen_backend.services.telegram_client import send_daily_text
from zen_backend.security.calendar_link import sign_calendar_link
from zen_backend.security.hmac_sig import sign_text

_TEMPLATE_ENV = Environment(
    loader=FileSystemLoader(str(Path(__file__).resolve().parents[1] / "templates")),
    autoescape=select_autoescape(["html", "xml"]),
)


_FORBIDDEN_PHRASES = (
    "you've got this",
    "believe in yourself",
    "trust the journey",
    "manifest",
    "hustle",
    "grind",
)

_FORBIDDEN_OPENERS = (
    "the passage",
    "this passage",
    "the text",
    "this text",
    "source:",
)

_STYLE_ROTATION: tuple[tuple[str, str], ...] = (
    (
        "poetic_minimal",
        "Style A (poetic-minimal): Use gentle imagery and minimal words. Keep it lyrical but grounded.",
    ),
    (
        "practical_grounded",
        "Style B (practical-grounded): Keep it practical and concrete. End with one tiny actionable suggestion.",
    ),
    (
        "mixed_poetic_action",
        "Style C (mixed): Start with a poetic image, then give one practical next step in plain language.",
    ),
    (
        "nature_seasons",
        "Style D (nature and seasons): Use nature/season imagery (light, wind, rain, dawn, evening, trees, sky) "
        "to frame the thought while staying relevant to daily life.",
    ),
)


def _fallback_reflection(passage_text: str) -> str:
    excerpt = passage_text.strip().split("\n")[0][:240]
    return (
        "Pause for one steady breath before the day pulls you in every direction.\n"
        f"{excerpt[:120]}. Let this line anchor one honest hour of focused work."
    )


def _select_daily_style(run_date: date) -> tuple[str, str]:
    idx = run_date.toordinal() % len(_STYLE_ROTATION)
    return _STYLE_ROTATION[idx]


def _style_retrieval_preferences(style_key: str) -> tuple[str, list[str], bool]:
    base = "focus on present, anxiety about future, calm and practical motivation for studies and career uncertainty"
    if style_key == "nature_seasons":
        return (
            f"{base}, nature rhythms, seasons, dawn light, rain, trees, sky, grounded calm",
            ["nature", "change", "presence"],
            True,
        )
    if style_key == "practical_grounded":
        return (f"{base}, practical next step, discipline, work, clarity", ["work", "discipline", "presence"], False)
    if style_key == "mixed_poetic_action":
        return (f"{base}, poetic image plus concrete action", ["presence", "courage"], False)
    return (f"{base}, gentle poetic thought", ["presence"], False)


def _adapt_preferences_with_checkin(
    query: str,
    required_tags: list[str],
    checkin_context_line: str,
    mood_avg: float | None,
    challenge_avg: float | None,
) -> tuple[str, list[str]]:
    updated_query = f"{query}; check-in context: {checkin_context_line}"
    updated_tags = list(required_tags)

    # mood_avg is now expressed on a 0-100 scale (CheckinSummary.mood_avg).
    # Previous thresholds 2.6 and 4.0 on the legacy 1-5 scale map to:
    #   (2.6 - 1) / 4 * 100 = 40   (low-mood threshold)
    #   (4.0 - 1) / 4 * 100 = 75   (high-mood threshold)
    if mood_avg is not None and mood_avg <= 40:
        updated_query += "; support overwhelm, reduce pressure, gentler framing"
        updated_tags.extend(["rest", "patience"])
    elif mood_avg is not None and mood_avg >= 75:
        updated_query += "; sustain momentum with grounded discipline"
        updated_tags.extend(["discipline", "work"])

    if challenge_avg is not None and challenge_avg >= 3.8:
        updated_query += "; prioritize clarity under heavy day-load"
        updated_tags.extend(["presence", "courage"])

    # Preserve order while removing duplicates.
    deduped_tags = list(dict.fromkeys(updated_tags))
    return updated_query, deduped_tags


def _build_feedback_link(sent_id: str, rating: int, channel: str) -> str:
    base = f"{sent_id}|{rating}|{channel}"
    sig = sign_text(settings.feedback_link_secret, base) if settings.feedback_link_secret else ""
    return (
        f"{settings.public_base_url.rstrip('/')}/feedback"
        f"?sent_id={sent_id}&rating={rating}&channel={channel}&sig={sig}"
    )


def _build_google_calendar_url(
    run_date: date, theme_of_day: str, reflection: str, citation: str
) -> str:
    """Direct Google Calendar `render?...` deep link (~250 chars). Used as
    a fallback when we can't sign a backend redirect (e.g. no sent_id yet,
    or the feedback link secret isn't set)."""
    start = run_date.strftime("%Y%m%d")
    end_date = (run_date + timedelta(days=1)).strftime("%Y%m%d")
    text = quote(f"Theme of the Day: {theme_of_day}")
    details = quote(f"{reflection}\n\nSource: {citation}")
    return (
        "https://calendar.google.com/calendar/render?action=TEMPLATE"
        f"&text={text}&dates={start}/{end_date}&details={details}"
    )


def _build_calendar_add_link(
    run_date: date,
    theme_of_day: str,
    reflection: str,
    citation: str,
    sent_id: str | None = None,
) -> str:
    """Return the URL we put in the daily email and Telegram message.

    Prefers the short signed redirect on our own backend
    (`/calendar/add?sent_id=...&sig=...`) so the iOS Telegram
    confirmation dialog (and any other URL preview) shows a short,
    recognizable address instead of a 250-character Google Calendar
    query string. Falls back to the inline Google URL when we don't yet
    have a sent_id or the link secret isn't configured.
    """
    if sent_id and settings.feedback_link_secret:
        sig = sign_calendar_link(settings.feedback_link_secret, sent_id)
        return (
            f"{settings.public_base_url.rstrip('/')}/calendar/add"
            f"?sent_id={sent_id}&sig={sig}"
        )
    return _build_google_calendar_url(run_date, theme_of_day, reflection, citation)


def _normalize_thought(reflection: str) -> str:
    compact = " ".join(reflection.replace("\n", " ").split())
    if not compact:
        return compact
    sentences: list[str] = []
    for sentence in compact.split(". "):
        clean = sentence.strip()
        if not clean:
            continue
        if not clean.endswith("."):
            clean += "."
        sentences.append(clean)
        if len(sentences) >= 2:
            break
    return " ".join(sentences) if sentences else compact


def _clean_tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-zA-Z']+", text.lower()) if len(t) > 2]


def _overlap_ratio(thought: str, passage_text: str) -> float:
    thought_tokens = _clean_tokens(thought)
    if not thought_tokens:
        return 1.0
    passage_set = set(_clean_tokens(passage_text))
    overlap = sum(1 for t in thought_tokens if t in passage_set)
    return overlap / len(thought_tokens)


def _quality_check(reflection: str, passage_text: str) -> tuple[bool, str]:
    thought = " ".join(reflection.split())
    words = thought.split()
    if len(words) < 20 or len(words) > 45:
        return False, "word_count"
    lowered = thought.lower()
    if any(lowered.startswith(prefix) for prefix in _FORBIDDEN_OPENERS):
        return False, "forbidden_opener"
    if any(token in lowered for token in (" passage ", " source ", " quote ", " citation ")):
        return False, "meta_reference"
    if any(phrase in lowered for phrase in _FORBIDDEN_PHRASES):
        return False, "forbidden_phrase"
    sentence_count = max(1, len([s for s in re.split(r"[.!?]+", thought) if s.strip()]))
    if sentence_count > 2:
        return False, "too_many_sentences"
    overlap = _overlap_ratio(thought, passage_text)
    if overlap < 0.12:
        return False, "weak_grounding"
    if overlap > 0.72:
        return False, "too_close_to_source"
    return True, "ok"


def _render_email_html(
    thought_of_day: str,
    theme_of_day: str,
    citation: str,
    calendar_add_link: str,
    sent_id: str | None = None,
) -> str:
    template = _TEMPLATE_ENV.get_template("email_zen.html.j2")
    links = {}
    if sent_id:
        links = {f"rating_{i}": _build_feedback_link(sent_id, i, "email") for i in range(1, 6)}
    return template.render(
        thought_of_day=thought_of_day,
        theme_of_day=theme_of_day,
        citation=citation,
        calendar_add_link=calendar_add_link,
        **links,
    )


def run_daily_generation(run_date: date, force: bool = False) -> dict[str, Any]:
    client = get_supabase_client()
    existing = get_sent_history_by_date(client, run_date)
    if existing and not force:
        return {"status": "already_sent", "sent_id": existing.get("id"), "run_date": run_date.isoformat()}
    existing_sent_id = str(existing.get("id")) if existing and existing.get("id") else None

    candidates = fetch_candidate_passages(client, source_tier="gold", limit=40)
    if not candidates:
        raise RuntimeError("No passages found. Seed the `passages` table first.")
    style_key, style_instruction = _select_daily_style(run_date)
    query, required_tags, prefer_season_words = _style_retrieval_preferences(style_key)
    recent_checkins = get_recent_checkin_responses(client, limit=30)
    checkin_summary = build_checkin_summary(recent_checkins, run_date)
    query, required_tags = _adapt_preferences_with_checkin(
        query=query,
        required_tags=required_tags,
        checkin_context_line=checkin_summary.context_line,
        mood_avg=checkin_summary.mood_avg,
        challenge_avg=checkin_summary.challenge_avg,
    )
    ranked = fetch_ranked_passages(
        query,
        source_tier="gold",
        required_tags=required_tags,
        prefer_season_words=prefer_season_words,
        limit=40,
    )
    if not ranked:
        # Fallback if embeddings are not backfilled yet.
        ranked = candidates
    passage = choose_passage(ranked)

    citation = f'{passage.get("source", "Unknown")} — {passage.get("citation", "Unknown citation")}'
    text = str(passage.get("text", "")).strip()
    if not text:
        raise RuntimeError("Selected passage has empty text.")
    system_prompt = get_active_prompt(client, "system") or (
        "You are a calm assistant. Write concise, grounded, motivational reflections in English."
    )
    reflection_prompt = get_active_prompt(client, "reflection") or "Write a short grounded thought."
    reflection_prompt_with_context = (
        f"{reflection_prompt}\n\n{style_instruction}\n\n"
        f"Same-day check-in context: {checkin_summary.context_line}"
    )
    try:
        reflection = generate_reflection(
            run_date=run_date,
            passage_text=text,
            citation=citation,
            system_prompt=system_prompt,
            reflection_prompt=reflection_prompt_with_context,
        )
        reflection = _normalize_thought(reflection)
        valid, reason = _quality_check(reflection, text)
        if not valid:
            retry_prompt = (
                f"{reflection_prompt_with_context}\n\n"
                f"Retry because previous output failed quality check: {reason}."
                " Keep it 25-55 words and grounded in source terms."
            )
            reflection = generate_reflection(
                run_date=run_date,
                passage_text=text,
                citation=citation,
                system_prompt=system_prompt,
                reflection_prompt=retry_prompt,
            )
            reflection = _normalize_thought(reflection)
            valid, _ = _quality_check(reflection, text)
            if not valid:
                raise RuntimeError("Reflection quality check failed after retry.")
    except Exception:
        # Fail soft for now so delivery still works while prompt/LLM wiring evolves.
        reflection = _fallback_reflection(text)

    theme_of_day_raw = str((passage.get("theme_tags") or ["present attention"])[0])
    theme_of_day = theme_of_day_raw.replace("_", " ").title()
    email_subject = f"Zen Daily Wisdom — {theme_of_day}"

    delivery = {"email": None, "telegram": None}
    channel_list: list[str] = []

    sent_payload = {
        "sent_date": run_date.isoformat(),
        "passage_ids": [str(passage["id"])],
        "arm_key": "bootstrap|calm|medium|gold",
        "arm_tradition": passage.get("tradition", "unknown"),
        "arm_tone": passage.get("tone", "gentle"),
        "arm_length": passage.get("length_bucket", "medium"),
        "arm_source_tier": passage.get("source_tier", "gold"),
        "theme_of_day": str(theme_of_day),
        "llm_output": reflection,
        "channels": channel_list,
        "retrieval_trace": {
            "strategy": "hashed_embedding_rank",
            "query": query,
            "candidate_count": len(ranked),
            "selected_passage_id": str(passage["id"]),
            "top_similarity": float(ranked[0].get("similarity", 0.0)) if ranked else None,
            "style_key": style_key,
            "checkin_context": checkin_summary.context_line,
            "checkin_mood_avg": checkin_summary.mood_avg,
            "checkin_challenge_avg": checkin_summary.challenge_avg,
            "required_tags": required_tags,
            "prefer_season_words": prefer_season_words,
        },
    }
    if existing_sent_id:
        saved = update_sent_history(client, existing_sent_id, sent_payload)
    else:
        saved = insert_sent_history(client, sent_payload)

    sent_id = saved.get("id")
    calendar_add_link = _build_calendar_add_link(
        run_date, theme_of_day, reflection, citation, sent_id=str(sent_id) if sent_id else None
    )
    email_html = _render_email_html(
        thought_of_day=reflection,
        theme_of_day=theme_of_day,
        citation=citation,
        calendar_add_link=calendar_add_link,
        sent_id=sent_id,
    )

    if (
        settings.gmail_from_address
        and settings.gmail_client_id
        and settings.gmail_client_secret
        and settings.gmail_refresh_token
    ):
        recipients = settings.gmail_to_addresses or [settings.gmail_from_address]
        email_responses = send_email_to_many(email_subject, email_html, recipients)
        delivery["email"] = {"recipients": recipients, "messages": email_responses}
        channel_list.append("email")

    if settings.telegram_bot_token and settings.telegram_chat_id:
        try:
            telegram_response = send_daily_text(
                thought_of_day=reflection,
                theme_of_day=theme_of_day,
                citation=citation,
                calendar_add_link=calendar_add_link,
                sent_id=sent_id,
            )
            delivery["telegram"] = telegram_response
            channel_list.append("telegram")
        except Exception as exc:  # noqa: BLE001
            # Don't fail the whole send if Telegram has a transient issue.
            delivery["telegram"] = {"status": "error", "error": str(exc)}

    if (
        settings.gcal_client_id
        and settings.gcal_client_secret
        and settings.gcal_refresh_token
        and settings.gcal_calendar_id
    ):
        try:
            upsert_theme_of_day_event(
                run_date=run_date,
                theme_of_day=str(theme_of_day),
                description=reflection[:500],
            )
        except Exception:
            # Calendar sync is non-critical for daily message delivery.
            pass

    if sent_id:
        update_sent_history(client, sent_id, {"channels": channel_list})

    return {
        "status": "sent",
        "run_date": run_date.isoformat(),
        "sent_id": saved.get("id"),
        "delivery": delivery,
    }

