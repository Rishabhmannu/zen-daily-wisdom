from __future__ import annotations

from datetime import date
from typing import Iterable

from google import genai

from zen_backend.config import settings


def _build_prompt(run_date: date, passage_text: str, citation: str) -> str:
    return (
        f"Date: {run_date.isoformat()}\n"
        "Write a short 'Thought of the Day' in English (20-45 words only).\n"
        "Tone must be calm, grounded, vivid, and non-generic.\n"
        "Use max 2 short sentences and no bullet points.\n"
        "Do not mention words like: passage, text, source, quote, or citation.\n"
        "Do not start with: 'The passage', 'This passage', 'The text', 'This text'.\n"
        "Write as if this thought stands alone in an email without any extra context.\n"
        "Do not use cliches like 'you've got this', 'believe in yourself', or 'trust the journey'.\n\n"
        f'Passage: "{passage_text}"\n'
        f"Citation: {citation}\n\n"
        "Output plain text only."
    )


def generate_reflection(
    run_date: date,
    passage_text: str,
    citation: str,
    system_prompt: str | None = None,
    reflection_prompt: str | None = None,
) -> str:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")

    client = genai.Client(api_key=settings.gemini_api_key)
    prompt = _build_prompt(run_date, passage_text, citation)
    if system_prompt:
        prompt = f"System instruction:\n{system_prompt}\n\n{prompt}"
    if reflection_prompt:
        prompt = f"{prompt}\n\nExtra instruction:\n{reflection_prompt}"
    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)

    text = (response.text or "").strip()
    if not text:
        raise RuntimeError("Gemini returned empty response.")
    return text


def _build_checkin_observation_prompt(
    *,
    window: str,
    on_date: date,
    answer_lines: Iterable[str],
    mood_score_weighted: float | None,
    challenge_score: float | None,
    note: str | None,
) -> str:
    """Prompt for the per-submit observational message.

    Two short sentences, observational not therapeutic. Reuses the same
    forbidden-phrase guardrails as the daily generator so the voice stays
    consistent across all surfaces.
    """
    answers_block = "\n".join(f"  - {line}" for line in answer_lines)
    mood_line = (
        f"Mood Score (0-100, where 100 is best): {mood_score_weighted:.0f}"
        if mood_score_weighted is not None
        else "Mood Score: not available"
    )
    challenge_line = (
        f"Challenge load (1-5, where 5 is heaviest): {challenge_score:.1f}"
        if challenge_score is not None
        else "Challenge load: not available"
    )
    note_line = f'User note: "{note}"' if note else "User note: (none)"
    return (
        "You write for Rishabh, a 22-year-old Indian B.Tech final-year student aspiring to ML/AI work.\n"
        f"He just submitted a {window} check-in on {on_date.isoformat()}. Use his answers below "
        "to write EXACTLY 2 short sentences:\n"
        "  1. The first observes what's true in his answers right now. Name what's there. "
        "Do not tell him what he feels.\n"
        "  2. The second points him to a small thing he can hold or notice next. "
        "Not advice; not a fix.\n\n"
        "Hard rules:\n"
        "  - Total length: 30 to 60 words.\n"
        "  - Calm, direct register. No clinical, therapeutic, or diagnostic language.\n"
        "  - No commands, no 'you should', no 'try to'.\n"
        "  - No clichés: 'you've got this', 'trust the journey', 'embrace', 'manifest', "
        "'hustle', 'grind', 'level up', 'remember that'.\n"
        "  - Do not mention 'data', 'scores', 'numbers', 'check-in', 'survey', or 'analysis'.\n"
        "  - Do not start with 'I see', 'It looks like', 'Based on', 'Your answers'.\n\n"
        "Today's check-in:\n"
        f"{answers_block}\n"
        f"{mood_line}\n"
        f"{challenge_line}\n"
        f"{note_line}\n\n"
        "Output the two sentences as plain text. Nothing else."
    )


def generate_checkin_observation(
    *,
    window: str,
    on_date: date,
    answer_lines: list[str],
    mood_score_weighted: float | None,
    challenge_score: float | None,
    note: str | None = None,
) -> str:
    """Call Gemini for a 2-sentence observational message tailored to this
    check-in. Raises on any error; the orchestrator is responsible for
    falling back to a static message."""
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")

    client = genai.Client(api_key=settings.gemini_api_key)
    prompt = _build_checkin_observation_prompt(
        window=window,
        on_date=on_date,
        answer_lines=answer_lines,
        mood_score_weighted=mood_score_weighted,
        challenge_score=challenge_score,
        note=note,
    )
    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    text = (response.text or "").strip()
    if not text:
        raise RuntimeError("Gemini returned empty response.")
    return text

