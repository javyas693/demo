import sys
import os

# Add parent dir to path if needed (though running from root won't need it)
from ai_advisory.portfolio.portfolio_state import PortfolioState
from ai_advisory.orchestration.time_simulator import simulate_portfolio
import logging
logging.basicConfig(filename='simulation_trace.log', filemode='w', level=logging.INFO, format='%(message)s')
logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))

initial_state = PortfolioState(
    cash=0.0,
    ticker="AAPL",
    shares=1000.0,
    current_price=100.0,
    cost_basis=100000.0,
    income_value=0.0,
    annual_income=0.0,
    income_holdings={},
    model_value=0.0,
    model_holdings={},
    tlh_inventory=0.0,
    risk_score=7,
    applied_event_ids=set()
)

print("Starting simulation...")
try:
    res = simulate_portfolio(
        initial_state=initial_state,
        ticker="AAPL",
        initial_shares=1000.0,
        cost_basis=100000.0,
        horizon_months=12,
        income_preference=50.0,
        export_reconciliation=True,
        export_chart_timeline=True
    )

    for snap in res:
        print(f"Month {snap['month']}: Val: {snap['total_portfolio_value']:.2f}, CP Price: {snap['cp_price']:.2f}")

except Exception as e:
    import traceback
    traceback.print_exc()
