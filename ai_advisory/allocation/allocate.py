from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable, Dict, List, Optional

from ai_advisory.models.model_portfolio import ModelPortfolio
from ai_advisory.allocation.rounding import round_quantity

from ai_advisory.core.frontier_status import FrontierStatus
from ai_advisory.frontier.store.fs_store import FileSystemFrontierStore


@dataclass(frozen=True)
class BuyIntent:
    symbol: str
    quantity: Decimal
    price: Decimal
    notional: Decimal


class AllocationError(Exception):
    pass


def allocate_cash_to_model(
    *,
    PortfolioState,
    model_portfolio: ModelPortfolio,
    price_lookup: Callable[[str], Decimal],
    ledger,
    as_of: str,
    run_id: str,
    min_trade_notional: Decimal = Decimal("250.00"),  # Phase 1 later changes to $250
    allow_fractional: bool = True,
    fractional_dp: int = 6,
    # Patch 6C (optional): execution gating against approved frontier
    frontier_store: Optional[FileSystemFrontierStore] = None,
    frontier_version: Optional[str] = None,
    model_id: Optional[str] = None,
) -> List[BuyIntent]:
    """
    Phase 1 minimal:
    - Allocate available cash proportionally to ModelPortfolio.target_weights
    - Round shares properly
    - Emit buy_fill
    - Update PortfolioState through ledger application

    Patch 6C (optional):
    - If frontier_store + frontier_version are provided, require the frontier be APPROVED
      before executing any fills.
    """
    model_portfolio.validate()

    # --- Patch 6C: status gate (only if caller supplies frontier context)
    if frontier_store is not None and frontier_version is not None:
        status = frontier_store.get_status(as_of, frontier_version)
        if status != FrontierStatus.APPROVED:
            raise AllocationError(
                f"Execution blocked: frontier_version={frontier_version} status={status.value}. "
                f"Must be APPROVED."
            )
        # optional safety: also ensure the frontier matches model_id if provided
        if model_id is not None:
            meta = frontier_store._read_meta(as_of, frontier_version)  # internal read ok for now
            meta_model = meta.get("model_id")
            if meta_model and meta_model != model_id:
                raise AllocationError(
                    f"Execution blocked: frontier model_id mismatch. meta.model_id={meta_model} expected={model_id}"
                )

    cash = _get_total_cash(PortfolioState)
    if cash <= 0:
        return []

    weights = model_portfolio.normalized_weights()

    # 1) compute current market value per model symbol (core sleeve)
    current_values: Dict[str, Decimal] = {}
    for symbol in weights.keys():
        px = price_lookup(symbol)
        qty = _get_position_quantity(PortfolioState, symbol, sleeve="core")
        current_values[symbol] = qty * px

    # 2) total investable = current holdings value + available cash
    total_investable = cash + sum(current_values.values())

    # 3) compute underweight gaps (target - current, clipped at 0)
    gaps: Dict[str, Decimal] = {}
    for symbol, w in weights.items():
        target_value = Decimal(str(w)) * total_investable
        gap = target_value - current_values.get(symbol, Decimal("0"))
        gaps[symbol] = gap if gap > 0 else Decimal("0")

    total_gap = sum(gaps.values())

    # 4) allocate cash to gaps; fallback to weights if no gaps exist
    if total_gap > 0:
        desired_notional = {s: (cash * (gaps[s] / total_gap)) for s in gaps}
    else:
        desired_notional = {s: (cash * Decimal(str(w))) for s, w in weights.items()}

    intents: List[BuyIntent] = []
    for symbol, notional in desired_notional.items():
        if notional < min_trade_notional:
            continue

        px = price_lookup(symbol)
        if px <= 0:
            raise AllocationError(f"Non-positive price for {symbol}: {px}")

        qty = round_quantity(notional / px, allow_fractional=allow_fractional, dp=fractional_dp)
        if qty <= 0:
            continue

        final_notional = qty * px
        if final_notional < min_trade_notional:
            continue

        intents.append(BuyIntent(symbol=symbol, quantity=qty, price=px, notional=final_notional))

    # Execute via ledger (idempotent per intent)
    for i, intent in enumerate(intents):
        idempotency_key = f"{run_id}:buy_fill:{i}:{intent.symbol}"

        ledger.buy_fill(
            PortfolioState=PortfolioState,
            symbol=intent.symbol,
            quantity=intent.quantity,
            price=intent.price,
            as_of=as_of,
            idempotency_key=idempotency_key,
            memo=f"allocate_cash_to_model model_portfolio={model_portfolio.name}",
        )

    return intents


def _get_total_cash(PortfolioState) -> Decimal:
    """
    Adapter layer so allocate module stays decoupled from PortfolioState internals.
    Works with:
      - cash_total() method
      - cash_total attribute
      - cash_balance attribute
      - get_cash_total() method
    """
    if hasattr(PortfolioState, "cash_total"):
        v = getattr(PortfolioState, "cash_total")
        v = v() if callable(v) else v
        return Decimal(str(v))

    if hasattr(PortfolioState, "cash_balance"):
        v = getattr(PortfolioState, "cash_balance")
        v = v() if callable(v) else v
        return Decimal(str(v))

    if hasattr(PortfolioState, "get_cash_total"):
        return Decimal(str(PortfolioState.get_cash_total()))

    raise AllocationError("PortfolioState missing cash_total/cash_balance/get_cash_total")


def _get_position_quantity(PortfolioState, symbol: str, sleeve: str = "core") -> Decimal:
    if hasattr(PortfolioState, "find_position"):
        pos = PortfolioState.find_position(symbol, sleeve)
        if pos is None:
            return Decimal("0")
        return Decimal(str(pos.quantity))

    if hasattr(PortfolioState, "positions"):
        for p in PortfolioState.positions:
            if getattr(p, "symbol", None) == symbol and getattr(p, "sleeve", None) == sleeve:
                return Decimal(str(getattr(p, "quantity", 0.0)))
    return Decimal("0")