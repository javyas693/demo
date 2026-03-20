import os
import sys
import subprocess

def main():
    print("===================================")
    print("   AI ADVISORY FULL TEST SUITE     ")
    print("===================================")
    
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    app_boot_script = os.path.join(tests_dir, "smoke", "app_boot_test.py")
    chat_resilience_script = os.path.join(tests_dir, "smoke", "test_chat_resilience.py")
    smoke_script = os.path.join(tests_dir, "smoke", "smoke_test.py")
    regression_script = os.path.join(tests_dir, "regression", "regression_test.py")
    income_script = os.path.join(tests_dir, "regression", "test_anchor_income.py")
    mp_script = os.path.join(tests_dir, "regression", "test_managed_portfolio.py")
    invariants_script = os.path.join(tests_dir, "regression", "test_invariants.py")
    integration_script = os.path.join(tests_dir, "integration", "test_integration.py")
    orchestration_script = os.path.join(tests_dir, "orchestration", "test_orchestration.py")
    portfolio_orch_script = os.path.join(tests_dir, "orchestration", "test_portfolio_orchestrator.py")
    
    # 0. Run Boot Test
    print("\nRunning test: app_boot_test.py...")
    res_boot = subprocess.run([sys.executable, app_boot_script], capture_output=False)
    if res_boot.returncode != 0:
        print("\n=> FAIL: APP BOOT TEST FAILED")
        sys.exit(1)
        
    # 0b. Run Chat Resilience Test
    print("\nRunning test: test_chat_resilience.py...")
    res_chat = subprocess.run([sys.executable, chat_resilience_script], capture_output=False)
    if res_chat.returncode != 0:
        print("\n=> FAIL: CHAT RESILIENCE TEST FAILED")
        sys.exit(1)
    
    # 1. Run Smoke Test
    print("\nRunning test: smoke_test.py...")
    res_smoke = subprocess.run([sys.executable, smoke_script], capture_output=False)
    if res_smoke.returncode != 0:
        print("\n=> FAIL: SMOKE TEST SUITE FAILED")
        sys.exit(1)
        
    # 2. Run Regression Tests
    print("\nRunning test: regression_test.py (Concentrated Position + Tax Neutral)...")
    res_regress = subprocess.run([sys.executable, regression_script], capture_output=False)
    if res_regress.returncode != 0:
        print("\n=> FAIL: REGRESSION TEST (CP/TN) FAILED")
        sys.exit(1)
        
    print("\nRunning test: test_anchor_income.py...")
    res_income = subprocess.run([sys.executable, income_script], capture_output=False)
    if res_income.returncode != 0:
        print("\n=> FAIL: REGRESSION TEST (INCOME) FAILED")
        sys.exit(1)
        
    print("\nRunning test: test_managed_portfolio.py...")
    res_mp = subprocess.run([sys.executable, mp_script], capture_output=False)
    if res_mp.returncode != 0:
        print("\n=> FAIL: REGRESSION TEST (MP) FAILED")
        sys.exit(1)
        
    print("\nRunning test: test_invariants.py...")
    res_inv = subprocess.run([sys.executable, invariants_script], capture_output=False)
    if res_inv.returncode != 0:
        print("\n=> FAIL: INVARIANTS TEST SUMMARY FAILED")
        sys.exit(1)
        
    # 3. Run Integration Tests
    print("\nRunning test: test_integration.py...")
    res_integ = subprocess.run([sys.executable, integration_script], capture_output=False)
    if res_integ.returncode != 0:
        print("\n=> FAIL: INTEGRATION TESTS FAILED")
        sys.exit(1)
        
    # 4. Run Orchestration Tests
    print("\nRunning test: test_orchestration.py...")
    res_orch = subprocess.run([sys.executable, orchestration_script], capture_output=False)
    if res_orch.returncode != 0:
        print("\n=> FAIL: ORCHESTRATION TESTS FAILED")
        sys.exit(1)
        
    print("\nRunning test: test_portfolio_orchestrator.py...")
    res_port_orch = subprocess.run([sys.executable, portfolio_orch_script], capture_output=False)
    if res_port_orch.returncode != 0:
        print("\n=> FAIL: PORTFOLIO ORCHESTRATOR TESTS FAILED")
        sys.exit(1)
        
    print("\n===================================")
    print("=> CLEAR PASS: ALL TESTS SUCCEEDED ")
    print("===================================")
    sys.exit(0)

if __name__ == "__main__":
    main()
