from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException
from supabase import Client

from app.agents.clinic_assistant import ClinicAssistant
from app.database.client import get_supabase
from app.services.llm import LLMNotConfigured, get_llm


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
