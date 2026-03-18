import os
import sys
import subprocess

def main():
    print("===================================")
    print("   AI ADVISORY FULL TEST SUITE     ")
    print("===================================")
    
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    app_boot_script = os.path.join(tests_dir, "app_boot_test.py")
    chat_resilience_script = os.path.join(tests_dir, "test_chat_resilience.py")
    smoke_script = os.path.join(tests_dir, "smoke_test.py")
    regression_script = os.path.join(tests_dir, "regression_test.py")
    
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
        
    # 2. Run Regression Test
    print("\nRunning test: regression_test.py...")
    res_regress = subprocess.run([sys.executable, regression_script], capture_output=False)
    if res_regress.returncode != 0:
        print("\n=> FAIL: REGRESSION TEST SUITE FAILED")
        sys.exit(1)
        
    print("\n===================================")
    print("=> CLEAR PASS: ALL TESTS SUCCEEDED ")
    print("===================================")
    sys.exit(0)

if __name__ == "__main__":
    main()
