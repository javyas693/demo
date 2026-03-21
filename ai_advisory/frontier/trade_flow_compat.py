"""
trade_flow_compat.py

Thin bridge between the frontier store and the portfolio orchestrator.
The orchestrator only needs one thing: {ticker: weight} for a given risk score.
This keeps the orchestrator decoupled from FrontierResult internals.
"""
from __future__ import annotations

from typing import Dict

from .store.fs_store import FileSystemFrontierStore
from .weights import weights_tuple_to_dict

_WEIGHT_THRESHOLD = 1e-4


def weights_for_risk_score(
    store: FileSystemFrontierStore,
    as_of: str,
    model_id: str,
    risk_score: int,
) -> Dict[str, float]:
    """
    Look up the optimized weights for a given risk_score (1–100) from the
    persisted frontier.

    Maps the 1–100 risk score onto the sampled frontier points by linear
    interpolation of the index (same logic as trade_flow.propose_from_latest_frontier).

    Returns {ticker: weight} with near-zero weights stripped and remainder
    renormalized to sum exactly to 1.0.
    """
    fv = store.get_latest(as_of, model_id)
    if not fv:
        raise ValueError(f"No latest frontier for as_of={as_of} model_id={model_id}")

    fr = store.get(as_of, fv)
    if not fr.points_sampled:
        raise ValueError(f"Frontier {fv} has no sampled points")

    n = len(fr.points_sampled)
    bounded = max(1, min(100, risk_score))
    idx = 0 if n == 1 else int(round((bounded - 1) / 99.0 * (n - 1)))

    point = fr.points_sampled[idx]
    assets = tuple(fr.assets)

    if isinstance(point.weights, dict):
        w_map = {str(k): float(v) for k, v in point.weights.items()}
    else:
        w_map = weights_tuple_to_dict(
            tuple(float(x) for x in point.weights), assets
        )

    # Strip near-zero weights and renormalize
    w_map = {k: v for k, v in w_map.items() if v > _WEIGHT_THRESHOLD}
    total = sum(w_map.values())
    if total <= 0:
        raise ValueError(f"All weights near-zero for risk_score={risk_score}")

    return {k: v / total for k, v in w_map.items()}
