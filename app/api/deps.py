from typing import Annotated

from fastapi import Depends, HTTPException
from supabase import Client

from app.database.client import get_supabase


def supabase_client() -> Client:
    """FastAPI dependency: gives a Supabase client or a clean 503."""
    try:
        return get_supabase()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


# Use in route signatures as:  client: SupabaseClient
SupabaseClient = Annotated[Client, Depends(supabase_client)]
