import json
from datetime import datetime, timezone
from ai_advisory.db.database import get_db
from ai_advisory.services.concentrated_service import _sanitize_for_json


def save_simulation(inputs: dict, timeline: list, monthly_intelligence: list) -> None:
    """Overwrite the single simulation row — latest run wins."""
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute("DELETE FROM simulations")
        conn.execute("""
            INSERT INTO simulations (id, created_at, inputs, timeline, monthly_intelligence)
            VALUES (1, ?, ?, ?, ?)
        """, (
            now,
            json.dumps(_sanitize_for_json(inputs)),
            json.dumps(_sanitize_for_json(timeline)),
            json.dumps(_sanitize_for_json(monthly_intelligence)),
        ))


def load_simulation() -> dict | None:
    """Load the latest simulation run. Returns None if no run stored yet."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM simulations WHERE id=1").fetchone()
    if not row:
        return None
    return {
        "created_at":           row["created_at"],
        "inputs":               json.loads(row["inputs"]),
        "timeline":             json.loads(row["timeline"]),
        "monthly_intelligence": json.loads(row["monthly_intelligence"]),
    }


def save_whatif(gate_overrides: dict, monthly_intelligence: list) -> None:
    """Overwrite the single what-if row — latest run wins."""
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute("DELETE FROM simulation_whatif")
        conn.execute("""
            INSERT INTO simulation_whatif (id, created_at, gate_overrides, monthly_intelligence)
            VALUES (1, ?, ?, ?)
        """, (
            now,
            json.dumps(gate_overrides),
            json.dumps(_sanitize_for_json(monthly_intelligence)),
        ))


def load_whatif() -> dict | None:
    """Load the latest what-if run. Returns None if none stored yet."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM simulation_whatif WHERE id=1").fetchone()
    if not row:
        return None
    return {
        "created_at":           row["created_at"],
        "gate_overrides":       json.loads(row["gate_overrides"]),
        "monthly_intelligence": json.loads(row["monthly_intelligence"]),
    }
