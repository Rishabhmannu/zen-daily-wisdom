#!/usr/bin/env python3
"""Backfill deterministic embeddings into passages.embedding (pgvector)."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

from zen_backend.db.pg_client import pg_connection
from zen_backend.services.embedding import embed_text, to_pgvector_literal

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    load_dotenv(ROOT / ".env")

    processed = 0
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("select id, text from passages where embedding is null")
            rows = cur.fetchall()
            for row in rows:
                pid, text = row
                vec = to_pgvector_literal(embed_text(text or ""))
                cur.execute("update passages set embedding = %s::vector where id = %s", (vec, pid))
                processed += 1
        conn.commit()

    print(f"Backfilled embeddings for {processed} passages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

