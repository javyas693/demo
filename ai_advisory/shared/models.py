"""
Pydantic models for structured data flowing between agents via session state.

These models enforce the contract between data-gathering sub-agents
and analysis AgentTools. The gatherer writes validated data; the analyzer
reads it with confidence.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import date


class TaxLot(BaseModel):
    """A single tax lot within a concentrated position."""
    lot_id: str = Field(description="Unique identifier for this lot")
    ticker: str = Field(description="Stock ticker symbol")
    shares: int = Field(description="Number of shares in this lot")
    cost_basis: float = Field(description="Cost basis per share at acquisition")
    acquisition_date: str = Field(description="Date acquired (YYYY-MM-DD)")
    holding_period_days: Optional[int] = Field(
        default=None,
        description="Computed: days held from acquisition to today"
    )
    is_long_term: Optional[bool] = Field(
        default=None,
        description="Computed: held > 365 days"
    )


class ConcentratedPosition(BaseModel):
    """Complete concentrated position data collected from the user."""
    ticker: str
    total_shares: int
    lots: list[TaxLot]
    current_price: Optional[float] = None
    total_market_value: Optional[float] = None
    portfolio_percentage: Optional[float] = Field(
        default=None,
        description="What % of total portfolio this position represents"
    )


class RiskProfile(BaseModel):
    """Output of the risk assessment process."""
    user_name: str
    scores: list[float] = Field(description="Per-question scores")
    composite_score: float = Field(description="Weighted composite 0.0–1.0")
    label: str = Field(description="Human-readable label: Conservative, Moderate, etc.")
    goal_statement: str = Field(description="User's stated investment goal")


class UnwindScenario(BaseModel):
    """A single unwind strategy scenario with projected outcomes."""
    strategy_name: str
    description: str
    annual_sell_percentage: float
    years_to_complete: int
    estimated_total_tax: float
    estimated_tax_rate_blended: float
    year_by_year: list[dict] = Field(
        description="Per-year breakdown: shares_sold, proceeds, tax, remaining"
    )


class UnwindAnalysis(BaseModel):
    """Complete output of the position unwind analysis."""
    position: ConcentratedPosition
    risk_profile_label: str
    scenarios: list[UnwindScenario]
    recommended_scenario: str = Field(description="Name of the recommended strategy")
    recommendation_rationale: str
