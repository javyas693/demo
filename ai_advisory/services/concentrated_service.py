from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Optional

from ..services.http_models import ClientProfile, PositionIn


def _pick_concentrated_position(profile: ClientProfile) -> Optional[PositionIn]:
    # MVP: choose the largest position by shares (price unknown)
    if not profile.positions:
        return None
    return max(profile.positions, key=lambda p: float(p.shares))


def _is_pandas_obj(x: Any) -> bool:
    try:
        import pandas as pd  # type: ignore
        return isinstance(x, (pd.DataFrame, pd.Series))
    except Exception:
        return False


def _is_numpy_scalar(x: Any) -> bool:
    try:
        import numpy as np  # type: ignore
        return isinstance(x, np.generic)
    except Exception:
        return False


def _sanitize_for_json(obj: Any) -> Any:
    """
    Recursively sanitize a result tree so FastAPI/Pydantic can JSON serialize it.

    Rules:
      - Remove any key named "time_series" anywhere.
      - Drop pandas objects (DataFrame/Series) entirely.
      - Convert Decimal -> float
      - Convert date/datetime -> ISO string
      - Convert numpy scalars -> Python scalars
      - Recurse dict/list/tuple
    """
    if obj is None:
        return None

    # Drop pandas objects entirely (we won't return them)
    if _is_pandas_obj(obj):
        return None

    # Normalize numpy scalars
    if _is_numpy_scalar(obj):
        try:
            return obj.item()
        except Exception:
            return float(obj)

    # Normalize decimals
    if isinstance(obj, Decimal):
        return float(obj)

    # Normalize dates
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()

    if isinstance(obj, dict):
        clean: dict[str, Any] = {}
        for k, v in obj.items():
            if k == "time_series":
                continue

            sv = _sanitize_for_json(v)

            # If the value sanitized to None because it was a DataFrame/Series,
            # we drop the key (instead of returning null).
            if sv is None and _is_pandas_obj(v):
                continue

            clean[str(k)] = sv
        return clean

    if isinstance(obj, (list, tuple)):
        out = []
        for v in obj:
            sv = _sanitize_for_json(v)
            # Drop pandas items from sequences too
            if sv is None and _is_pandas_obj(v):
                continue
            out.append(sv)
        return out

    # primitives (str/int/float/bool) or already-serializable types
    return obj


def propose_concentrated(profile: ClientProfile) -> Dict[str, Any]:
    # IMPORTANT: this import path must match where you actually placed strategy_unwind.py
    from ai_advisory.strategy.strategy_unwind import run_strategy_comparison

    pos = _pick_concentrated_position(profile)
    if pos is None:
        return {"error": "No positions in profile."}

    start_date = "2020-01-01"
    end_date = str(date.today())

    raw = run_strategy_comparison(
        ticker=pos.symbol,
        start_date=start_date,
        end_date=end_date,
        initial_shares=int(pos.shares),
        cost_basis=float(pos.cost_basis) if pos.cost_basis is not None else None,
        share_reduction_trigger_pct=0.10,
        enable_tax_loss_harvest=True,
    )

    return _sanitize_for_json(raw)