"""The slice of the OpenAI chat-completions request this endpoint reads.

ElevenLabs' custom LLM integration sends the standard shape (plus its own keys),
so the models are permissive on purpose: ``extra="allow"`` keeps an unexpected
field from turning into a 422 in the middle of a live call.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    role: str
    # OpenAI allows a string or a list of content parts. ElevenLabs sends text,
    # but accepting both keeps the endpoint honest about the contract.
    content: str | list[dict[str, Any]] | None = None


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str = "clinic-rag"
    messages: list[ChatMessage] = Field(default_factory=list)
    stream: bool = True
    stream_options: dict[str, Any] | None = None


class ChatCompletionChunk(BaseModel):
    """Only used to document the response shape in OpenAPI.

    The endpoint writes chunks by hand because the important detail is the SSE
    framing around them, which a response model would hide.
    """

    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int
    model: str
    choices: list[dict[str, Any]]
