import pytest

from app.core.config import settings
from app.services.voice import VoiceError


@pytest.fixture(autouse=True)
def agent_configured(monkeypatch):
    """Pretend the dashboard agent exists; the individual tests override it."""
    monkeypatch.setattr(settings, "ELEVENLABS_AGENT_ID", "agent_test_123")


def test_session_returns_a_signed_url_and_one_fewer_call(client, fake_voice, fake_budget):
    response = client.get("/voice/session")
    assert response.status_code == 200

    body = response.json()
    assert body["signed_url"].startswith("wss://")
    assert body["max_seconds"] == settings.VOICE_MAX_CALL_SECONDS
    assert body["remaining_calls"] == settings.VOICE_DAILY_CALL_LIMIT - 1

    # The configured agent was the one signed for, not something from the request.
    assert fake_voice.signed_for == ["agent_test_123"]
    assert fake_budget.remaining() == settings.VOICE_DAILY_CALL_LIMIT - 1


def test_session_refuses_when_no_agent_is_configured(client, fake_voice, monkeypatch):
    monkeypatch.setattr(settings, "ELEVENLABS_AGENT_ID", "")

    response = client.get("/voice/session")
    assert response.status_code == 503
    assert "ELEVENLABS_AGENT_ID" in response.json()["detail"]
    assert fake_voice.signed_for == []


def test_session_stops_at_the_daily_allowance(client, fake_voice, fake_budget):
    for _ in range(settings.VOICE_DAILY_CALL_LIMIT):
        fake_budget.take()

    response = client.get("/voice/session")
    assert response.status_code == 429
    assert "today" in response.json()["detail"]
    # No signed URL, so no credits: the refusal happens before the API call.
    assert fake_voice.signed_for == []


def test_session_does_not_count_a_failed_handshake(client, fake_voice, fake_budget):
    fake_voice.signed_url_error = VoiceError("ElevenLabs returned 401: bad key")

    response = client.get("/voice/session")
    assert response.status_code == 502
    assert "bad key" in response.json()["detail"]
    assert fake_budget.remaining() == settings.VOICE_DAILY_CALL_LIMIT


def test_session_needs_the_api_key_when_one_is_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "shared-secret")

    assert client.get("/voice/session").status_code == 401
    ok = client.get("/voice/session", headers={"X-API-Key": "shared-secret"})
    assert ok.status_code == 200
