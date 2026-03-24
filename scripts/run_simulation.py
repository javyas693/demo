import argparse
import sys
import logging
from ai_advisory.portfolio.portfolio_state import PortfolioState
from ai_advisory.orchestration.time_simulator import simulate_portfolio

def main():
    parser = argparse.ArgumentParser(description="Run deterministic portfolio simulations locally")
    parser.add_argument("--ticker", type=str, default="AAPL", help="Stock ticker to simulate")
    parser.add_argument("--shares", type=float, default=5000, help="Initial concentrated shares")
    parser.add_argument("--price", type=float, default=100.0, help="Initial price of stock")
    parser.add_argument("--cash", type=float, default=0.0, help="Starting cash balance")
    parser.add_argument("--horizon", type=int, default=12, help="Horizon in months")
    parser.add_argument("--basis", type=float, default=50.0, help="Cost basis of shares")
    parser.add_argument("--tlh", type=float, default=0.0, help="Available Tax Loss Harvesting inventory")

    args = parser.parse_args()

    # Pre-simulate Portfolio State mapping constraint
    initial_state = PortfolioState(
        cash=args.cash,
        ticker=args.ticker,
        shares=args.shares,
        current_price=args.price,
        cost_basis=args.basis,
        income_value=0.0,
        annual_income=0.0,
        model_value=0.0,
        tlh_inventory=args.tlh,
        risk_score=50.0
    )

    print(f"\n[INIT] Simulating {args.horizon} Months for {args.ticker}")
    print(f"Starting Baseline Value: ${initial_state.total_portfolio_value:,.2f}")
    print("-" * 50)

    try:
        timeline = simulate_portfolio(
            initial_state=initial_state,
            ticker=args.ticker,
            initial_shares=args.shares,
            cost_basis=args.basis,
            horizon_months=args.horizon
        )
    except Exception as e:
        print(f"\n[FATAL ERROR] Simulation Engine crashed: {str(e)}")
        sys.exit(1)

    # Replay timeline array strictly to log the determinism
    for step in timeline:
        month = step["month"]
        if month == 0:
            continue
        
        cv = step["concentrated_value"]
        iv = step["income_value"]
        mv = step["model_value"]
        total = step["total_portfolio_value"]
        
        print(f"M{month:<2} | CP=${cv:,.0f} | INC=${iv:,.0f} | MOD=${mv:,.0f} | TOTAL=${total:,.0f} | %CP={step['concentration_pct']:.1f}%")

    # Overall Summary
    baseline = timeline[0]
    final = timeline[-1]
    
    print("-" * 50)
    print(f"[FINAL DUMP]")
    print(f"Start Val: ${baseline['total_portfolio_value']:,.0f}")
    print(f"End Val:   ${final['total_portfolio_value']:,.0f}")
    print(f"Total Drift: ${(final['total_portfolio_value'] - baseline['total_portfolio_value']):,.0f}")

if __name__ == "__main__":
    main()
