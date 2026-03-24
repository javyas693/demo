from datetime import datetime, timezone
from ai_advisory.db.database import get_db


def append_message(conversation_id: str, role: str, content: str) -> None:
    """Append a single message to chat history."""
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute("""
            INSERT INTO chat_history (conversation_id, role, content, created_at)
            VALUES (?, ?, ?, ?)
        """, (conversation_id, role, content, now))


def load_conversation(conversation_id: str) -> list:
    """Load all messages for a conversation in chronological order."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT role, content, created_at
            FROM chat_history
            WHERE conversation_id=?
            ORDER BY created_at ASC
        """, (conversation_id,)).fetchall()
    return [
        {"role": r["role"], "content": r["content"], "created_at": r["created_at"]}
        for r in rows
    ]


def load_all_conversations() -> dict:
    """Load all conversations grouped by conversation_id."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT conversation_id, role, content, created_at
            FROM chat_history
            ORDER BY conversation_id, created_at ASC
        """).fetchall()
    result = {}
    for r in rows:
        cid = r["conversation_id"]
        if cid not in result:
            result[cid] = []
        result[cid].append({
            "role":       r["role"],
            "content":    r["content"],
            "created_at": r["created_at"],
        })
    return result


def delete_conversation(conversation_id: str) -> None:
    """Hard delete all messages for a conversation."""
    with get_db() as conn:
        conn.execute(
            "DELETE FROM chat_history WHERE conversation_id=?",
            (conversation_id,)
        )
