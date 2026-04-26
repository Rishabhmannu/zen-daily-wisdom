#!/usr/bin/env python3
"""Seed passages table from downloaded corpus assets."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from supabase import create_client


ROOT = Path(__file__).resolve().parents[1]
GOLD_DIR = ROOT / "assets" / "corpus" / "gold"
SILVER_FILE = ROOT / "assets" / "corpus" / "silver" / "abirate_english_quotes.jsonl"


GOLD_SOURCES: dict[str, tuple[str, str]] = {
    "bhagavad_gita_song_celestial.txt": ("bhagavad_gita", "Bhagavad Gita (Song Celestial)"),
    "tao_te_ching_legge.txt": ("tao_te_ching", "Tao Te Ching (Legge)"),
    "analects_legge.txt": ("analects", "Analects (Legge)"),
    "meditations_marcus_aurelius.txt": ("marcus_aurelius", "Meditations (Marcus Aurelius)"),
    "epictetus_discourses.txt": ("epictetus", "Discourses (Epictetus)"),
    "walden_thoreau.txt": ("thoreau", "Walden (Thoreau)"),
    "emerson_essays_first_series.txt": ("emerson", "Essays First Series (Emerson)"),
    "gibran_the_prophet.txt": ("gibran", "The Prophet (Gibran)"),
    "aesops_fables.txt": ("aesop", "Aesop's Fables"),
    "tagore_gitanjali.txt": ("tagore", "Gitanjali (Tagore)"),
    "dhammapada_muller.txt": ("dhammapada", "Dhammapada (Muller)"),
    "my_first_summer_in_the_sierra_muir.txt": ("muir", "My First Summer in the Sierra (Muir)"),
    "wake_robin_burroughs.txt": ("burroughs", "Wake-Robin (Burroughs)"),
}


KEYWORD_TAGS: dict[str, set[str]] = {
    "nature": {"nature", "forest", "river", "sky", "tree", "wind", "earth", "mountain", "bird"},
    "work": {"work", "labor", "craft", "duty", "effort", "task"},
    "presence": {"present", "today", "now", "attention", "aware", "mindful"},
    "courage": {"courage", "brave", "fear", "bold"},
    "impermanence": {"impermanence", "change", "passing", "death", "mortal"},
    "love": {"love", "heart", "friend", "friendship"},
    "discipline": {"discipline", "habit", "practice", "routine"},
    "joy": {"joy", "happiness", "delight"},
    "sorrow": {"sorrow", "grief", "pain"},
    "cosmos": {"universe", "infinite", "stars", "cosmos"},
    "animals": {"fox", "lion", "wolf", "bird", "animal", "dog", "cat"},
    "change": {"spring", "summer", "autumn", "fall", "winter", "season", "monsoon", "rain"},
}


def _normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _chunk_text(raw: str) -> list[str]:
    cleaned = _normalize_whitespace(raw)
    # Paragraph-level chunks.
    chunks = [c.strip() for c in re.split(r"\n\s*\n", cleaned) if c.strip()]
    # Keep chunks with meaningful size.
    return [c for c in chunks if 120 <= len(c) <= 1800]


def _length_bucket(text: str) -> str:
    words = len(text.split())
    if words < 40:
        return "short"
    if words <= 120:
        return "medium"
    return "long"


def _tags_for_text(text: str) -> list[str]:
    lowered = text.lower()
    tags: list[str] = []
    for tag, words in KEYWORD_TAGS.items():
        if any(word in lowered for word in words):
            tags.append(tag)
    if not tags:
        tags = ["presence"]
    return tags[:3]


def _gold_rows(limit_per_source: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for file in sorted(GOLD_DIR.glob("*.txt")):
        if file.name not in GOLD_SOURCES:
            continue
        tradition, source = GOLD_SOURCES[file.name]
        chunks = _chunk_text(file.read_text(encoding="utf-8", errors="ignore"))
        if limit_per_source:
            chunks = chunks[:limit_per_source]
        for i, chunk in enumerate(chunks, start=1):
            rows.append(
                {
                    "tradition": tradition,
                    "source": source,
                    "citation": f"{file.stem}#{i}",
                    "text": chunk,
                    "theme_tags": _tags_for_text(chunk),
                    "tone": "gentle",
                    "length_bucket": _length_bucket(chunk),
                    "source_tier": "gold",
                    "embedding": None,
                }
            )
    return rows


def _silver_rows(limit: int | None = None) -> list[dict[str, Any]]:
    if not SILVER_FILE.exists():
        return []

    rows: list[dict[str, Any]] = []
    with SILVER_FILE.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            if limit and i > limit:
                break
            raw = json.loads(line)
            quote = str(raw.get("quote", "")).strip().strip('"')
            author = str(raw.get("author", "Unknown")).strip()
            if len(quote) < 60:
                continue
            rows.append(
                {
                    "tradition": "quotes_collection",
                    "source": f"{author} (Abirate english_quotes)",
                    "citation": f"abirate_quote#{i}",
                    "text": quote,
                    "theme_tags": _tags_for_text(quote),
                    "tone": "gentle",
                    "length_bucket": _length_bucket(quote),
                    "source_tier": "silver",
                    "embedding": None,
                }
            )
    return rows


def _batched(rows: list[dict[str, Any]], size: int = 200) -> list[list[dict[str, Any]]]:
    return [rows[i : i + size] for i in range(0, len(rows), size)]


def seed(
    *,
    include_silver: bool,
    dry_run: bool,
    limit_gold_per_source: int | None,
    limit_silver: int | None,
) -> None:
    load_dotenv(ROOT / ".env")
    supabase_url = __import__("os").environ.get("SUPABASE_URL", "").strip().replace("\r", "")
    service_role_key = __import__("os").environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip().replace("\r", "")
    if not supabase_url or not service_role_key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")

    gold = _gold_rows(limit_per_source=limit_gold_per_source)
    silver = _silver_rows(limit=limit_silver) if include_silver else []
    all_rows = gold + silver

    print(f"Prepared rows: gold={len(gold)} silver={len(silver)} total={len(all_rows)}")
    if not all_rows:
        print("No rows to seed.")
        return

    if dry_run:
        print("Dry run enabled; no database writes executed.")
        return

    client = create_client(supabase_url, service_role_key)
    total_inserted = 0
    for batch in _batched(all_rows, size=200):
        # on_conflict works against unique(source, citation, text)
        client.table("passages").upsert(batch, on_conflict="source,citation,text").execute()
        total_inserted += len(batch)
        print(f"Upserted batch, cumulative rows processed: {total_inserted}")
    print("Seeding completed.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed passages table from local corpus assets")
    parser.add_argument("--dry-run", action="store_true", help="Prepare rows but do not write to DB")
    parser.add_argument(
        "--include-silver",
        action="store_true",
        help="Include silver dataset rows from abirate_english_quotes.jsonl",
    )
    parser.add_argument("--limit-gold-per-source", type=int, default=None)
    parser.add_argument("--limit-silver", type=int, default=None)
    args = parser.parse_args()

    seed(
        include_silver=args.include_silver,
        dry_run=args.dry_run,
        limit_gold_per_source=args.limit_gold_per_source,
        limit_silver=args.limit_silver,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

