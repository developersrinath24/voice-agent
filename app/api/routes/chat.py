import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.api.deps import Assistant, SupabaseClient
from app.database import repositories as repo
from app.schemas.chat import ChatRequest, ChatResponse, SourceRef

logger = logging.getLogger(__name__)

router = APIRouter()

# How many previous turns to give the model. Enough for "and on Saturday?"
# follow-ups, short enough to keep the prompt cheap and the context focused.
HISTORY_LIMIT = 10


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    client: SupabaseClient,
    assistant: Assistant,
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

    history = [
        (row["role"], row["content"])
        for row in repo.recent_messages(client, session_id, limit=HISTORY_LIMIT)
    ]

    # Store the question first: if generation fails, the transcript still shows
    # what was asked.
    repo.add_message(client, session_id, "user", request.message)

    try:
        answer = assistant.answer(request.message, history=history)
    except Exception:
        logger.exception("assistant failed session_id=%s", session_id)
        raise HTTPException(
            status_code=502,
            detail="The assistant could not answer right now. Please try again.",
        ) from None

    repo.add_message(client, session_id, "assistant", answer.text)

    logger.info(
        "chat turn session_id=%s grounded=%s sources=%d",
        session_id,
        answer.grounded,
        len(answer.sources),
    )

    return ChatResponse(
        session_id=session_id,
        response=answer.text,
        message_count=repo.count_messages(client, session_id),
        grounded=answer.grounded,
        sources=[
            SourceRef(
                section=chunk.section,
                source=chunk.source,
                score=round(chunk.score, 4),
            )
            for chunk in answer.sources
        ],
    )
