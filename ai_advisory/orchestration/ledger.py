from typing import Dict, Any, List

# Global in-memory event store
ledger: List[Dict[str, Any]] = []

def record_event(event: Dict[str, Any]) -> None:
    """Append event to ledger list."""
    ledger.append(event)

def get_ledger() -> List[Dict[str, Any]]:
    """Returns full event list."""
    return ledger
