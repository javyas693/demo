from __future__ import annotations

from typing import Iterable, List, Sequence

from .results import FrontierPoint
from .tolerances import ZERO_VOL_TOL, DOMINANCE_EPS_RISK, DOMINANCE_EPS_RETURN, DUP_TOL_RISK, DUP_TOL_RETURN


def add_sharpe(points: Sequence[FrontierPoint], rf_annual: float) -> List[FrontierPoint]:
    out: List[FrontierPoint] = []
    for p in points:
        if p.vol is None or p.vol <= ZERO_VOL_TOL:
            out.append(FrontierPoint(
                risk_score=p.risk_score,
                exp_return=p.exp_return,
                vol=p.vol,
                weights=p.weights,
                excess_return=None,
                sharpe=None,
            ))
            continue
        ex = float(p.exp_return - rf_annual)
        sh = float(ex / p.vol)
        out.append(FrontierPoint(
            risk_score=p.risk_score,
            exp_return=p.exp_return,
            vol=p.vol,
            weights=p.weights,
            excess_return=ex,
            sharpe=sh,
        ))
    return out


def pareto_filter(points: Sequence[FrontierPoint]) -> List[FrontierPoint]:
    """
    Deterministic Pareto filter:
    - Sort by vol asc, then exp_return desc
    - Keep points with strictly improving return envelope (within eps)
    """
    pts = sorted(points, key=lambda p: (p.vol, -p.exp_return))
    kept: List[FrontierPoint] = []
    best_ret = float("-inf")

    for p in pts:
        if not kept:
            kept.append(p)
            best_ret = p.exp_return
            continue

        # dominated if return is not better than the current envelope
        if p.exp_return <= best_ret + DOMINANCE_EPS_RETURN:
            continue

        kept.append(p)
        best_ret = p.exp_return

    return kept


def collapse_duplicates(points: Sequence[FrontierPoint]) -> List[FrontierPoint]:
    """
    Collapse near-duplicates in (vol, exp_return) space deterministically.
    Keep the highest sharpe when duplicates exist, else keep first.
    """
    pts = sorted(points, key=lambda p: (p.vol, -p.exp_return))
    out: List[FrontierPoint] = []

    def better(a: FrontierPoint, b: FrontierPoint) -> FrontierPoint:
        # prefer higher sharpe if both present
        if a.sharpe is not None and b.sharpe is not None:
            return a if a.sharpe >= b.sharpe else b
        if a.sharpe is not None:
            return a
        if b.sharpe is not None:
            return b
        # fallback: higher return, then lower vol
        if a.exp_return != b.exp_return:
            return a if a.exp_return > b.exp_return else b
        return a if a.vol <= b.vol else b

    for p in pts:
        if not out:
            out.append(p)
            continue
        last = out[-1]
        if abs(p.vol - last.vol) <= DUP_TOL_RISK and abs(p.exp_return - last.exp_return) <= DUP_TOL_RETURN:
            out[-1] = better(out[-1], p)
        else:
            out.append(p)

    return out