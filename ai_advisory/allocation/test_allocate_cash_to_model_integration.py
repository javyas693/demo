from datetime import datetime, date
from decimal import Decimal

from ai_advisory.core.ids import new_id
from ai_advisory.portfolio.state import PortfolioState
import ai_advisory.portfolio.ledger as ledger
from ai_advisory.models.registry import get_model_portfolio
from ai_advisory.allocation.allocate import allocate_cash_to_model


def test_allocate_cash_to_model_integration():
    state = PortfolioState(
        schema_version="v1",
        engine_version="0.1.0",
        id=new_id("state"),
        user_id="u_123",
        as_of=date.today(),
        created_at=datetime.now(),
    )

    ledger.deposit(
        PortfolioState=state,
        user_id="u_123",
        as_of=date.today(),
        created_at=datetime.now(),
        sleeve="core",
        amount=Decimal("10000"),
        idempotency_key="dep:1",
    )

    model_portfolio = get_model_portfolio(5)

    def price_lookup(sym: str) -> Decimal:
        return {"VTI": Decimal("200"), "VXUS": Decimal("50"), "BND": Decimal("100")}[sym]

    intents = allocate_cash_to_model(
        PortfolioState=state,
        model_portfolio=model_portfolio,
        price_lookup=price_lookup,
        ledger=ledger,
        as_of=str(date.today()),
        run_id="run_integration_001",
        allow_fractional=True,
    )
    assert all(i.notional >= Decimal("250.00") for i in intents)

    assert len(intents) > 0