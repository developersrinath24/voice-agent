import logging

from fastapi import APIRouter, HTTPException

from app.api.deps import Assistant, SupabaseClient
from app.api.turns import begin_turn
from app.database import repositories as repo
from app.schemas.chat import ChatRequest, ChatResponse, SourceRef

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    client: SupabaseClient,
    assistant: Assistant,
) -> ChatResponse:
    # Deliberately a sync endpoint: everything it calls is blocking (supabase-py,
    # fastembed, the LLM chain). FastAPI runs sync endpoints in a thread pool, so
    # a second caller waits on a worker instead of freezing the event loop for
    # everyone else.
    session_id, history = begin_turn(client, request.session_id, request.message)

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
        sources=[SourceRef.from_chunk(chunk) for chunk in answer.sources],
    )
