import asyncio
from httpx import AsyncClient
from ai_advisory.api.server import app

import json
from ai_advisory.api.server import TimeSimulateRequest, api_portfolio_simulate

try:
    payload_dict = {
        "total_portfolio_value": 1000000.0,
        "cash": 100000.0,
        "concentrated_position_value": 900000.0,
        "income_portfolio_value": 0.0,
        "model_portfolio_value": 0.0,
        "tlh_inventory": 0.0,
        "risk_score": 50,
        "income_preference": 50,
        "ticker": "NVDA",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "initial_shares": 1000,
        "unwind_cost_basis": 100.0,
        "horizon_months": 12
    }
    
    req = TimeSimulateRequest(**payload_dict)
    api_portfolio_simulate(req)
except Exception as e:
    import traceback
    traceback.print_exc()
