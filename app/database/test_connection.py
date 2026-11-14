"""Quick manual check that Supabase credentials and the schema are wired up.

Run with:  uv run python -m app.database.test_connection
"""

from app.database.client import get_supabase


def test_connection() -> None:
    client = get_supabase()

    sessions = client.table("sessions").select("id").limit(1).execute()
    messages = client.table("messages").select("id").limit(1).execute()

    print("Supabase connection OK")
    print(f"  sessions table reachable (rows read: {len(sessions.data)})")
    print(f"  messages table reachable (rows read: {len(messages.data)})")


if __name__ == "__main__":
    test_connection()
