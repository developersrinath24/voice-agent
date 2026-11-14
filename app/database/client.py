"""Supabase client.

Created lazily (not at import time) so the app can still boot for health
checks and tests when credentials are missing or wrong.
"""

from functools import lru_cache

from supabase import Client, create_client

from app.core.config import settings


@lru_cache
def get_supabase() -> Client:
    if not settings.supabase_configured:
        raise RuntimeError("Supabase is not configured. Set SUPABASE_URL and SUPABASE_KEY in .env")
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
