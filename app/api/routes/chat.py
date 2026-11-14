import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.api.deps import SupabaseClient
from app.database import repositories as repo
from app.schemas.chat import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# The RAG + LLM pipeline replaces this in the next phase. Messages are already
# being persisted, so history and session plumbing are real from here on.
PLACEHOLDER_ANSWER = (
    "Thanks, I have saved your message. The clinic knowledge base and "
    "reasoning pipeline are not connected yet."
)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    client: SupabaseClient,
) -> ChatResponse:
    if request.session_id is not None:
        session = repo.get_session(client, request.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        if session["status"] != "active":
            raise HTTPException(status_code=409, detail="Session has already ended")
    else:
        session = repo.create_session(client)

    session_id = UUID(session["id"])

    repo.add_message(client, session_id, "user", request.message)
    repo.add_message(client, session_id, "assistant", PLACEHOLDER_ANSWER)

    logger.info("chat turn stored session_id=%s", session_id)

    return ChatResponse(
        session_id=session_id,
        response=PLACEHOLDER_ANSWER,
        message_count=repo.count_messages(client, session_id),
    )
