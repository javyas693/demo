import json
from datetime import datetime, timezone
from ai_advisory.db.database import get_db


def save_profile(profile_dict: dict) -> None:
    """Overwrite the single client profile row."""
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute("DELETE FROM client_profile")
        conn.execute("""
            INSERT INTO client_profile (id, updated_at, data)
            VALUES (1, ?, ?)
        """, (now, json.dumps(profile_dict)))


def load_profile() -> dict | None:
    """Load the client profile. Returns None if not yet stored."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT data FROM client_profile WHERE id=1"
        ).fetchone()
    if not row:
        return None
    return json.loads(row["data"])
