import subprocess
import requests

payload = {
  "ticker": "AAPL",
  "initial_shares": 5000,
  "cost_basis": 100000,
  "horizon_months": 12,
  "risk_score": 60,
  "total_portfolio_value": 1000000,
  "cash": 0,
  "concentrated_position_value": 1000000,
  "tlh_inventory": 0,
  "income_preference": 50
}
res = requests.post("http://127.0.0.1:8000/api/portfolio/simulate", json=payload)
data = res.json()
print("Holdings:", data["timeline"][-1]["strategies"]["model"]["holdings"])
