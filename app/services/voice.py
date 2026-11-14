"""ElevenLabs speech-to-text and text-to-speech.

Two HTTP calls, no SDK on purpose: the SDK would hide the request shapes, and
the shapes are the interesting part. Audio goes up as multipart form data, the
transcript comes back as JSON, and speech comes back as MP3 bytes.

Both calls are blocking, which is fine here because the route that uses them is
a sync ``def`` and therefore runs in FastAPI's thread pool.
"""

import logging

import httpx

from app.core.config import settings

BASE_URL = "https://api.elevenlabs.io"

logger = logging.getLogger(__name__)


class VoiceNotConfigured(RuntimeError):
    """No API key, so speech cannot be attempted at all."""


class VoiceError(RuntimeError):
    """ElevenLabs was reached but refused, or could not be reached."""


class ElevenLabsClient:
    def __init__(self, api_key: str, base_url: str = BASE_URL, timeout: float = 60.0) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def _post(self, path: str, **kwargs) -> httpx.Response:
        try:
            response = httpx.post(
                f"{self._base_url}{path}",
                headers={"xi-api-key": self._api_key},
                timeout=self._timeout,
                **kwargs,
            )
        except httpx.HTTPError as exc:
            raise VoiceError(f"could not reach ElevenLabs: {exc}") from exc

        if response.status_code >= 400:
            # The body usually explains the refusal (bad model id, no credits,
            # unsupported format). Truncated because it can be a long JSON dump.
            raise VoiceError(f"ElevenLabs returned {response.status_code}: {response.text[:200]}")
        return response

    def transcribe(self, audio: bytes, filename: str, content_type: str) -> str:
        """Audio bytes -> text. Returns an empty string if nothing was said."""
        response = self._post(
            "/v1/speech-to-text",
            files={"file": (filename, audio, content_type)},
            data={
                "model_id": settings.ELEVENLABS_STT_MODEL,
                # Otherwise laughter, coughs and doorbells come back inline as
                # "(laughter)" and end up in the prompt.
                "tag_audio_events": "false",
            },
        )
        return (response.json().get("text") or "").strip()

    def synthesize(self, text: str) -> bytes:
        """Text -> MP3 bytes. The voice and model come from settings."""
        response = self._post(
            f"/v1/text-to-speech/{settings.ELEVENLABS_VOICE_ID}",
            params={"output_format": "mp3_44100_128"},
            json={
                "text": text,
                "model_id": settings.ELEVENLABS_TTS_MODEL,
                # Flash v2.5 disables number normalisation to stay fast, so
                # "01234 567890", "08:30" and "999" get read as digits. A clinic
                # answer is mostly numbers, so turn it back on.
                "apply_text_normalization": "on",
            },
        )
        return response.content
