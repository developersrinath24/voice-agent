"""Turn-based voice: one recording in, one spoken answer out.

This is deliberately not realtime. It is the smallest honest voice pipeline —
speech-to-text, the same RAG chain as /chat, text-to-speech — and it exists to
make the seam between speech and knowledge visible before an agent platform
takes the audio plumbing over.

Two consequences worth knowing: there is no barge-in, and the user waits for the
whole answer to be generated before hearing any of it. Both disappear when the
answer is streamed token by token into a streaming TTS call.
"""

import base64
import logging
from time import perf_counter
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.api.deps import Assistant, SupabaseClient, Voice
from app.api.turns import begin_turn
from app.core.config import settings
from app.database import repositories as repo
from app.schemas.chat import SourceRef
from app.schemas.voice import VoiceTurnResponse
from app.services.voice import VoiceError

logger = logging.getLogger(__name__)

router = APIRouter()

# Browsers send audio/webm from MediaRecorder and audio/mp4 on Safari; the
# extension of the file is irrelevant to ElevenLabs.
ALLOWED_CONTENT_TYPES = {"video/webm", "application/octet-stream"}


@router.post("/voice/turn", response_model=VoiceTurnResponse)
def voice_turn(
    client: SupabaseClient,
    assistant: Assistant,
    speech: Voice,
    file: Annotated[UploadFile, File(description="Recorded question, e.g. audio/webm")],
    session_id: Annotated[UUID | None, Form()] = None,
) -> VoiceTurnResponse:
    # Sync def for the same reason as /chat: httpx, supabase and the chain all
    # block, so FastAPI hands this to a thread-pool worker.
    content_type = (file.content_type or "application/octet-stream").split(";")[0].strip()
    if not content_type.startswith("audio/") and content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported audio type: {content_type}")

    # Read one byte past the cap so an oversized upload is detected without
    # loading the whole thing into memory.
    limit = settings.VOICE_MAX_UPLOAD_BYTES
    audio = file.file.read(limit + 1)
    if not audio:
        raise HTTPException(status_code=422, detail="The recording was empty")
    if len(audio) > limit:
        raise HTTPException(
            status_code=413,
            detail=f"Recording is larger than {limit // (1024 * 1024)} MB",
        )

    started = perf_counter()
    try:
        transcript = speech.transcribe(
            audio, file.filename or "question.webm", content_type
        ).strip()
    except VoiceError as exc:
        logger.warning("transcription failed: %s", exc)
        raise HTTPException(status_code=502, detail="Could not transcribe the recording") from None
    after_transcribe = perf_counter()

    if not transcript:
        raise HTTPException(status_code=422, detail="No speech detected in the recording")

    resolved, history = begin_turn(client, session_id, transcript)

    try:
        answer = assistant.answer(transcript, history=history)
    except Exception:
        logger.exception("assistant failed session_id=%s", resolved)
        raise HTTPException(
            status_code=502,
            detail="The assistant could not answer right now. Please try again.",
        ) from None
    after_answer = perf_counter()

    repo.add_message(client, resolved, "assistant", answer.text)

    # The answer is stored before synthesis: if text-to-speech fails, the caller
    # gets an error but the transcript is still complete.
    try:
        spoken = speech.synthesize(answer.text)
    except VoiceError as exc:
        logger.warning("synthesis failed session_id=%s: %s", resolved, exc)
        raise HTTPException(
            status_code=502,
            detail="The answer was produced but could not be turned into audio",
        ) from None
    finished = perf_counter()

    timings = {
        "transcribe": round((after_transcribe - started) * 1000),
        "answer": round((after_answer - after_transcribe) * 1000),
        "speak": round((finished - after_answer) * 1000),
    }
    logger.info(
        "voice turn session_id=%s grounded=%s sources=%d ms=%s audio_bytes=%d",
        resolved,
        answer.grounded,
        len(answer.sources),
        timings,
        len(spoken),
    )

    return VoiceTurnResponse(
        session_id=resolved,
        transcript=transcript,
        response=answer.text,
        grounded=answer.grounded,
        sources=[SourceRef.from_chunk(chunk) for chunk in answer.sources],
        audio_base64=base64.b64encode(spoken).decode("ascii"),
        timings_ms=timings,
    )
