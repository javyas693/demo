from __future__ import annotations

from dataclasses import asdict, is_dataclass
from decimal import Decimal
import hashlib
import json
from typing import Any, Mapping, Sequence


class IntegrityError(ValueError):
    pass


def _to_primitive(obj: Any) -> Any:
    # Convert dataclasses / Decimal / dates to stable primitives
    if isinstance(obj, Decimal):
        return str(obj)
    if is_dataclass(obj):
        return {k: _to_primitive(v) for k, v in asdict(obj).items()}
    if isinstance(obj, Mapping):
        return {str(k): _to_primitive(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_primitive(x) for x in obj]
    # date/datetime
    if hasattr(obj, "isoformat"):
        try:
            return obj.isoformat()
        except Exception:
            pass
    return obj


def stable_hash(obj: Any) -> str:
    prim = _to_primitive(obj)
    blob = json.dumps(prim, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def validate_portfolio_state(state: Any) -> None:
    """
    Patch-5 integrity gate.
    Keep it strict but not opinionated about your engine internals.
    We only assert invariants that should ALWAYS hold.
    """
    # Basic expected attributes
    for attr in ("id", "as_of"):
        if not hasattr(state, attr):
            raise IntegrityError(f"PortfolioState missing required field: {attr}")

    # If you have cash + positions, enforce non-negative cash & sane positions
    if hasattr(state, "cash"):
        cash = getattr(state, "cash")
        try:
            if Decimal(str(cash)) < Decimal("0"):
                raise IntegrityError(f"Cash is negative: {cash}")
        except Exception:
            # if cash is not numeric, that’s also bad
            raise IntegrityError(f"Cash is not numeric: {cash}")

    if hasattr(state, "positions"):
        positions = getattr(state, "positions") or []
        if not isinstance(positions, Sequence):
            raise IntegrityError("positions must be a sequence")

        for p in positions:
            for a in ("symbol", "sleeve", "qty"):
                if not hasattr(p, a):
                    raise IntegrityError(f"Position missing required field: {a}")
            qty = getattr(p, "qty")
            try:
                if Decimal(str(qty)) < Decimal("0"):
                    raise IntegrityError(f"Negative qty not allowed (unless shorting supported): {qty}")
            except Exception:
                raise IntegrityError(f"qty not numeric: {qty}")


def validate_frontier_payload(frontier: Any) -> None:
    """
    Validates frontier structure. Adjust to your internal representation.
    """
    # Common patterns: frontier.points list, or frontier is list of points
    points = None
    if isinstance(frontier, Sequence) and not isinstance(frontier, (str, bytes, bytearray)):
        points = frontier
    elif hasattr(frontier, "points"):
        points = getattr(frontier, "points")

    if points is None:
        raise IntegrityError("Frontier has no points")

    if len(points) < 2:
        raise IntegrityError("Frontier must have at least 2 points")

    # Enforce monotonic-ish sanity if you track risk/return
    # (Don’t overfit: just check required keys exist)
    sample = points[0]
    # Accept dict or dataclass-like point
    def has_field(obj: Any, name: str) -> bool:
        return (isinstance(obj, Mapping) and name in obj) or hasattr(obj, name)

    for field in ("vol", "exp_return", "weights"):
        if not has_field(sample, field):
            # If your point uses different names, change here once.
            raise IntegrityError(f"Frontier point missing field: {field}")