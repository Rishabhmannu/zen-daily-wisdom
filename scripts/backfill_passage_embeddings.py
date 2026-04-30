#!/usr/bin/env python3
"""Backfill embeddings into `passages.embedding` (pgvector).

By default, embeds only rows where `embedding IS NULL` (so an interrupted
run resumes cleanly on re-invocation). Use `--reset` to NULL out every
row first — required when *changing* embedding backends, since query and
corpus embeddings must use the same model. `--force-reembed` always
re-embeds every row regardless of NULL status (less efficient, but
useful for forcing a refresh).

The embedding backend is selected by `services.embedding.embed_text`,
which honors the `EMBEDDING_METHOD` env var (`gemini` | `hash`) and
otherwise prefers Gemini when `GEMINI_API_KEY` is set.

Free-tier rate limits (Gemini API, gemini-embedding-001 as of 2026):
  - 100 RPM (requests per minute, per user/project/model)
  - separate TPM (tokens per minute) cap

This script paces itself below those limits via `--rpm` (default 90, a
~10% margin), and on a 429 it sleeps for the server-suggested retry
delay before continuing.

Usage:
    # First-time switch from a different backend (recommended):
    uv run --project apps/backend python scripts/backfill_passage_embeddings.py \\
        --reset --source-tier gold --batch-size 32

    # Resume an interrupted run (only embeds NULL rows):
    uv run --project apps/backend python scripts/backfill_passage_embeddings.py \\
        --source-tier gold --batch-size 32

    # Force re-embed of every row regardless of state:
    uv run --project apps/backend python scripts/backfill_passage_embeddings.py \\
        --force-reembed --source-tier gold
"""

from __future__ import annotations

import argparse
import re
import time
from pathlib import Path

from dotenv import load_dotenv

from zen_backend.db.pg_client import pg_connection
from zen_backend.services.embedding import (
    _selected_method,
    embed_text,
    embed_texts_gemini_batch,
    to_pgvector_literal,
)

ROOT = Path(__file__).resolve().parents[1]


def _parse_retry_after_seconds(exc_text: str) -> float | None:
    """Extract the 'Please retry in NN.NNNs' value from a 429 message."""
    m = re.search(r"retry in ([\d.]+)\s*s", str(exc_text))
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def _embed_one_batch_with_retry(
    texts: list[str],
    method: str,
    max_429_retries: int = 3,
) -> list[list[float]]:
    """Embed a single batch, sleeping on 429 and retrying. Falls back to
    per-row hash embedding only after we've exhausted retries — that way
    a transient rate limit doesn't silently corrupt the corpus."""
    last_exc: Exception | None = None
    for attempt in range(max_429_retries):
        try:
            if method == "gemini":
                return embed_texts_gemini_batch(texts)
            return [embed_text(t) for t in texts]
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            msg = str(exc)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                wait = _parse_retry_after_seconds(msg) or 60.0
                wait = min(wait + 1.0, 90.0)  # cap at 90s; add 1s margin
                print(
                    f"    rate-limited (attempt {attempt + 1}/{max_429_retries}); "
                    f"sleeping {wait:.1f}s before retry"
                )
                time.sleep(wait)
                continue
            # Non-429 error — surface immediately.
            raise
    # Out of retries — re-raise the last 429 so the caller's outer
    # exception handler can decide what to do.
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("unreachable")


def _select_rows(cur, *, force_reembed: bool, source_tier: str | None, limit: int | None):
    where = []
    params: list = []
    if not force_reembed:
        where.append("embedding is null")
    if source_tier:
        where.append("source_tier = %s")
        params.append(source_tier)
    sql = "select id, text from passages"
    if where:
        sql += " where " + " and ".join(where)
    if limit:
        sql += f" limit {int(limit)}"
    cur.execute(sql, params)
    return cur.fetchall()


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill passage embeddings")
    parser.add_argument(
        "--reset",
        action="store_true",
        help=(
            "Set embedding=NULL for all rows (matching --source-tier if set) "
            "before backfilling. Use when switching embedding backends so "
            "query and corpus embeddings stay consistent."
        ),
    )
    parser.add_argument(
        "--force-reembed",
        action="store_true",
        help=(
            "Re-embed every row, including those that already have an "
            "embedding. Different from --reset: doesn't NULL them first; "
            "just overwrites."
        ),
    )
    parser.add_argument(
        "--source-tier",
        default=None,
        choices=["gold", "silver", None],
        help="Restrict to a single source tier. Default: all tiers.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Items per batch API call. Smaller is safer on token limits.",
    )
    parser.add_argument(
        "--rpm",
        type=float,
        default=90.0,
        help="Cap on outgoing requests per minute (free tier limit is 100).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional cap on rows to process (for testing).",
    )
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    method = _selected_method()
    print(f"Embedding backend:    {method}")
    print(f"Source tier filter:   {args.source_tier or '(all)'}")
    print(f"Batch size:           {args.batch_size}")
    print(f"RPM cap:              {args.rpm}")
    if args.reset:
        print("Mode:                 --reset (NULL all matching rows, then embed)")
    elif args.force_reembed:
        print("Mode:                 --force-reembed (overwrite every matching row)")
    else:
        print("Mode:                 NULL-only (resume-friendly)")

    min_interval = 60.0 / args.rpm if args.rpm > 0 else 0.0

    with pg_connection() as conn:
        if args.reset:
            with conn.cursor() as cur:
                if args.source_tier:
                    cur.execute(
                        "update passages set embedding = null where source_tier = %s",
                        (args.source_tier,),
                    )
                else:
                    cur.execute("update passages set embedding = null")
                conn.commit()
                print(f"Reset complete: {cur.rowcount} rows now have embedding = NULL.")

        with conn.cursor() as cur:
            rows = _select_rows(
                cur,
                force_reembed=args.force_reembed,
                source_tier=args.source_tier,
                limit=args.limit,
            )

        total = len(rows)
        if total == 0:
            print("Nothing to do.")
            return 0
        print(f"Rows to embed:        {total}\n")

        ids = [row[0] for row in rows]
        texts = [row[1] or "" for row in rows]

        t0 = time.time()
        last_request_t = 0.0
        processed = 0
        skipped = 0
        chunk_size = max(1, args.batch_size)

        for chunk_start in range(0, total, chunk_size):
            chunk_ids = ids[chunk_start : chunk_start + chunk_size]
            chunk_texts = texts[chunk_start : chunk_start + chunk_size]

            # Pace ourselves below the RPM cap.
            wait = min_interval - (time.time() - last_request_t)
            if wait > 0:
                time.sleep(wait)

            tc = time.time()
            try:
                embeddings = _embed_one_batch_with_retry(chunk_texts, method=method)
            except Exception as exc:  # noqa: BLE001
                print(
                    f"  ! batch starting at {chunk_start}: gave up after retries — "
                    f"{type(exc).__name__}: {str(exc)[:160]}"
                )
                skipped += len(chunk_ids)
                last_request_t = time.time()
                continue

            with conn.cursor() as cur:
                for pid, vec in zip(chunk_ids, embeddings):
                    cur.execute(
                        "update passages set embedding = %s::vector where id = %s",
                        (to_pgvector_literal(vec), pid),
                    )
            conn.commit()
            last_request_t = time.time()
            processed += len(chunk_ids)
            elapsed = time.time() - tc
            print(
                f"  {processed:>5}/{total} embedded "
                f"(this batch: {len(chunk_ids):>3} in {elapsed:.1f}s)"
            )

    total_t = time.time() - t0
    print(f"\nDone. {processed} rows embedded, {skipped} skipped, in {total_t:.1f}s.")
    if skipped:
        print(
            "Skipped rows still have their previous embedding. "
            "Re-run this script (without --reset or --force-reembed) to retry them."
        )
    return 0 if skipped == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
