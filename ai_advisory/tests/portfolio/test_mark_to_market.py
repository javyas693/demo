from datetime import datetime, date
from decimal import Decimal

import pytest

from ai_advisory.core.ids import new_id
from ai_advisory.portfolio.portfolio_state import PortfolioState
from ai_advisory.portfolio import ledger


def make_state() -> PortfolioState:
    return PortfolioState(
        schema_version="v1",
        engine_version="0.1.0",
        id=new_id("state"),
        user_id="u_123",
        as_of=date.today(),
        created_at=datetime.now(),
    )


def test_mark_to_market_updates_value_not_structure():
    state = make_state()

    ledger.deposit(
        PortfolioState=state,
        user_id="u_123",
        created_at=datetime.now(),
        as_of=date.today(),
        sleeve="core",
        amount=Decimal("10000"),
        idempotency_key="dep:1",
    )

    ledger.buy_fill(
        PortfolioState=state,
        user_id="u_123",
        created_at=datetime.now(),
        as_of=date.today(),
        sleeve="core",
        symbol="SPY",
        quantity=Decimal("10"),
        price=Decimal("100"),
        idempotency_key="buy:1",
    )

    cash_before = state.cash_by_sleeve["core"]
    pos_before = state.find_position("SPY", "core")
    assert pos_before is not None
    qty_before = pos_before.quantity
    mv_before = pos_before.market_value

    # Act: MTM to higher price
    ledger.mark_to_market(
        PortfolioState=state,
        user_id="u_123",
        created_at=datetime.now(),
        as_of=date.today(),
        sleeve="core",
        prices={"SPY": 120.0},
        idempotency_key="mtm:1",
    )

    # Assert
    assert state.cash_by_sleeve["core"] == cash_before  # cash unchanged
    pos_after = state.find_position("SPY", "core")
    assert pos_after is not None
    assert pos_after.quantity == qty_before             # qty unchanged
    assert pos_after.last_price == 120.0
    assert pos_after.market_value > mv_before
    assert pos_after.market_value == pytest.approx(10.0 * 120.0)


def test_mark_to_market_partial_quotes_only_updates_provided_symbols():
    state = make_state()

    ledger.deposit(
        PortfolioState=state,
        user_id="u_123",
        created_at=datetime.now(),
        as_of=date.today(),
        sleeve="core",
        amount=Decimal("20000"),
        idempotency_key="dep:1",
    )

    ledger.buy_fill(
        PortfolioState=state,
        user_id="u_123",
        created_at=datetime.now(),
        as_of=date.today(),
        sleeve="core",
        symbol="SPY",
        quantity=Decimal("10"),
        price=Decimal("100"),
        idempotency_key="buy:spy",
    )

    ledger.buy_fill(
        PortfolioState=state,
        user_id="u_123",
        created_at=datetime.now(),
        as_of=date.today(),
        sleeve="core",
        symbol="IEF",
        quantity=Decimal("5"),
        price=Decimal("90"),
        idempotency_key="buy:ief",
    )

    spy_before = state.find_position("SPY", "core")
    ief_before = state.find_position("IEF", "core")
    assert spy_before is not None and ief_before is not None
    spy_px_before = spy_before.last_price
    ief_px_before = ief_before.last_price

    # Act: only SPY updated
    ledger.mark_to_market(
        PortfolioState=state,
        user_id="u_123",
        created_at=datetime.now(),
        as_of=date.today(),
        sleeve="core",
        prices={"SPY": 110.0},
        idempotency_key="mtm:1",
    )

    spy_after = state.find_position("SPY", "core")
    ief_after = state.find_position("IEF", "core")
    assert spy_after is not None and ief_after is not None

    assert spy_after.last_price == 110.0
    assert ief_after.last_price == ief_px_before
    assert spy_after.last_price != spy_px_before


def test_mark_to_market_is_idempotent_by_event_id():
    """
    apply_event enforces idempotency via state.applied_event_ids.
    This test proves applying the same MTM event twice doesn't double-apply.
    """
    state = make_state()

    ledger.deposit(
        PortfolioState=state,
        user_id="u_123",
        created_at=datetime.now(),
        as_of=date.today(),
        sleeve="core",
        amount=Decimal("10000"),
        idempotency_key="dep:1",
    )
    ledger.buy_fill(
        PortfolioState=state,
        user_id="u_123",
        created_at=datetime.now(),
        as_of=date.today(),
        sleeve="core",
        symbol="SPY",
        quantity=Decimal("10"),
        price=Decimal("100"),
        idempotency_key="buy:1",
    )

    # Create one MTM event and apply it twice by reusing the same event id.
    # Easiest way: call mark_to_market once, then manually re-apply the same event.
    # This requires access to the event constructor + apply_event.
    from ai_advisory.portfolio.ledger_engine import LedgerEvent, apply_event

    ev = LedgerEvent(
        schema_version="LE-1",
        id=new_id("event"),
        user_id="u_123",
        created_at=datetime.now(),
        as_of=date.today(),
        engine_version=state.engine_version,
        event_type="mark_to_market",
        sleeve="core",
        prices={"SPY": 120.0},
    )

    mv_before = state.find_position("SPY", "core").market_value
    apply_event(state, ev)
    mv_after_once = state.find_position("SPY", "core").market_value
    apply_event(state, ev)  # same id => should be ignored
    mv_after_twice = state.find_position("SPY", "core").market_value

    assert mv_after_once > mv_before
    assert mv_after_twice == mv_after_once