"""Data access for sessions and messages.

All queries take an explicit Supabase client, which keeps this layer easy to
fake in tests.

Column lists are explicit rather than ``select("*")`` so an unexpected schema
change fails loudly here instead of quietly leaking columns into an API
response.
"""

from typing import Any
from uuid import UUID

from supabase import Client

SESSIONS = "sessions"
MESSAGES = "messages"

SESSION_COLUMNS = "id,status,created_at,updated_at"
MESSAGE_COLUMNS = "id,session_id,role,content,created_at"


def create_session(client: Client) -> dict[str, Any]:
    result = client.table(SESSIONS).insert({"status": "active"}).execute()
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
) -> dict[str, Any]:
    result = (
        client.table(MESSAGES)
        .insert({"session_id": str(session_id), "role": role, "content": content})
        .execute()
    )
    return result.data[0]


def end_session(client: Client, session_id: UUID) -> dict[str, Any] | None:
    result = client.table(SESSIONS).update({"status": "ended"}).eq("id", str(session_id)).execute()
    return result.data[0] if result.data else None
