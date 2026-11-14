"""Pin the exact requests we send to ElevenLabs.

These assertions exist because two of these fields are easy to lose and hard to
notice: without ``tag_audio_events=false`` the transcript picks up "(laughter)",
and Flash v2.5 does not normalise numbers unless asked, so phone numbers and
opening times get read out digit by digit.
"""

import httpx
import pytest

from app.core.config import settings
from app.services.voice import ElevenLabsClient, VoiceError


class Recorder:
    """Captures the call and returns whatever response the test prepared."""

    def __init__(self, response: httpx.Response) -> None:
        self.response = response
        self.calls: list[dict] = []

    def __call__(self, url, *, headers=None, timeout=None, **kwargs) -> httpx.Response:
        self.calls.append({"url": url, "headers": headers, "options": kwargs})
        return self.response


@pytest.fixture
def client() -> ElevenLabsClient:
    return ElevenLabsClient("test-key")


def test_transcribe_sends_the_audio_as_multipart(monkeypatch, client):
    recorder = Recorder(httpx.Response(200, json={"text": "  how do I book  "}))
    monkeypatch.setattr("app.services.voice.httpx.post", recorder)

    assert client.transcribe(b"webm-bytes", "question.webm", "audio/webm") == "how do I book"

    call = recorder.calls[0]
    assert call["url"].endswith("/v1/speech-to-text")
    assert call["headers"]["xi-api-key"] == "test-key"
    assert call["options"]["files"] == {
        "file": ("question.webm", b"webm-bytes", "audio/webm"),
    }
    assert call["options"]["data"]["model_id"] == "scribe_v3"
    assert call["options"]["data"]["tag_audio_events"] == "false"


def test_transcribe_tolerates_a_response_without_text(monkeypatch, client):
    monkeypatch.setattr("app.services.voice.httpx.post", Recorder(httpx.Response(200, json={})))
    assert client.transcribe(b"x", "q.webm", "audio/webm") == ""


def test_synthesize_asks_for_number_normalisation(monkeypatch, client):
    recorder = Recorder(httpx.Response(200, content=b"ID3-mp3"))
    monkeypatch.setattr("app.services.voice.httpx.post", recorder)

    assert client.synthesize("Ring 01234 567890") == b"ID3-mp3"

    call = recorder.calls[0]
    assert "/v1/text-to-speech/" in call["url"]
    assert call["url"].endswith(f"/v1/text-to-speech/{settings.ELEVENLABS_VOICE_ID}")
    assert call["options"]["json"]["apply_text_normalization"] == "on"
    assert call["options"]["json"]["text"] == "Ring 01234 567890"
    assert call["options"]["params"]["output_format"] == "mp3_44100_128"


def test_api_errors_become_voice_errors_without_leaking_the_key(monkeypatch, client):
    recorder = Recorder(httpx.Response(401, json={"detail": "invalid_api_key"}))
    monkeypatch.setattr("app.services.voice.httpx.post", recorder)

    with pytest.raises(VoiceError) as raised:
        client.synthesize("hello")

    assert "401" in str(raised.value)
    assert "test-key" not in str(raised.value)


def test_network_failures_become_voice_errors(monkeypatch, client):
    def explode(*args, **kwargs):
        raise httpx.ConnectError("no route to host")

    monkeypatch.setattr("app.services.voice.httpx.post", explode)

    with pytest.raises(VoiceError, match="could not reach ElevenLabs"):
        client.transcribe(b"x", "q.webm", "audio/webm")
