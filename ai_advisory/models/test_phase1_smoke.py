from decimal import Decimal
from ai_advisory.models.registry import get_model_portfolio
from ai_advisory.allocation.allocate import allocate_cash_to_model


class FakePortfolioState:
    cash_total = Decimal("10000")


class FakeLedger:
    def __init__(self):
        self.calls = []

    def buy_fill(self, **kwargs):
        self.calls.append(kwargs)


def test_get_model_portfolio_smoke():
    mp = get_model_portfolio(5)
    mp.validate()
    assert len(mp.target_weights) > 0


def test_allocate_cash_to_model_smoke():
    mp = get_model_portfolio(5)
    ledger = FakeLedger()

    def px(sym: str) -> Decimal:
        return {"VTI": Decimal("200"), "VXUS": Decimal("50"), "BND": Decimal("100")}[sym]

    intents = allocate_cash_to_model(
        PortfolioState=FakePortfolioState,
        model_portfolio=mp,
        price_lookup=px,
        ledger=ledger,
        as_of="2026-02-24",
        run_id="run_smoke_001",
        allow_fractional=True,
    )

    assert len(intents) > 0
    assert len(ledger.calls) == len(intents)