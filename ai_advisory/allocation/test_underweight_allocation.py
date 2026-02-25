from datetime import datetime, date
from decimal import Decimal

from ai_advisory.core.ids import new_id
from ai_advisory.portfolio.state import PortfolioState
import ai_advisory.portfolio.ledger as ledger
from ai_advisory.models.definitions import BALANCED
from ai_advisory.allocation.allocate import allocate_cash_to_model


def test_allocate_prefers_underweight_assets():
    # Balanced: VTI 50%, VXUS 25%, BND 25%
    # Seed state with an overweight VTI position, then deposit cash.
    state = PortfolioState(
        schema_version="v1",
        engine_version="0.1.0",
        id=new_id("state"),
        user_id="u_123",
        as_of=date.today(),
        created_at=datetime.now(),
    )

    # Put $50,000 into VTI already (overweight), none in VXUS/BND
    # Price VTI = 200 => qty 250 shares
    state.upsert_position("VTI", "core", quantity_delta=250.0, price=200.0)

    # Add $10,000 cash
    ledger.deposit(
        PortfolioState=state,
        user_id="u_123",
        as_of=date.today(),
        created_at=datetime.now(),
        sleeve="core",
        amount=Decimal("10000"),
        idempotency_key="dep:uw:1",
    )

    def px(sym: str) -> Decimal:
        return {"VTI": Decimal("200"), "VXUS": Decimal("50"), "BND": Decimal("100")}[sym]

    intents = allocate_cash_to_model(
        PortfolioState=state,
        model_portfolio=BALANCED,
        price_lookup=px,
        ledger=ledger,
        as_of=str(date.today()),
        run_id="run_underweight_001",
        allow_fractional=True,
        min_trade_notional=Decimal("250.00"),
    )

    bought = {i.symbol for i in intents}

    # VTI should be overweight, so allocation should prefer VXUS and/or BND
    assert "VTI" not in bought
    assert ("VXUS" in bought) or ("BND" in bought)