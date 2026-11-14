from uuid import UUID

from app.core.config import settings


def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["version"] == settings.APP_VERSION


def test_health_lists_integration_flags(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert set(body["configured"]) == {"supabase", "qdrant", "deepseek", "gemini", "elevenlabs"}


def test_chat_starts_a_session_and_stores_both_turns(client, fake_supabase):
    response = client.post("/chat", json={"message": "What are your opening hours?"})
    assert response.status_code == 200

    body = response.json()
    session_id = UUID(body["session_id"])
    assert body["message_count"] == 2
    assert "not connected yet" in body["response"]

    stored_roles = [m["role"] for m in fake_supabase.store["messages"]]
    assert stored_roles == ["user", "assistant"]
    assert all(m["session_id"] == str(session_id) for m in fake_supabase.store["messages"])


def test_chat_continues_an_existing_session(client, fake_supabase):
    first = client.post("/chat", json={"message": "hello"}).json()
    second = client.post(
        "/chat", json={"message": "and again", "session_id": first["session_id"]}
    ).json()

    assert second["session_id"] == first["session_id"]
    assert second["message_count"] == 4
    assert len(fake_supabase.store["sessions"]) == 1


def test_chat_rejects_unknown_session(client):
    response = client.post(
        "/chat",
        json={"message": "hi", "session_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 404


def test_chat_rejects_empty_message(client):
    assert client.post("/chat", json={"message": ""}).status_code == 422


def test_chat_rejects_malformed_session_id(client):
    assert client.post("/chat", json={"message": "hi", "session_id": "nope"}).status_code == 422


def test_session_history_round_trip(client):
    created = client.post("/sessions").json()
    session_id = created["session_id"]
    assert created["status"] == "active"
    assert created["message_count"] == 0

    client.post("/chat", json={"message": "I need a repeat prescription", "session_id": session_id})

    messages = client.get(f"/sessions/{session_id}/messages").json()
    assert [m["role"] for m in messages] == ["user", "assistant"]

    ended = client.post(f"/sessions/{session_id}/end").json()
    assert ended["status"] == "ended"

    assert client.post("/chat", json={"message": "hi", "session_id": session_id}).status_code == 409


def test_messages_for_unknown_session_returns_404(client):
    response = client.get("/sessions/00000000-0000-0000-0000-000000000000/messages")
    assert response.status_code == 404


def test_voice_endpoint_reports_not_implemented(client):
    assert client.post("/voice/turn").status_code == 501


def test_supabase_dependency_returns_503_when_not_configured(monkeypatch):
    from fastapi.testclient import TestClient

    from app.database.client import get_supabase
    from app.main import app

    monkeypatch.setattr(settings, "SUPABASE_URL", "")
    monkeypatch.setattr(settings, "SUPABASE_KEY", "")
    get_supabase.cache_clear()

    with TestClient(app) as test_client:
        response = test_client.post("/chat", json={"message": "hi"})

    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]
