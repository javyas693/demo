from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date
from typing import Dict, Literal, Optional

from ai_advisory.portfolio.portfolio_state import PortfolioState

EventType = Literal[
    "deposit",
    "buy_fill",
    "sell_fill",
    "withdrawal",
    "fee",
    "mark_to_market",
]


@dataclass(frozen=True)
class LedgerEvent:
    # Envelope (LE-1)
    schema_version: str  # "LE-1"
    id: str
    user_id: str
    created_at: datetime
    as_of: date

    # Phase 1 discipline
    engine_version: str

    # Type
    event_type: EventType
    sleeve: str = "core"

    # Cash events
    amount: float = 0.0

    # Trade events
    symbol: Optional[str] = None
    quantity: Optional[float] = None
    price: Optional[float] = None

    # Valuation events
    prices: Optional[Dict[str, float]] = None


def apply_event(state: PortfolioState, event: LedgerEvent) -> PortfolioState:
    """
    Mutates and returns `state` (in-place) for simplicity in Release 0.1.
    Enforces idempotency via state.applied_event_ids.
    """
    if event.id in state.applied_event_ids:
        return state

    # Phase 1 discipline: engine_version must always exist
    if not event.engine_version:
        raise ValueError("LedgerEvent.engine_version is required (Phase 1 discipline)")

    state.applied_event_ids.add(event.id)

    et = event.event_type

    # --- Cash events ---
    if et == "deposit":
        state.cash_by_sleeve[event.sleeve] += float(event.amount)
        return state

    if et == "withdrawal":
        state.cash_by_sleeve[event.sleeve] -= float(event.amount)
        return state

    if et == "fee":
        state.cash_by_sleeve[event.sleeve] -= float(event.amount)
        return state

    # --- Valuation events ---
    if et == "mark_to_market":
        if event.prices is None:
            raise ValueError("mark_to_market requires prices")

        for symbol, price in event.prices.items():
            px = float(price)
            if px <= 0:
                raise ValueError(f"Invalid price for {symbol}: {px}")

            pos = state.find_position(symbol, event.sleeve)
            if pos:
                # Update price only; market_value is derived (property)
                pos.last_price = px

        return state

    # --- Trade events ---
    if et in ("buy_fill", "sell_fill"):
        if event.symbol is None or event.quantity is None or event.price is None:
            raise ValueError(f"{et} requires symbol, quantity, price")

        qty = float(event.quantity)
        px = float(event.price)
        notional = qty * px

        if et == "buy_fill":
            state.cash_by_sleeve[event.sleeve] -= notional
            state.upsert_position(event.symbol, event.sleeve, qty, px)
            return state

        # sell_fill
        state.cash_by_sleeve[event.sleeve] += notional
        state.upsert_position(event.symbol, event.sleeve, -qty, px)
        return state

    raise ValueError(f"Unknown event_type: {et}")