from __future__ import annotations

from datetime import date

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

