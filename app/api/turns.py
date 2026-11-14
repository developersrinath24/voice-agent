"""Setup shared by every conversational turn.

``/chat`` and ``/voice/turn`` do the same three things before any model work:
resolve the session (or open one), read recent history for the prompt, and
record what the user said. Keeping that in one place means the two entry points
cannot drift on the rules that matter — 404 for an unknown session, 409 for an
ended one, and the same history cap.
"""

from uuid import UUID

from fastapi import HTTPException
from supabase import Client

from app.database import repositories as repo

# Enough history for "and on Saturday?" follow-ups, short enough to keep the
# prompt cheap and the context focused.
HISTORY_LIMIT = 10


def begin_turn(
    client: Client,
    session_id: UUID | None,
    user_message: str,
) -> tuple[UUID, list[tuple[str, str]]]:
    """Resolve the session, load its recent history, and store the user turn.

    The message is stored *before* the model is called: if generation fails, the
    transcript still shows what the patient asked, which is what a receptionist
    reviewing the log would need.
    """
    if session_id is not None:
        session = repo.get_session(client, session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        if session["status"] != "active":
            raise HTTPException(status_code=409, detail="Session has already ended")
    else:
        session = repo.create_session(client)

    resolved = UUID(session["id"])
    history = [
        (row["role"], row["content"])
        for row in repo.recent_messages(client, resolved, limit=HISTORY_LIMIT)
    ]
    repo.add_message(client, resolved, "user", user_message)
    return resolved, history
