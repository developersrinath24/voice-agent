import base64

from app.core.config import settings
from app.services.voice import VoiceError

QUESTION = "How long does a repeat prescription take?"


def send(client, audio: bytes = b"fake-webm-bytes", content_type: str = "audio/webm", form=None):
    return client.post(
        "/voice/turn",
        files={"file": ("question.webm", audio, content_type)},
        data=form or {},
    )


def test_voice_turn_goes_speech_to_answer_to_speech(client, fake_assistant, fake_voice):
    response = send(client)
    assert response.status_code == 200

    body = response.json()
    assert body["transcript"] == QUESTION
    assert body["response"] == fake_assistant.text
    assert body["grounded"] is True
    assert body["audio_mime"] == "audio/mpeg"
    assert base64.b64decode(body["audio_base64"]) == fake_voice.audio

    # The transcript is what the chain was asked, and the answer is what was spoken.
    assert fake_assistant.calls[0][0] == QUESTION
    assert fake_voice.spoken == [fake_assistant.text]


def test_voice_turn_reports_where_the_time_went(client):
    timings = send(client).json()["timings_ms"]
    assert set(timings) == {"transcribe", "answer", "speak"}
    assert all(isinstance(value, int) and value >= 0 for value in timings.values())


def test_voice_turn_stores_both_sides_of_the_conversation(client, fake_supabase):
    body = send(client).json()
    session_id = body["session_id"]

    stored = [(m["role"], m["content"]) for m in fake_supabase.store["messages"]]
    assert stored == [("user", QUESTION), ("assistant", body["response"])]
    assert all(m["session_id"] == session_id for m in fake_supabase.store["messages"])


def test_voice_turn_continues_a_session_and_sends_history(client, fake_assistant):
    first = send(client).json()

    second = send(client, form={"session_id": first["session_id"]}).json()
    assert second["session_id"] == first["session_id"]

    _, history = fake_assistant.calls[-1]
    assert history == [("user", QUESTION), ("assistant", fake_assistant.text)]


def test_voice_turn_rejects_unknown_session(client):
    response = send(client, form={"session_id": "00000000-0000-0000-0000-000000000000"})
    assert response.status_code == 404


def test_voice_turn_rejects_non_audio_uploads(client):
    assert send(client, content_type="text/plain").status_code == 415


def test_voice_turn_accepts_media_recorder_content_type(client):
    """Chrome sends audio/webm;codecs=opus, so the codec suffix must not matter."""
    assert send(client, content_type="audio/webm;codecs=opus").status_code == 200


def test_voice_turn_rejects_an_empty_recording(client):
    assert send(client, audio=b"").status_code == 422


def test_voice_turn_rejects_an_oversized_recording(client, monkeypatch):
    monkeypatch.setattr(settings, "VOICE_MAX_UPLOAD_BYTES", 4)
    assert send(client, audio=b"far-too-many-bytes").status_code == 413


def test_voice_turn_rejects_silence(client, fake_voice):
    fake_voice.transcript = "   "
    assert send(client).status_code == 422


def test_voice_turn_creates_no_session_when_transcription_fails(
    client, fake_supabase, fake_voice, monkeypatch
):
    def boom(*args, **kwargs):
        raise VoiceError("ElevenLabs returned 401: invalid api key")

    monkeypatch.setattr(fake_voice, "transcribe", boom)

    assert send(client).status_code == 502
    assert fake_supabase.store["sessions"] == []


def test_voice_turn_keeps_the_answer_when_speech_fails(
    client, fake_supabase, fake_assistant, fake_voice, monkeypatch
):
    def boom(*args, **kwargs):
        raise VoiceError("ElevenLabs returned 429: rate limited")

    monkeypatch.setattr(fake_voice, "synthesize", boom)

    assert send(client).status_code == 502

    stored = [(m["role"], m["content"]) for m in fake_supabase.store["messages"]]
    assert stored == [("user", QUESTION), ("assistant", fake_assistant.text)]


def test_voice_turn_returns_503_when_elevenlabs_is_not_configured(client, monkeypatch):
    from app.api.deps import get_voice_client, voice_client
    from app.main import app

    # Drop the fake so the real dependency runs against an empty key.
    app.dependency_overrides.pop(voice_client, None)
    monkeypatch.setattr(settings, "ELEVENLABS_API_KEY", "")
    get_voice_client.cache_clear()

    response = send(client)

    assert response.status_code == 503
    assert "ELEVENLABS_API_KEY" in response.json()["detail"]
