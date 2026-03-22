from dataclasses import dataclass, field
from typing import Optional, Any


@dataclass(frozen=True)
class PortfolioState:
    """
    Read-only unified state representation of the investor's current portfolio.
    Aggregates inputs necessary for orchestration across all sub-engines.
    """
    # Core
    total_portfolio_value: float = 0.0
    cash: float = 0.0

    # Concentrated
    ticker: str = "TICKER"
    shares: float = 0.0
    current_price: float = 0.0
    cost_basis: float = 0.0
    market_value: float = 0.0

    # Income
    income_value: float = 0.0
    annual_income: float = 0.0
    income_holdings: dict = field(default_factory=dict)

    # Model
    model_value: float = 0.0
    model_holdings: dict = field(default_factory=dict)

    # Tax
    tlh_inventory: float = 0.0

    # Overlay Options
    open_option: Optional[Any] = None
    next_call_allowed_date: Optional[Any] = None

    # Risk
    risk_score: float = 50.0

    # Client constraint — fed to DecisionService via orchestrator.
    # Valid values: "NO_SELL" | "SELL_OPTIONAL" | "SELL_REQUIRED"
    client_constraint: str = "SELL_OPTIONAL"

    # System Ledger Tracking
    applied_event_ids: frozenset = field(default_factory=frozenset)

    def __post_init__(self):
        # Resolve concentrated market value from shares * price
        calculated_market = self.shares * self.current_price
        object.__setattr__(self, 'market_value', calculated_market)

        # Total portfolio value derived from components (never set directly)
        calculated_total = self.cash + calculated_market + self.income_value + self.model_value
        object.__setattr__(self, 'total_portfolio_value', calculated_total)

        # Hard guards
        assert self.total_portfolio_value >= 0.0, f"total_portfolio_value cannot be negative: {self.total_portfolio_value}"
        assert self.cash >= 0.0,           f"cash cannot be negative: {self.cash}"
        assert self.shares >= 0.0,         f"shares cannot be negative: {self.shares}"
        assert self.current_price >= 0.0,  f"price cannot be negative: {self.current_price}"
        assert self.cost_basis >= 0.0,     f"cost_basis cannot be negative: {self.cost_basis}"
        assert self.market_value >= 0.0,   f"market_value cannot be negative: {self.market_value}"
        assert self.income_value >= 0.0,   f"income_value cannot be negative: {self.income_value}"
        assert self.annual_income >= 0.0,  f"annual_income cannot be negative: {self.annual_income}"
        assert self.model_value >= 0.0,    f"model_value cannot be negative: {self.model_value}"

        # Concentration guard
        if self.concentration_pct > 1.001 or self.concentration_pct < 0.0:
            raise ValueError(
                f"State Validation Failed: concentration {self.concentration_pct * 100:.2f}% out of bounds."
            )

        # Client constraint guard
        valid_constraints = {"NO_SELL", "SELL_OPTIONAL", "SELL_REQUIRED"}
        if self.client_constraint not in valid_constraints:
            raise ValueError(
                f"State Validation Failed: client_constraint='{self.client_constraint}' "
                f"must be one of {valid_constraints}."
            )

    @property
    def unrealized_loss(self) -> float:
        """Percentage of unrealized loss relative to cost basis."""
        if self.cost_basis <= 0:
            return 0.0
        return max(0.0, (self.cost_basis - self.current_price) / self.cost_basis)

    @property
    def concentration_pct(self) -> float:
        """Fraction of total portfolio tied up in the concentrated position."""
        if self.total_portfolio_value <= 0:
            return 0.0
        return self.market_value / self.total_portfolio_value
