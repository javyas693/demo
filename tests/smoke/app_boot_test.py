import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from ai_advisory.api.server import app

def run_app_boot_test():
    print("--- RUNNING APP BOOT TEST ---")
    client = TestClient(app)
    
    print("Testing GET /health endpoint...")
    response = client.get("/health")
    
    if response.status_code != 200:
        print(f"Error: Expected 200, got {response.status_code}")
        return False
        
    data = response.json()
    if data.get("status") != "ok":
        print(f"Error: Expected status 'ok', got {data.get('status')}")
        return False
        
    if data.get("ok") is not True:
        print(f"Error: Expected ok=True, got {data.get('ok')}")
        return False
        
    print("=> APP BOOT TEST PASSED: Application started successfully and health endpoint responded.")
    return True

if __name__ == "__main__":
    success = run_app_boot_test()
    sys.exit(0 if success else 1)
