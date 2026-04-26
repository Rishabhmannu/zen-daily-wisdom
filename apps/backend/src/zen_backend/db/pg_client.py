from __future__ import annotations

from contextlib import contextmanager

import psycopg

from zen_backend.config import settings


def _clean(value: str) -> str:
    return value.strip().strip('"').strip("'").replace("\r", "").replace("\n", "")


def _get_dsn() -> str:
    dsn = _clean(settings.supabase_db_dsn_pooler or settings.supabase_db_dsn)
    if not dsn:
        raise RuntimeError("Set SUPABASE_DB_DSN or SUPABASE_DB_DSN_POOLER for direct SQL access.")
    return dsn


@contextmanager
def pg_connection():
    dsn = _get_dsn()
    with psycopg.connect(dsn) as conn:
        yield conn

