import json
from datetime import datetime, timezone
from ai_advisory.db.database import get_db


def log_gate_override_run(gate_overrides: dict, monthly_intelligence: list) -> None:
    """
    Append-only log of every what-if run with gate overrides.
    Stores summary metrics for quick inspection without loading full intelligence blob.
    """
    now = datetime.now(timezone.utc).isoformat()

    total_shares     = sum(m.get("shares_to_sell", 0) for m in monthly_intelligence)
    final_value      = monthly_intelligence[-1].get("total_portfolio_value", 0) if monthly_intelligence else 0
    months_unblocked = sum(1 for m in monthly_intelligence if m.get("enable_unwind", False))

    summary = {
        "total_shares_sold":      total_shares,
        "final_portfolio_value":  final_value,
        "months_unblocked":       months_unblocked,
        "month_count":            len(monthly_intelligence),
    }

    with get_db() as conn:
        conn.execute("""
            INSERT INTO gate_override_history (created_at, gate_overrides, summary_metrics)
            VALUES (?, ?, ?)
        """, (now, json.dumps(gate_overrides), json.dumps(summary)))


def load_gate_override_history() -> list:
    """Returns all gate override runs, most recent first."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT id, created_at, gate_overrides, summary_metrics
            FROM gate_override_history
            ORDER BY created_at DESC
        """).fetchall()
    return [
        {
            "id":              r["id"],
            "created_at":      r["created_at"],
            "gate_overrides":  json.loads(r["gate_overrides"]),
            "summary_metrics": json.loads(r["summary_metrics"]),
        }
        for r in rows
    ]
