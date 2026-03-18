import os
import sys
import json
from unittest.mock import patch
from test_utils import mock_yf_download

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ai_advisory.strategy.strategy_unwind import StrategyUnwindEngine

BASELINES_DIR = os.path.join(os.path.dirname(__file__), "baselines")
SCENARIO_A = os.path.join(BASELINES_DIR, "baseline_scenario_A.json")
SCENARIO_B = os.path.join(BASELINES_DIR, "baseline_scenario_B.json")

def extract_metrics(results):
    summary = results["summary"]
    return {
        "final_portfolio_value": round(summary["final_portfolio_value"], 2),
        "shares_sold": summary["initial_shares"] - summary["final_shares"],
        "tlh_inventory_remaining": round(summary.get("final_tlh_inventory", 0.0), 2),
        "total_return_pct": round(summary["total_return_pct"], 4)
    }

def run_scenario(engine, name, **kwargs):
    results = engine.run_covered_call_overlay(**kwargs)
    return extract_metrics(results)

def compare_results(actual, expected, tolerance=0.01):
    for key in expected:
        if key not in actual:
            return False, f"Missing key '{key}' in actual results"
        
        val_act = actual[key]
        val_exp = expected[key]
        
        if abs(val_act - val_exp) > tolerance:
            return False, f"Deviation found in {key}: actual={val_act}, expected={val_exp}"
            
    return True, "No deviations found"

@patch('ai_advisory.strategy.strategy_unwind.yf.download', side_effect=mock_yf_download)
def run_regression_test(mock_download):
    print("--- RUNNING REGRESSION TEST ---")
    
    engine = StrategyUnwindEngine(
        ticker="MOCK",
        start_date="2023-01-01",
        end_date="2023-10-01",
        initial_shares=1000
    )
    
    # Scenario A: Moderate parameters
    args_A = dict(
        strategy_mode="tax_neutral",
        enable_tax_loss_harvest=True,
        share_reduction_trigger_pct=0.3,
        cost_basis=100.0,
        coverage_pct=50.0,
        target_dte_days=30,
        target_delta=0.20,
        profit_capture_pct=0.50,
        max_shares_per_month=200,
        starting_cash=0.0
    )
    
    # Scenario B: Aggressive parameters
    args_B = dict(
        strategy_mode="tax_neutral",
        enable_tax_loss_harvest=True,
        share_reduction_trigger_pct=0.1,  # triggers faster
        cost_basis=100.0,
        coverage_pct=50.0,
        target_dte_days=30,
        target_delta=0.35, # more option risk
        profit_capture_pct=0.30, # takes profit faster
        max_shares_per_month=300,
        starting_cash=0.0
    )
    
    scenario_A_results = run_scenario(engine, "Scenario A", **args_A)
    scenario_B_results = run_scenario(engine, "Scenario B", **args_B)
    
    # Generate baselines if they don't exist
    if not os.path.exists(SCENARIO_A):
        print("Saving baseline A...")
        with open(SCENARIO_A, 'w') as f:
            json.dump(scenario_A_results, f, indent=2)
            
    if not os.path.exists(SCENARIO_B):
        print("Saving baseline B...")
        with open(SCENARIO_B, 'w') as f:
            json.dump(scenario_B_results, f, indent=2)
            
    # Load baselines and compare
    with open(SCENARIO_A, 'r') as f:
        baseline_A = json.load(f)
        
    with open(SCENARIO_B, 'r') as f:
        baseline_B = json.load(f)
        
    print("[1/2] Comparing Scenario A...")
    match_A, msg_A = compare_results(scenario_A_results, baseline_A)
    if not match_A:
        print(f"FAILED: {msg_A}")
        return False
    print("PASS: Scenario A")
        
    print("[2/2] Comparing Scenario B...")
    match_B, msg_B = compare_results(scenario_B_results, baseline_B)
    if not match_B:
        print(f"FAILED: {msg_B}")
        return False
    print("PASS: Scenario B")
    
    print("=> REGRESSION TEST PASSED: Outputs deterministically match baselines.")
    return True

if __name__ == "__main__":
    success = run_regression_test()
    sys.exit(0 if success else 1)
