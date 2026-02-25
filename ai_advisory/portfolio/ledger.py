from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from typing import Dict, Optional, Union

from ai_advisory.core.ids import new_id
from ai_advisory.portfolio.ledger_engine import LedgerEvent, apply_event
from ai_advisory.portfolio.portfolio_state import PortfolioState as PortfolioStateT

DateLike = Union[date, str]


def _to_date(d: DateLike) -> date:
    if isinstance(d, date):
        return d
    return date.fromisoformat(d)


def _resolve_state(
    state: Optional[PortfolioStateT],
    legacy_state: Optional[PortfolioStateT],
    fn_name: str,
) -> PortfolioStateT:
    if state is not None:
        return state
    if legacy_state is not None:
        return legacy_state
    raise TypeError(f"{fn_name} requires 'state' (or legacy 'PortfolioState')")


def deposit(
    *,
    state: Optional[PortfolioStateT] = None,
    PortfolioState: Optional[PortfolioStateT] = None,  # legacy keyword used by tests
    user_id: str,
    created_at: datetime,
    as_of: DateLike,
    sleeve: str,
    amount: Decimal,
    idempotency_key: str = "",
) -> None:
    st = _resolve_state(state, PortfolioState, "deposit")

    event = LedgerEvent(
        schema_version="LE-1",
        id=new_id("event"),
        user_id=user_id,
        created_at=created_at,
        as_of=_to_date(as_of),
        engine_version=st.engine_version,  # Phase 1 discipline
        event_type="deposit",
        sleeve=sleeve,
        amount=float(amount),
    )
    apply_event(st, event)


def withdrawal(
    *,
    state: Optional[PortfolioStateT] = None,
    PortfolioState: Optional[PortfolioStateT] = None,  # legacy keyword used by tests
    user_id: str,
    created_at: datetime,
    as_of: DateLike,
    sleeve: str,
    amount: Decimal,
    idempotency_key: str = "",
    reason: str = "",
) -> None:
    st = _resolve_state(state, PortfolioState, "withdrawal")

    # reason is intentionally not stored in LE-1 event in Phase 1
    event = LedgerEvent(
        schema_version="LE-1",
        id=new_id("event"),
        user_id=user_id,
        created_at=created_at,
        as_of=_to_date(as_of),
        engine_version=st.engine_version,  # Phase 1 discipline
        event_type="withdrawal",
        sleeve=sleeve,
        amount=float(amount),
    )
    apply_event(st, event)


def fee(
    *,
    state: Optional[PortfolioStateT] = None,
    PortfolioState: Optional[PortfolioStateT] = None,  # legacy keyword used by tests
    user_id: str,
    created_at: datetime,
    as_of: DateLike,
    sleeve: str,
    amount: Decimal,
    fee_type: str = "other",
    related_event_id: Optional[str] = None,
    idempotency_key: str = "",
) -> None:
    st = _resolve_state(state, PortfolioState, "fee")

    # fee_type/related_event_id intentionally not stored in LE-1 event in Phase 1
    event = LedgerEvent(
        schema_version="LE-1",
        id=new_id("event"),
        user_id=user_id,
        created_at=created_at,
        as_of=_to_date(as_of),
        engine_version=st.engine_version,  # Phase 1 discipline
        event_type="fee",
        sleeve=sleeve,
        amount=float(amount),
    )
    apply_event(st, event)


def buy_fill(
    *,
    state: Optional[PortfolioStateT] = None,
    PortfolioState: Optional[PortfolioStateT] = None,  # legacy keyword used by tests
    user_id: str = "u_123",
    created_at: Optional[datetime] = None,
    as_of: DateLike,
    sleeve: str = "core",
    symbol: str,
    quantity: Decimal,
    price: Decimal,
    idempotency_key: str = "",
    memo: str = "",
) -> None:
    st = _resolve_state(state, PortfolioState, "buy_fill")
    ca = created_at or datetime.now()

    event = LedgerEvent(
        schema_version="LE-1",
        id=new_id("event"),
        user_id=user_id,
        created_at=ca,
        as_of=_to_date(as_of),
        engine_version=st.engine_version,  # Phase 1 discipline
        event_type="buy_fill",
        sleeve=sleeve,
        symbol=symbol,
        quantity=float(quantity),
        price=float(price),
    )
    apply_event(st, event)


def sell_fill(
    *,
    state: Optional[PortfolioStateT] = None,
    PortfolioState: Optional[PortfolioStateT] = None,  # legacy keyword used by tests
    user_id: str = "u_123",
    created_at: Optional[datetime] = None,
    as_of: DateLike,
    sleeve: str = "core",
    symbol: str,
    quantity: Decimal,
    price: Decimal,
    idempotency_key: str = "",
    memo: str = "",
) -> None:
    st = _resolve_state(state, PortfolioState, "sell_fill")
    ca = created_at or datetime.now()

    event = LedgerEvent(
        schema_version="LE-1",
        id=new_id("event"),
        user_id=user_id,
        created_at=ca,
        as_of=_to_date(as_of),
        engine_version=st.engine_version,  # Phase 1 discipline
        event_type="sell_fill",
        sleeve=sleeve,
        symbol=symbol,
        quantity=float(quantity),
        price=float(price),
    )
    apply_event(st, event)


def mark_to_market(
    *,
    state: Optional[PortfolioStateT] = None,
    PortfolioState: Optional[PortfolioStateT] = None,  # legacy keyword used by tests
    user_id: str,
    created_at: datetime,
    as_of: DateLike,
    sleeve: str,
    prices: Dict[str, float],
    idempotency_key: str = "",
) -> None:
    st = _resolve_state(state, PortfolioState, "mark_to_market")

    event = LedgerEvent(
        schema_version="LE-1",
        id=new_id("event"),
        user_id=user_id,
        created_at=created_at,
        as_of=_to_date(as_of),
        engine_version=st.engine_version,  # Phase 1 discipline
        event_type="mark_to_market",
        sleeve=sleeve,
        prices=dict(prices),
    )
    apply_event(st, event)