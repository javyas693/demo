from datetime import datetime, date

from ai_advisory.core.ids import new_id
from ai_advisory.portfolio.portfolio_state import PortfolioState
from ai_advisory.core.ledger import LedgerEvent, apply_event


state = PortfolioState(
    schema_version="v1",
    engine_version="0.1.0",
    id=new_id("state"),
    user_id="u_123",
    as_of=date.today(),
    created_at=datetime.now(),
)

# Deposit 10,000
deposit = LedgerEvent(
    "v1",
    new_id("event"),
    "u_123",
    datetime.now(),
    date.today(),
    "deposit",
    "core",
    10000.0
)

apply_event(state, deposit)

# Buy 10 shares of SPY at 500
buy = LedgerEvent(
    "v1",
    new_id("event"),
    "u_123",
    datetime.now(),
    date.today(),
    "buy_fill",
    "core",
    0.0,
    "SPY",
    10,
    500.0
)

apply_event(state, buy)

# Buy 5 shares of IEF at 100
buy2 = LedgerEvent(
    "v1",
    new_id("event"),
    "u_123",
    datetime.now(),
    date.today(),
    "buy_fill",
    "core",
    0.0,
    "IEF",
    5,
    100.0
)

apply_event(state, buy2)

sell_spy = LedgerEvent(
    "v1",
    new_id("event"),
    "u_123",
    datetime.now(),
    date.today(),
    "sell_fill",
    "core",
    0.0,
    "SPY",
    2,
    510.0
)
apply_event(state, sell_spy)

print("Cash:", state.cash_total())
print("Positions:", [(p.symbol, p.quantity, p.market_value) for p in state.positions])
print("Total Value:", state.total_portfolio_value())