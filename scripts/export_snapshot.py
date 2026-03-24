#!/usr/bin/env python3
import json
import os
import sys

# Ensure we can import from the ai_advisory package
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ai_advisory.portfolio.portfolio_state import PortfolioState
from ai_advisory.orchestration.time_simulator import simulate_portfolio, INCOME_YIELD_ANNUAL, MODEL_RETURN_ANNUAL, CP_DRIFT_ANNUAL

class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, 'item'):
            return obj.item()
        return super().default(obj)

def run_export():
    print("Initializing simulation exporter...")
    
    # 1. Config Parameters
    ticker = "AAPL"
    initial_shares = 1000.0
    cost_basis = 50.0
    starting_cash = 100000.0
    horizon_months = 12
    income_preference = 50.0
    cp_price = 150.0
    
    initial_state = PortfolioState(
        total_portfolio_value=(initial_shares * cp_price) + starting_cash,
        cash=starting_cash,
        ticker=ticker,
        shares=initial_shares,
        current_price=cp_price,
        cost_basis=cost_basis,
        market_value=(initial_shares * cp_price),
        income_value=0.0,
        annual_income=0.0,
        model_value=0.0,
        tlh_inventory=250000.0,
        risk_score=50.0
    )
    
    # 2. Run standard simulation
    timeline = simulate_portfolio(
        initial_state=initial_state,
        ticker=ticker,
        initial_shares=initial_shares,
        cost_basis=cost_basis,
        horizon_months=horizon_months,
        income_preference=income_preference
    )
    
    os.makedirs("outputs", exist_ok=True)
    
    # MODULE 1 - EXPORT FULL TIMELINE
    print(f"Exporting Module 1: full timeline ({len(timeline)} steps) -> outputs/full_timeline_dump.json")
    with open("outputs/full_timeline_dump.json", "w") as f:
        json.dump(timeline, f, indent=2, cls=NpEncoder)
        
    # MODULE 2 & 3 - EXPORT SAMPLE STEPS (Step 1, Mid Step, Final Step)
    print("Exporting Module 2 & 3: sample steps -> outputs/sample_steps.json")
    if len(timeline) >= 2:
        step_1 = timeline[1]  # index 1 is Month 1 (index 0 is baseline)
        mid_idx = len(timeline) // 2
        step_mid = timeline[mid_idx]
        step_final = timeline[-1]
        
        sample_steps = {
            "step_1": step_1,
            "mid_step": step_mid,
            "final_step": step_final
        }
    else:
        sample_steps = {"only_step": timeline[0]}
        
    with open("outputs/sample_steps.json", "w") as f:
        json.dump(sample_steps, f, indent=2, cls=NpEncoder)
        
    # MODULE 4 - EXPORT CONFIG / PARAMETERS
    print("Exporting Module 4: strategy config -> outputs/strategy_config.json")
    config = {
        "engine_assumptions": {
            "income_yield_annual": INCOME_YIELD_ANNUAL,
            "model_return_annual": MODEL_RETURN_ANNUAL,
            "cp_price_drift_annual": CP_DRIFT_ANNUAL
        },
        "allocation_rules": {
            "income_preference_pct": income_preference,
            "model_preference_pct": 100.0 - income_preference
        },
        "unwind_parameters": {
            "ticker": ticker,
            "initial_shares": initial_shares,
            "cost_basis": cost_basis,
            "starting_cash": starting_cash,
            "horizon_months": horizon_months,
            "share_reduction_trigger_pct": 0.25, # Default value mapped by orchestrator in test runs
            "max_shares_per_month": 200 # Default value handled by TLH mapping
        }
    }
    
    with open("outputs/strategy_config.json", "w") as f:
        json.dump(config, f, indent=2, cls=NpEncoder)
        
    print("Export complete! 3 files written to outputs/ directory.")

if __name__ == "__main__":
    run_export()
