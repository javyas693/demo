#!/usr/bin/env bash
set -euo pipefail

ROOT="ai_advisory"
mkdir -p "$ROOT/core" "$ROOT/demo" "$ROOT/tests"

touch "$ROOT/__init__.py" "$ROOT/core/__init__.py" "$ROOT/demo/__init__.py" "$ROOT/tests/__init__.py"

cat > "$ROOT/core/ids.py" << 'PY'
from __future__ import annotations
import uuid

def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"
PY

cat > "$ROOT/core/portfolio_state.py" << 'PY'
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, date

Sleeve = str  # "core" | "income"

@dataclass
class Position:
    symbol: str
    quantity: float
    mark_price: float
    sleeve: Sleeve = "core"
    asset_class: Optional[str] = None

    @property
    def market_value(self) -> float:
        return float(self.quantity) * float(self.mark_price)

@dataclass
class PortfolioState:
    schema_version: str
    engine_version: str
    id: str
    user_id: str
    as_of: date
    created_at: datetime
    base_currency: str = "USD"
    cash_by_sleeve: Dict[Sleeve, float] = field(default_factory=lambda: {"core": 0.0, "income": 0.0})
    positions: List[Position] = field(default_factory=list)
    applied_ledger_event_ids: set[str] = field(default_factory=set)
    sleeve_targets: Dict[Sleeve, float] = field(default_factory=lambda: {"core": 0.80, "income": 0.20})

    def cash_total(self) -> float:
        return float(sum(self.cash_by_sleeve.values()))

    def total_market_value(self) -> float:
        return float(sum(p.market_value for p in self.positions))

    def total_portfolio_value(self) -> float:
        return self.cash_total() + self.total_market_value()

    def find_position(self, symbol: str, sleeve: Sleeve) -> Optional[Position]:
        for p in self.positions:
            if p.symbol == symbol and p.sleeve == sleeve:
                return p
        return None

    def upsert_position(self, symbol: str, sleeve: Sleeve, delta_qty: float, mark_price: float) -> None:
        pos = self.find_position(symbol, sleeve)
        if pos is None:
            if abs(delta_qty) > 0:
                self.positions.append(Position(symbol=symbol, quantity=float(delta_qty), mark_price=float(mark_price), sleeve=sleeve))
            return

        pos.quantity = float(pos.quantity) + float(delta_qty)
        pos.mark_price = float(mark_price)

        if abs(pos.quantity) < 1e-12:
            self.positions = [p for p in self.positions if not (p.symbol == symbol and p.sleeve == sleeve)]
PY

cat > "$ROOT/core/ledger.py" << 'PY'
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional, Literal, Dict, Any

from .portfolio_state import PortfolioState, Sleeve

EventType = Literal[
    "deposit",
    "withdrawal",
    "buy_fill",
    "sell_fill",
    "fee",
    "option_income",
    "tax_realized",
]

@dataclass
class LedgerEvent:
    schema_version: str
    id: str
    user_id: str
    created_at: datetime
    as_of: date
    event_type: EventType
    sleeve: Sleeve = "core"
    amount: float = 0.0
    currency: str = "USD"
    symbol: Optional[str] = None
    quantity: Optional[float] = None
    price: Optional[float] = None
    details: Optional[Dict[str, Any]] = None

class LedgerError(Exception):
    pass

def apply_event(state: PortfolioState, event: LedgerEvent) -> PortfolioState:
    # idempotency
    if event.id in state.applied_ledger_event_ids:
        return state
    if event.user_id != state.user_id:
        raise LedgerError("event.user_id does not match state.user_id")

    state.applied_ledger_event_ids.add(event.id)

    sleeve = event.sleeve
    if sleeve not in state.cash_by_sleeve:
        state.cash_by_sleeve[sleeve] = 0.0

    et = event.event_type

    if et == "deposit":
        state.cash_by_sleeve[sleeve] += float(event.amount)
        return state

    if et == "withdrawal":
        state.cash_by_sleeve[sleeve] -= float(event.amount)
        return state

    if et == "fee":
        state.cash_by_sleeve[sleeve] -= float(event.amount)
        return state

    if et in ("buy_fill", "sell_fill"):
        if event.symbol is None or event.quantity is None or event.price is None:
            raise LedgerError(f"{et} requires symbol, quantity, price")

        qty = float(event.quantity)
        px = float(event.price)
        notional = qty * px

        if et == "buy_fill":
            state.cash_by_sleeve[sleeve] -= notional
            state.upsert_position(symbol=event.symbol, sleeve=sleeve, delta_qty=qty, mark_price=px)
        else:
            state.cash_by_sleeve[sleeve] += notional
            state.upsert_position(symbol=event.symbol, sleeve=sleeve, delta_qty=-qty, mark_price=px)

        return state

    # Keep other event types no-op for now (option_income, tax_realized) — schema frozen, logic later
    return state
PY

cat > "$ROOT/demo/demo_phase1.py" << 'PY'
from datetime import datetime, date
from ai_advisory.core.ids import new_id
from ai_advisory.core.portfolio_state import PortfolioState
from ai_advisory.core.ledger import LedgerEvent, apply_event

def main():
    state = PortfolioState(
        schema_version="v1",
        engine_version="0.1.0",
        id=new_id("state"),
        user_id="u_123",
        as_of=date.today(),
        created_at=datetime.now(),
    )

    dep = LedgerEvent(
        schema_version="v1",
        id=new_id("ledg"),
        user_id="u_123",
        created_at=datetime.now(),
        as_of=date.today(),
        event_type="deposit",
        sleeve="core",
        amount=10000.0,
    )
    apply_event(state, dep)

    buy = LedgerEvent(
        schema_version="v1",
        id=new_id("ledg"),
        user_id="u_123",
        created_at=datetime.now(),
        as_of=date.today(),
        event_type="buy_fill",
        sleeve="core",
        symbol="SPY",
        quantity=10,
        price=500.0,
    )
    apply_event(state, buy)

    # replay buy should do nothing (idempotent)
    apply_event(state, buy)

    print("Cash by sleeve:", state.cash_by_sleeve)
    print("Positions:", [(p.symbol, p.quantity, p.mark_price, p.sleeve) for p in state.positions])
    print("Total value:", state.total_portfolio_value())

if __name__ == "__main__":
    main()
PY

cat > "$ROOT/tests/test_phase1_min.py" << 'PY'
from datetime import datetime, date
from ai_advisory.core.ids import new_id
from ai_advisory.core.portfolio_state import PortfolioState
from ai_advisory.core.ledger import LedgerEvent, apply_event

def test_deposit_and_buy_and_idempotency():
    state = PortfolioState(
        schema_version="v1",
        engine_version="0.1.0",
        id=new_id("state"),
        user_id="u_123",
        as_of=date.today(),
        created_at=datetime.now(),
    )

    dep = LedgerEvent("v1", new_id("ledg"), "u_123", datetime.now(), date.today(), "deposit", "core", 10000.0)
    apply_event(state, dep)
    assert abs(state.cash_total() - 10000.0) < 1e-9

    buy = LedgerEvent("v1", new_id("ledg"), "u_123", datetime.now(), date.today(), "buy_fill", "core", 0.0, "USD", "SPY", 10, 500.0)
    apply_event(state, buy)

    assert abs(state.cash_total() - 5000.0) < 1e-9
    assert len(state.positions) == 1
    assert state.positions[0].symbol == "SPY"
    assert abs(state.positions[0].quantity - 10.0) < 1e-9

    # replay same event id must not change state
    apply_event(state, buy)
    assert abs(state.cash_total() - 5000.0) < 1e-9
    assert len(state.positions) == 1
PY

echo "Bootstrap complete."
echo "Next:"
echo "  python -m ai_advisory.demo.demo_phase1"
echo "  pytest -q"