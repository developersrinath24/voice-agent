from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.post("/voice/turn")
async def voice_turn() -> None:
    """Speech in, speech out for one conversational turn.

    Not implemented yet. The order of work is: knowledge base + retrieval,
    then the LLM pipeline, then speech-to-text and text-to-speech on top.
    """
    raise HTTPException(
        status_code=501,
        detail="Voice pipeline not implemented yet. /chat is the current entry point.",
    )
