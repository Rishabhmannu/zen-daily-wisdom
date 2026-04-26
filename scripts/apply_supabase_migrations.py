#!/usr/bin/env python3
"""Apply SQL migrations in infra/supabase/migrations using SUPABASE_DB_DSN."""

from __future__ import annotations

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = ROOT / "infra" / "supabase" / "migrations"


def main() -> int:
    load_dotenv(ROOT / ".env")
    dsn = os.getenv("SUPABASE_DB_DSN", "").strip().replace("\r", "")
    if not dsn:
        raise SystemExit("SUPABASE_DB_DSN is required to apply migrations.")

    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        raise SystemExit(f"No migration files found in {MIGRATIONS_DIR}")

    with psycopg.connect(dsn) as conn:
        conn.autocommit = False
        with conn.cursor() as cur:
            for file in files:
                sql = file.read_text(encoding="utf-8")
                print(f"Applying {file.name} ...")
                cur.execute(sql)
        conn.commit()

    print(f"Applied {len(files)} migration files successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

