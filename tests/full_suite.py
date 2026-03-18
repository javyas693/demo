import os
import sys
import subprocess

def main():
    print("===================================")
    print("   AI ADVISORY FULL TEST SUITE     ")
    print("===================================")
    
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    smoke_script = os.path.join(tests_dir, "smoke_test.py")
    regression_script = os.path.join(tests_dir, "regression_test.py")
    
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
