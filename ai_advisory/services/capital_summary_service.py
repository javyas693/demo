from __future__ import annotations

from .http_models import CapitalSummary, ClientProfile
from .signals_service import compute_signals


def compute_capital_summary(profile: ClientProfile) -> CapitalSummary:
    signals = compute_signals(profile)

    # items requiring review: medium/high actionable signals
    review_count = sum(1 for s in signals if s.actionable and s.severity in ("medium", "high"))

    # concentration status derived from concentration alert severity
    conc_status = "ok"
    for s in signals:
        if s.program == "risk_reduction" and s.title.lower().startswith("concentration"):
            conc_status = "breach" if s.severity == "high" else "elevated"
            break

    headline = "Your capital is aligned with your goals." if review_count == 0 else "Your capital is aligned with your goals."
    subheadline = "No items require review." if review_count == 0 else f"{review_count} item(s) require review."

    # Calculate real portfolio metrics
    cash_available = profile.cash_to_invest
    
    portfolio_value = cash_available
    largest_holding_symbol = None
    largest_holding_value = 0.0
    
    # Assumed stub price is 1.0 for paper trading execution logic
    STUB_PRICE = 1.0
    
    positions = getattr(profile, "positions", [])
    for pos in positions:
        pos_value = pos.shares * STUB_PRICE
        portfolio_value += pos_value
        
        if pos_value > largest_holding_value:
            largest_holding_value = pos_value
            largest_holding_symbol = pos.symbol
            
    concentration_pct = 0.0
    if portfolio_value > 0 and largest_holding_value > 0:
        concentration_pct = largest_holding_value / portfolio_value

    return CapitalSummary(
        portfolio_value=portfolio_value,
        cash_available=cash_available,
        largest_holding_symbol=largest_holding_symbol,
        largest_holding_value=largest_holding_value,
        concentration_pct=concentration_pct,
        concentration_status=conc_status,
        items_require_review=review_count,
        headline=headline,
        subheadline=subheadline,
    )