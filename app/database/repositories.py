"""Data access for sessions and messages.

All queries take an explicit Supabase client, which keeps this layer easy to
fake in tests.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from supabase import Client

SESSIONS = "sessions"
MESSAGES = "messages"

SESSION_COLUMNS = "id,channel,status,created_at,updated_at,ended_at"
MESSAGE_COLUMNS = "id,session_id,role,content,created_at,latency_ms,model"


def create_session(client: Client, channel: str = "web") -> dict[str, Any]:
    result = client.table(SESSIONS).insert({"channel": channel}).execute()
    return result.data[0]


def get_session(client: Client, session_id: UUID) -> dict[str, Any] | None:
    result = (
        client.table(SESSIONS).select(SESSION_COLUMNS).eq("id", str(session_id)).limit(1).execute()
    )
    return result.data[0] if result.data else None


def count_messages(client: Client, session_id: UUID) -> int:
    result = (
        client.table(MESSAGES)
        .select("id", count="exact")
        .eq("session_id", str(session_id))
        .execute()
    )
    return result.count or 0


def list_messages(client: Client, session_id: UUID, limit: int = 50) -> list[dict[str, Any]]:
    result = (
        client.table(MESSAGES)
        .select(MESSAGE_COLUMNS)
        .eq("session_id", str(session_id))
        .order("created_at")
        .limit(limit)
        .execute()
    )
    return result.data or []


def add_message(
    client: Client,
    session_id: UUID,
    role: str,
    content: str,
    *,
    latency_ms: int | None = None,
    model: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "session_id": str(session_id),
        "role": role,
        "content": content,
    }
    if latency_ms is not None:
        payload["latency_ms"] = latency_ms
    if model is not None:
        payload["model"] = model
    if metadata is not None:
        payload["metadata"] = metadata

    result = client.table(MESSAGES).insert(payload).execute()
    return result.data[0]


def end_session(client: Client, session_id: UUID) -> dict[str, Any] | None:
    result = (
        client.table(SESSIONS)
        .update(
            {
                "status": "ended",
                "ended_at": datetime.now(UTC).isoformat(),
            }
        )
        .eq("id", str(session_id))
        .execute()
    )
    return result.data[0] if result.data else None
