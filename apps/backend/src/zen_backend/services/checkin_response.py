"""Orchestrator for the per-submit Gemini observation + grounded passage.

Run after a check-in is persisted. Returns a `(message, passage)` pair
that the public `/checkin` page renders inline. Designed to never block
the user: every external call is wrapped, a hard timeout caps Gemini,
and graceful fallbacks (static message, random recent gold passage,
nothing-at-all) cover every failure mode.
"""

from __future__ import annotations

import concurrent.futures
import logging
import random
import re
from dataclasses import dataclass
from datetime import date as date_type
from typing import Any

from zen_backend.config import settings
from zen_backend.db.client import get_supabase_client
from zen_backend.db.queries import fetch_candidate_passages
from zen_backend.services.gemini_client import generate_checkin_observation
from zen_backend.services.retrieval import choose_passage, fetch_ranked_passages

logger = logging.getLogger(__name__)


_FORBIDDEN_PHRASES: tuple[str, ...] = (
    "you've got this",
    "trust the journey",
    "embrace",
    "manifest",
    "hustle",
    "grind",
    "level up",
    "remember that,",
    "based on your",
    "i see that",
)

_FORBIDDEN_OPENERS: tuple[str, ...] = (
    "i see",
    "it looks like",
    "based on",
    "your answers",
    "the data",
    "your check-in",
)


_FALLBACK_MESSAGES: dict[str, str] = {
    "morning": (
        "The morning is here, and so are you. "
        "Let one steady breath be the first thing you give yourself today."
    ),
    "midday": (
        "The middle of the day asks little — only that you stay near what is in front of you. "
        "One unhurried look around, and continue."
    ),
    "evening": (
        "The day is closing on its own time. "
        "Let what was enough be enough, and rest into the quiet that is already waiting."
    ),
}


@dataclass
class CheckinResponseBundle:
    message: str
    message_source: str  # "gemini" or "fallback"
    passage: dict[str, Any] | None
    passage_source: str  # "retrieval", "random_gold", or "none"


def _format_answer_lines(window: str, answers: list[dict[str, Any]]) -> list[str]:
    """Build the human-readable lines fed into the Gemini prompt.

    Imports are local so the module stays usable in tests that monkeypatch
    just the Gemini call without standing up the full route module.
    """
    from zen_backend.routes.checkin import _QUESTIONS_BY_WINDOW

    label_by_key = {
        q["key"]: q["label"]
        for q in _QUESTIONS_BY_WINDOW.get(window, [])
    }
    lines = []
    for ans in answers:
        key = str(ans.get("key", "?"))
        score = ans.get("score", "?")
        label = label_by_key.get(key, key)
        lines.append(f"{key} ({score}/5): {label}")
    return lines


def _validate_message(text: str) -> bool:
    """Reject obvious cliché / meta-reference output. Same spirit as the
    daily generator's quality check, but smaller — this is a softer
    surface and we'd rather show *something* than nothing."""
    if not text or not text.strip():
        return False
    lowered = text.strip().lower()
    if any(lowered.startswith(opener) for opener in _FORBIDDEN_OPENERS):
        return False
    if any(phrase in lowered for phrase in _FORBIDDEN_PHRASES):
        return False
    word_count = len(re.findall(r"\b\w+\b", text))
    if word_count < 18 or word_count > 100:
        return False
    return True


def _gemini_with_timeout(
    *,
    window: str,
    on_date: date_type,
    answer_lines: list[str],
    mood_score_weighted: float | None,
    challenge_score: float | None,
    note: str | None,
    timeout_s: float,
) -> str | None:
    """Run the Gemini call on a worker thread with a hard wall-clock cap."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            generate_checkin_observation,
            window=window,
            on_date=on_date,
            answer_lines=answer_lines,
            mood_score_weighted=mood_score_weighted,
            challenge_score=challenge_score,
            note=note,
        )
        try:
            return future.result(timeout=timeout_s)
        except concurrent.futures.TimeoutError:
            logger.warning("Gemini check-in observation timed out after %.1fs", timeout_s)
            return None
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gemini check-in observation failed: %s", exc)
            return None


def _build_retrieval_query_and_tags(
    window: str,
    mood_score_weighted: float | None,
    challenge_score: float | None,
) -> tuple[str, list[str]]:
    """Map the answer pattern to a retrieval query + required-tag set.

    Mirrors the same logic the daily generator already uses (mood thresholds
    on the 0-100 scale: <=40 low, >=75 high) so the daily reflection and
    the per-check-in passage stay in the same conceptual neighbourhood.
    """
    base = "calm presence, grounded reflection, daily anchor"
    tags: list[str] = ["presence"]

    if window == "morning":
        base += ", morning intention, fresh beginning, dawn"
    elif window == "midday":
        base += ", midday pause, present focus"
    elif window == "evening":
        base += ", end of day reflection, rest, return"

    if mood_score_weighted is not None:
        if mood_score_weighted <= 40:
            base += ", support overwhelm, gentler framing, patience"
            tags.extend(["rest", "patience"])
        elif mood_score_weighted >= 75:
            base += ", sustain momentum with grounded discipline"
            tags.extend(["discipline", "work"])

    if challenge_score is not None and challenge_score >= 4.0:
        base += ", clarity under pressure"
        tags.extend(["courage"])

    return base, list(dict.fromkeys(tags))


def _retrieve_passage(
    window: str,
    mood_score_weighted: float | None,
    challenge_score: float | None,
) -> tuple[dict[str, Any] | None, str]:
    """Try the embedding-ranked retrieval first; fall back to a random
    recent gold passage; if both fail, return None.
    Returns (passage_dict_or_None, source_tag).
    """
    query, tags = _build_retrieval_query_and_tags(window, mood_score_weighted, challenge_score)
    try:
        ranked = fetch_ranked_passages(
            query,
            source_tier="gold",
            required_tags=tags or None,
            prefer_season_words=False,
            limit=8,
        )
        if ranked:
            return choose_passage(ranked), "retrieval"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Check-in passage retrieval failed: %s", exc)

    try:
        client = get_supabase_client()
        candidates = fetch_candidate_passages(client, source_tier="gold", limit=20)
        if candidates:
            return random.choice(candidates), "random_gold"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Check-in random-gold fallback failed: %s", exc)

    return None, "none"


# Match leading verse-number prefixes the chunker leaves on some traditions,
# e.g. "314. An evil deed…" (Dhammapada) or "42. The wise…" (verse texts).
# We deliberately do NOT match Roman numerals or chapter.verse patterns —
# those are rare and ambiguous (could be legitimate content).
_LEADING_VERSE_NUMBER_RE = re.compile(r"^\s*\d+\s*[.)]\s+")


def _strip_leading_verse_marker(text: str) -> str:
    return _LEADING_VERSE_NUMBER_RE.sub("", text, count=1)


def _public_passage_view(passage: dict[str, Any] | None) -> dict[str, Any] | None:
    """Strip the passage dict to the fields the public form needs.
    Avoids leaking embedding similarity scores etc. to the browser, and
    cleans up cosmetic chunker artifacts like the leading verse number."""
    if not passage:
        return None
    raw_text = str(passage.get("text", "")).strip()
    return {
        "text": _strip_leading_verse_marker(raw_text),
        "source": str(passage.get("source", "")).strip(),
        "citation": str(passage.get("citation", "")).strip(),
        "tradition": str(passage.get("tradition", "")).strip(),
    }


def build_checkin_response_bundle(
    *,
    window: str,
    on_date: date_type,
    answers: list[dict[str, Any]],
    mood_score_weighted: float | None,
    challenge_score: float | None,
    note: str | None = None,
) -> CheckinResponseBundle:
    """Top-level entry. Always returns a bundle; never raises."""
    fallback_message = _FALLBACK_MESSAGES.get(window, _FALLBACK_MESSAGES["evening"])

    if not settings.enable_checkin_gemini_response or not settings.gemini_api_key:
        passage, passage_source = _retrieve_passage(
            window, mood_score_weighted, challenge_score
        )
        return CheckinResponseBundle(
            message=fallback_message,
            message_source="fallback",
            passage=_public_passage_view(passage),
            passage_source=passage_source,
        )

    answer_lines = _format_answer_lines(window, answers)
    raw = _gemini_with_timeout(
        window=window,
        on_date=on_date,
        answer_lines=answer_lines,
        mood_score_weighted=mood_score_weighted,
        challenge_score=challenge_score,
        note=note,
        timeout_s=settings.checkin_gemini_timeout_s,
    )

    if raw is not None and _validate_message(raw):
        message = raw.strip()
        message_source = "gemini"
    else:
        if raw is not None:
            logger.info("Gemini check-in observation rejected by validator: %r", raw[:120])
        message = fallback_message
        message_source = "fallback"

    passage, passage_source = _retrieve_passage(
        window, mood_score_weighted, challenge_score
    )
    return CheckinResponseBundle(
        message=message,
        message_source=message_source,
        passage=_public_passage_view(passage),
        passage_source=passage_source,
    )
