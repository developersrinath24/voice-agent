from fastapi import APIRouter, HTTPException

from app.api.deps import CallBudgetDep, Voice
from app.core.config import settings
from app.schemas.voice_session import VoiceSessionResponse
from app.services.voice import VoiceError

router = APIRouter()

# Shown in the UI when there is nothing left today. Kept here so the wording is
# one edit, not two.
ALLOWANCE_SPENT = (
    "The voice demo has used its calls for today. Please use the text chat, or come back tomorrow."
)


@router.get("/voice/session", response_model=VoiceSessionResponse)
def voice_session(voice: Voice, budget: CallBudgetDep) -> VoiceSessionResponse:
    """Issue a signed URL for one realtime agent call.

    The counter is decremented here rather than on the LLM endpoint because a
    call is what costs money; the number of turns inside it is irrelevant to
    the bill. A call is only counted once ElevenLabs has actually issued a URL,
    so a failed handshake does not eat the demo's allowance.
    """
    if not settings.ELEVENLABS_AGENT_ID:
        raise HTTPException(
            status_code=503,
            detail="ELEVENLABS_AGENT_ID is not set; realtime calls are disabled",
        )

    if budget.remaining() <= 0:
        raise HTTPException(status_code=429, detail=ALLOWANCE_SPENT)

    try:
        signed_url = voice.signed_url(settings.ELEVENLABS_AGENT_ID)
    except VoiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not budget.take():
        raise HTTPException(status_code=429, detail=ALLOWANCE_SPENT)

    return VoiceSessionResponse(
        signed_url=signed_url,
        max_seconds=settings.VOICE_MAX_CALL_SECONDS,
        remaining_calls=budget.remaining(),
    )
