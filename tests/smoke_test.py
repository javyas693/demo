import os
import sys
import traceback
from unittest.mock import patch
from test_utils import mock_yf_download

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ai_advisory.strategy.strategy_unwind import StrategyUnwindEngine

@patch('ai_advisory.strategy.strategy_unwind.yf.download', side_effect=mock_yf_download)
def run_smoke_test(mock_download):
    print("--- RUNNING SMOKE TEST ---")
    try:
        engine = StrategyUnwindEngine(
            ticker="MOCK",
            start_date="2023-01-01",
            end_date="2023-10-01",
            initial_shares=1000
        )

        print("[1/2] Testing harvest mode...")
        harvest_results = engine.run_covered_call_overlay(
            strategy_mode="harvest",
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
        assert harvest_results is not None
        assert "summary" in harvest_results
        
        print("[2/2] Testing tax_neutral mode...")
        tn_results = engine.run_covered_call_overlay(
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
        assert tn_results is not None
        assert "summary" in tn_results

        print("=> SMOKE TEST PASSED: No exceptions + valid outputs.")
        return True

    except Exception as e:
        print("=> SMOKE TEST FAILED with exception:")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_smoke_test()
    sys.exit(0 if success else 1)
