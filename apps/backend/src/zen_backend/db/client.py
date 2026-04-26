from __future__ import annotations

import os
from functools import lru_cache

from supabase import Client, create_client

from zen_backend.config import settings


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    supabase_url = (
        settings.supabase_url.strip().strip('"').strip("'").replace("\r", "").replace("\n", "")
    )
    service_role_key = (
        settings.supabase_service_role_key.strip()
        .strip('"')
        .strip("'")
        .replace("\r", "")
        .replace("\n", "")
    )
    if not supabase_url or not service_role_key:
        raise RuntimeError("Supabase is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
    # In local/dev shells, inherited proxy variables can break Supabase postgrest calls.
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        os.environ.pop(key, None)
    os.environ.setdefault("NO_PROXY", "*")
    os.environ.setdefault("no_proxy", "*")
    return create_client(supabase_url, service_role_key)

