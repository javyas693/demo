from datetime import datetime, date
from decimal import Decimal

import pytest

from ai_advisory.core.ids import new_id
from ai_advisory.portfolio.portfolio_state import PortfolioState
from ai_advisory.portfolio import ledger
from ai_advisory.portfolio.ledger_engine import LedgerEvent, apply_event


def make_state() -> PortfolioState:
    return PortfolioState(
        schema_version="v1",
        engine_version="0.1.0",
        id=new_id("state"),
        user_id="u_123",
        as_of=date.today(),
        created_at=datetime.now(),
    )


def test_withdrawal_reduces_cash():
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

    cash_before = state.cash_by_sleeve["core"]

    ledger.withdrawal(
        PortfolioState=state,
        user_id="u_123",
        created_at=datetime.now(),
        as_of=date.today(),
        sleeve="core",
        amount=Decimal("2500"),
        idempotency_key="wd:1",
        reason="test",
    )

    assert state.cash_by_sleeve["core"] == pytest.approx(cash_before - 2500.0)


def test_fee_reduces_cash():
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

    cash_before = state.cash_by_sleeve["core"]

    ledger.fee(
        PortfolioState=state,
        user_id="u_123",
        created_at=datetime.now(),
        as_of=date.today(),
        sleeve="core",
        amount=Decimal("25"),
        fee_type="test_fee",
        idempotency_key="fee:1",
    )

    assert state.cash_by_sleeve["core"] == pytest.approx(cash_before - 25.0)


def test_engine_version_missing_raises():
    state = make_state()

    # Construct a raw event with empty engine_version to ensure discipline is enforced
    ev = LedgerEvent(
        schema_version="LE-1",
        id=new_id("event"),
        user_id="u_123",
        created_at=datetime.now(),
        as_of=date.today(),
        engine_version="",  # <-- should fail
        event_type="deposit",
        sleeve="core",
        amount=100.0,
    )

    with pytest.raises(ValueError, match="engine_version"):
        apply_event(state, ev)