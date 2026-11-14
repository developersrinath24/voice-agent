import secrets
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from supabase import Client

from app.agents.clinic_assistant import ClinicAssistant
from app.core.config import settings
from app.database.client import get_supabase
from app.services.llm import LLMNotConfigured, get_llm


def require_api_key(x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None) -> None:
    """Optional shared-secret gate for every endpoint that costs money.

    Off when ``API_KEY`` is empty, so local development needs no ceremony. On a
    public host it is the only thing between your LLM quota and the internet.
    Compared with ``compare_digest`` so the check does not leak the key's length
    or prefix through response timing.
    """
    expected = settings.API_KEY
    if not expected:
        return
    if x_api_key is None or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def supabase_client() -> Client:
    """FastAPI dependency: gives a Supabase client or a clean 503."""
    try:
        return get_supabase()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@lru_cache
def get_assistant() -> ClinicAssistant:
    return ClinicAssistant(get_llm())


def clinic_assistant() -> ClinicAssistant:
    """FastAPI dependency: the assembled RAG chain, or a clean 503."""
    try:
        return get_assistant()
    except LLMNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


# Use in route signatures as:  client: SupabaseClient
SupabaseClient = Annotated[Client, Depends(supabase_client)]
Assistant = Annotated[ClinicAssistant, Depends(clinic_assistant)]
