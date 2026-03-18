from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Callable, Dict, List, Optional, Tuple

from ai_advisory.core.frontier_status import FrontierStatus
from ai_advisory.frontier.store.fs_store import FileSystemFrontierStore
from ai_advisory.frontier.weights import weights_tuple_to_dict
from ai_advisory.frontier.results import FrontierResult, FrontierPoint

from ai_advisory.allocation.allocate import BuyIntent, allocate_cash_to_model, AllocationError


@dataclass(frozen=True)
class FrontierProposal:
    as_of: str
    model_id: str
    frontier_version: str
    frontier_status: FrontierStatus
    risk_score: int  # 1..N
    assets: Tuple[str, ...]
    target_weights: Dict[str, float]  # ticker -> weight (sums to ~1)
    # optional: snapshot of point metrics for explanation
    exp_return: float
    vol: float
    sharpe: Optional[float] = None


class TradeFlowError(Exception):
    pass


def propose_from_latest_frontier(
    *,
    store: FileSystemFrontierStore,
    as_of: str,
    model_id: str,
    risk_score: int,
) -> FrontierProposal:
    """
    Read-only selection:
      - uses latest frontier for (as_of, model_id)
      - selects points_sampled[risk_score]
      - returns a proposal suitable for chatbot explanation + trade preview

    NOTE: status may be LOCKED (preview ok). Execution requires APPROVED.
    """
    fv = store.get_latest(as_of, model_id)
    if not fv:
        raise TradeFlowError(f"No latest frontier for as_of={as_of} model_id={model_id}")

    status = store.get_status(as_of, fv)
    fr = store.get(as_of, fv)

    if not fr.points_sampled:
        raise TradeFlowError(f"Frontier {fv} has no sampled points")

    n = len(fr.points_sampled)
    
    # Map the UI risk score (1-100) to the available frontier points interpolation indices (0 to n-1)
    bounded_score = max(1, min(100, risk_score))
    if n == 1:
        idx = 0
    else:
        idx = int(round((bounded_score - 1) / 99.0 * (n - 1)))
        
    p: FrontierPoint = fr.points_sampled[idx]

    # weights can be tuple aligned to fr.assets (fs_store returns tuple)
    if isinstance(p.weights, dict):
        w_map = {str(k): float(v) for k, v in p.weights.items()}
        assets = tuple(fr.assets)
    else:
        assets = tuple(fr.assets)
        w_map = weights_tuple_to_dict(tuple(float(x) for x in p.weights), assets)

    # normalize (defensive)
    s = sum(float(v) for v in w_map.values())
    if s > 0:
        w_map = {k: float(v) / s for k, v in w_map.items()}

    return FrontierProposal(
        as_of=as_of,
        model_id=model_id,
        frontier_version=fv,
        frontier_status=status,
        risk_score=risk_score,
        assets=assets,
        target_weights=w_map,
        exp_return=float(getattr(p, "exp_return", 0.0)),
        vol=float(getattr(p, "vol", 0.0)),
        sharpe=float(getattr(p, "sharpe")) if getattr(p, "sharpe", None) is not None else None,
    )


def preview_buys_only(
    *,
    PortfolioState,
    proposal: FrontierProposal,
    price_lookup: Callable[[str], Decimal],
    min_trade_notional: Decimal = Decimal("250.00"),
    allow_fractional: bool = True,
    fractional_dp: int = 6,
) -> List[BuyIntent]:
    """
    Preview buy intents WITHOUT writing to ledger.
    This reuses allocate_cash_to_model by passing a no-op ledger.

    Phase 1 preview is buys-only; sells/rebalance can be added later.
    """
    class _NoOpLedger:
        def buy_fill(self, **kwargs):  # noqa: ANN001
            return None

    # Build a lightweight ModelPortfolio-like adapter
    # allocate_cash_to_model only needs:
    #   - validate()
    #   - normalized_weights()
    #   - name
    class _MP:
        def __init__(self, name: str, weights: Dict[str, float]):
            self.name = name
            self.target_weights = dict(weights)

        def validate(self) -> None:
            if not self.target_weights:
                raise ValueError("Empty target_weights")
            s = sum(float(v) for v in self.target_weights.values())
            if s <= 0:
                raise ValueError("Non-positive weight sum")

        def normalized_weights(self) -> Dict[str, float]:
            s = sum(float(v) for v in self.target_weights.values())
            return {k: float(v) / s for k, v in self.target_weights.items()}

    mp = _MP(
        name=f"frontier:{proposal.model_id}:{proposal.frontier_version}:rs{proposal.risk_score}",
        weights=proposal.target_weights,
    )

    return allocate_cash_to_model(
        PortfolioState=PortfolioState,
        model_portfolio=mp,  # adapter
        price_lookup=price_lookup,
        ledger=_NoOpLedger(),
        as_of=proposal.as_of,
        run_id="preview",
        min_trade_notional=min_trade_notional,
        allow_fractional=allow_fractional,
        fractional_dp=fractional_dp,
        # no gating here; preview is always allowed
    )


def execute_buys_only(
    *,
    PortfolioState,
    proposal: FrontierProposal,
    price_lookup: Callable[[str], Decimal],
    ledger,
    store: FileSystemFrontierStore,
    run_id: str,
    user_id: str = "u_123",
    created_at=None,
    min_trade_notional: Decimal = Decimal("250.00"),
    allow_fractional: bool = True,
    fractional_dp: int = 6,
) -> List[BuyIntent]:
    """
    Execute buy intents via ledger.buy_fill, gated by frontier status == APPROVED.
    Marks frontier as EXECUTED after success.

    Phase 1 execution is buys-only.
    """
    # Gate: must be APPROVED at execution time (fresh read)
    status = store.get_status(proposal.as_of, proposal.frontier_version)
    if status != FrontierStatus.APPROVED:
        raise TradeFlowError(
            f"Execution blocked: frontier_version={proposal.frontier_version} status={status.value}. Must be APPROVED."
        )

    # ModelPortfolio adapter (same as preview)
    class _MP:
        def __init__(self, name: str, weights: Dict[str, float]):
            self.name = name
            self.target_weights = dict(weights)

        def validate(self) -> None:
            if not self.target_weights:
                raise ValueError("Empty target_weights")
            s = sum(float(v) for v in self.target_weights.values())
            if s <= 0:
                raise ValueError("Non-positive weight sum")

        def normalized_weights(self) -> Dict[str, float]:
            s = sum(float(v) for v in self.target_weights.values())
            return {k: float(v) / s for k, v in self.target_weights.items()}

    mp = _MP(
        name=f"frontier:{proposal.model_id}:{proposal.frontier_version}:rs{proposal.risk_score}",
        weights=proposal.target_weights,
    )

    try:
        intents = allocate_cash_to_model(
            PortfolioState=PortfolioState,
            model_portfolio=mp,  # adapter
            price_lookup=price_lookup,
            ledger=ledger,
            as_of=proposal.as_of,
            run_id=run_id,
            min_trade_notional=min_trade_notional,
            allow_fractional=allow_fractional,
            fractional_dp=fractional_dp,
            # Patch 6C: pass gating context (defense-in-depth)
            frontier_store=store,
            frontier_version=proposal.frontier_version,
            model_id=proposal.model_id,
        )
    except AllocationError as e:
        raise TradeFlowError(str(e)) from e

    # If we got here, ledger writes succeeded.
    store.set_status(proposal.as_of, proposal.frontier_version, FrontierStatus.EXECUTED)
    return intents