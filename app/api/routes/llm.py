"""OpenAI-compatible endpoint that ElevenLabs' agent uses as its "custom LLM".

The agent handles the hard realtime parts — microphone, turn taking, barge-in,
speech synthesis. It hands us the transcript and expects a stream of
``chat.completion.chunk`` events back. So this module is a thin translation
layer:

    ElevenLabs messages -> question + history -> ClinicAssistant -> SSE chunks

Two things matter for how it sounds on a phone:

* The first chunk is a short buffer phrase, sent before retrieval starts. The
  RAG turn takes a couple of seconds; without it the caller hears silence and
  talks over the agent. The phrase buys that time and sounds like a person.
* The chunks are plain text, not tokens. The answer is written by a chain that
  does not stream, and speaking "Let me check…" followed by a half-written
  sentence is worse than waiting for the sentence.

The endpoint is gated by ``AGENT_LLM_SECRET``, not by the user-facing API key:
ElevenLabs never sees the API key, and every call here spends LLM quota.
"""

import json
import logging
import time
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.api.deps import Assistant, require_agent_secret
from app.api.turns import HISTORY_LIMIT
from app.schemas.llm import ChatCompletionRequest, ChatMessage

logger = logging.getLogger(__name__)

router = APIRouter()

# Said while the chain works. Spoken by the same voice, so it should read like
# something a receptionist would actually say, not like a loading spinner.
BUFFER_PHRASE = "One moment, let me check that for you. "

# Used when retrieval or generation throws. Still in character: the caller has
# no idea the backend failed, and "internal server error" is not a sentence.
FAILURE_ANSWER = (
    "Sorry, I could not look that up just now. Could you ask me again, "
    "or call reception on 01234 567890?"
)


def _text(content: str | list[dict] | None) -> str:
    """Flatten an OpenAI content field to plain text."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        ]
        return " ".join(part for part in parts if part).strip()
    return ""


def _split_turn(
    messages: list[ChatMessage],
) -> tuple[str, list[tuple[str, str]]]:
    """Last user message as the question, everything before it as history.

    The agent also sends a system prompt and possibly tool messages; only
    user/assistant text belongs in our prompt. History is capped to the same
    number of turns ``/chat`` uses, for the same reason: enough for follow-ups,
    not enough to drown the retrieved context.
    """
    last_user = None
    for index, message in enumerate(messages):
        if message.role == "user" and _text(message.content):
            last_user = index

    if last_user is None:
        return "", []

    question = _text(messages[last_user].content)
    history = [
        (message.role, text)
        for message in messages[:last_user]
        if message.role in ("user", "assistant") and (text := _text(message.content))
    ]
    return question, history[-HISTORY_LIMIT:]


def _chunk(model: str, content: str, finish_reason: str | None = None) -> str:
    payload = {
        "id": "chatcmpl-clinic",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {"content": content} if content else {},
                "finish_reason": finish_reason,
            }
        ],
    }
    return f"data: {json.dumps(payload)}\n\n"


@router.post(
    "/v1/chat/completions",
    dependencies=[Depends(require_agent_secret)],
    response_class=StreamingResponse,
)
def chat_completions(
    payload: ChatCompletionRequest,
    assistant: Assistant,
) -> StreamingResponse:
    """Answer one agent turn as server-sent events.

    A sync generator on purpose: the chain blocks (Qdrant, the model), and
    Starlette iterates sync generators in a thread pool. An async def here
    would block the event loop instead, which on a single worker means the
    whole demo stalls during one answer.
    """
    question, history = _split_turn(payload.messages)
    if not question:
        raise HTTPException(status_code=422, detail="No user message in the request")

    def stream() -> Iterator[str]:
        yield _chunk(payload.model, BUFFER_PHRASE)
        try:
            answer = assistant.answer(question, history=history)
        except Exception:
            logger.exception("agent turn failed question=%r", question)
            yield _chunk(payload.model, FAILURE_ANSWER)
        else:
            # The sources are not spoken; they are logged so a surprising answer
            # in a demo can be traced to the document it came from.
            logger.info(
                "agent turn grounded=%s sources=%s",
                answer.grounded,
                [source.section for source in answer.sources],
            )
            yield _chunk(payload.model, answer.text)
        yield _chunk(payload.model, "", finish_reason="stop")
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            # Tells nginx-style proxies not to sit on the chunks. Harmless
            # behind Caddy, which streams by default.
            "X-Accel-Buffering": "no",
        },
    )
