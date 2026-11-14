from uuid import UUID

from fastapi import APIRouter, HTTPException
from supabase import Client

from app.api.deps import SupabaseClient
from app.database import repositories as repo
from app.schemas.session import MessageResponse, SessionResponse

router = APIRouter(prefix="/sessions")


def _to_response(client: Client, session: dict) -> SessionResponse:
    session_id = UUID(session["id"])
    return SessionResponse(
        session_id=session_id,
        status=session["status"],
        message_count=repo.count_messages(client, session_id),
        created_at=session.get("created_at"),
    )


@router.post("", response_model=SessionResponse, status_code=201)
def create_session(client: SupabaseClient) -> SessionResponse:
    return _to_response(client, repo.create_session(client))


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(session_id: UUID, client: SupabaseClient) -> SessionResponse:
    session = repo.get_session(client, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return _to_response(client, session)


@router.get("/{session_id}/messages", response_model=list[MessageResponse])
def get_messages(session_id: UUID, client: SupabaseClient) -> list[MessageResponse]:
    session = repo.get_session(client, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return [
        MessageResponse(
            id=row["id"],
            role=row["role"],
            content=row["content"],
            created_at=row["created_at"],
        )
        for row in repo.list_messages(client, session_id)
    ]


@router.post("/{session_id}/end", response_model=SessionResponse)
def end_session(session_id: UUID, client: SupabaseClient) -> SessionResponse:
    session = repo.get_session(client, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["status"] == "ended":
        return _to_response(client, session)

    updated = repo.end_session(client, session_id)
    return _to_response(client, updated or session)
