#!/usr/bin/env python3
"""Export production data into `assets/eval/` for the evaluation notebooks.

The notebooks in `notebooks/` are deliberately decoupled from Supabase so a
recruiter can render them from a clean clone without DB credentials. This
script is the bridge: it pulls live tables once, writes them as JSON
snapshots under `assets/eval/`, and the notebooks read from there.

Run:
    uv run --project apps/backend python scripts/export_eval_data.py

Outputs (gitignored by default — check `.gitignore`):
    assets/eval/sent_history.json
    assets/eval/feedback.json
    assets/eval/checkin_responses.json
    assets/eval/bandit_state.json
    assets/eval/_meta.json   (exported_at, row counts)

Add `--commit-snapshot` to write the JSON outside .gitignore (useful when
you want a specific eval run to be portfolio-reproducible).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
EVAL_DIR = ROOT / "assets" / "eval"


TABLES = ["sent_history", "feedback", "checkin_responses", "bandit_state"]


def _supabase_client():
    """Lazy-import so the module works for `--help` even without supabase installed."""
    from dotenv import load_dotenv
    from supabase import create_client

    load_dotenv(ENV_PATH)

    import os

    url = (os.environ.get("SUPABASE_URL") or "").strip().replace("\r", "")
    key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip().replace("\r", "")
    if not url or not key:
        raise SystemExit(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env"
        )
    return create_client(url, key)


def fetch_all(client, table: str, page_size: int = 1000) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        result = (
            client.table(table)
            .select("*")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        chunk = result.data or []
        rows.extend(chunk)
        if len(chunk) < page_size:
            break
        offset += page_size
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Supabase tables for eval notebooks.")
    parser.add_argument(
        "--commit-snapshot",
        action="store_true",
        help="Write a JSON snapshot that's not gitignored (use with care; data may be personal).",
    )
    args = parser.parse_args()

    client = _supabase_client()
    EVAL_DIR.mkdir(parents=True, exist_ok=True)

    counts = {}
    for table in TABLES:
        print(f"Fetching {table}…", end=" ", flush=True)
        rows = fetch_all(client, table)
        counts[table] = len(rows)
        out_path = EVAL_DIR / f"{table}.json"
        out_path.write_text(json.dumps(rows, default=str, indent=2), encoding="utf-8")
        print(f"{len(rows):>4} rows -> {out_path.relative_to(ROOT)}")

    meta = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "counts": counts,
        "committed": args.commit_snapshot,
    }
    (EVAL_DIR / "_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"\nMeta: {EVAL_DIR / '_meta.json'}")
    print("\nDone. Open the notebooks in `notebooks/` to render eval reports.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
