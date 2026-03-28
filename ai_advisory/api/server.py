from __future__ import annotations

from pathlib import Path
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from typing import Optional, Dict
from dotenv import load_dotenv
from dotenv import load_dotenv
import os
import logging

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(message)s",
    filename="simulation_output.txt",
    filemode="w"
)

# Keep track of our specific handler
_sim_handler = None
for h in logging.getLogger().handlers:
    if getattr(h, "baseFilename", "").endswith("simulation_output.txt"):
        _sim_handler = h

def clear_simulation_log():
    if _sim_handler:
        try:
            _sim_handler.stream.seek(0)
            _sim_handler.stream.truncate()
        except:
            pass

logging.getLogger().addHandler(logging.StreamHandler())

from ai_advisory.config import USE_LLM

if USE_LLM:
    from ai_advisory.agent.bot import ChatSessionManager
    
from ai_advisory.services.http_models import ClientProfile, ProfilePatch, OrchestrateResponse
from ai_advisory.services.profile_store import ProfileStore
from ai_advisory.services.orchestrator_service import propose as orchestrate_propose
from ai_advisory.services.http_models import (
    ClientProfile, ProfilePatch, OrchestrateResponse,
    SessionResponse, SignalsResponse, ProgramWorkspaceResponse,
)
from ai_advisory.services.capital_summary_service import compute_capital_summary
from ai_advisory.services.signals_service import compute_signals
import warnings
import numpy as np
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime
import uuid
from ai_advisory.api.plan_models import TradePlan, TradeAction, CombinedTradePlan, TransitionRequest
from ai_advisory.core.plan_store import PlanStore
from ai_advisory.strategy.strategy_unwind import StrategyUnwindEngine
from ai_advisory.services.frontier_service import FrontierService
from ai_advisory.services.api_models import FrontierProposalRequest, FrontierProposalResponse
from ai_advisory.services.portfolio_analytics import run_mp_backtest
import json
from ai_advisory.strategy.transition_manager import TransitionManager
from ai_advisory.strategy.anchor_income import AnchorIncomeEngine
from ai_advisory.frontier.store.fs_store import FileSystemFrontierStore
from ai_advisory.services.concentrated_service import _sanitize_for_json
from datetime import timedelta
from fastapi.responses import JSONResponse as jsonify
from ai_advisory.portfolio.portfolio_state import PortfolioState
from ai_advisory.orchestration.portfolio_orchestrator import run_portfolio_cycle
from ai_advisory.orchestration.time_simulator import simulate_portfolio
from ai_advisory.orchestration.trace_logger import trace_log, reset_trace

app = FastAPI(title="AI-Advisory API", version="0.1.0")
 
# Phase 8 — init SQLite DB on startup
from ai_advisory.db.database import init_db
init_db()
 
# Phase 7 — SPY benchmark cache

# Phase 7 — SPY benchmark cache (loaded once per process on first /simulate call)
_spy_prices_cache: dict | None = None

def _get_spy_prices() -> dict:
    global _spy_prices_cache
    if _spy_prices_cache is None:
        from ai_advisory.data.spy_loader import load_spy_prices
        _spy_prices_cache = load_spy_prices()
    return _spy_prices_cache


# Single instance of ChatSessionManager
session_manager = ChatSessionManager() if USE_LLM else None

# MOCK STATE FOR LOGIN
# In a real app, this would be handled via tokens/cookies
MOCK_LOGGED_IN = False
# CORS must be initialized immediately to handle all incoming origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # More permissive for dev connectivity
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parents[2]  # repo root
QUESTIONNAIRE_PATH = BASE_DIR / "Simplified Risk Profile Questionarre Algo.xlsx"
STORE_ROOT = BASE_DIR / "data" / "frontiers"

PROFILE_PATH = BASE_DIR / "data" / "profile.json"
profile_store = ProfileStore(PROFILE_PATH)

PLAN_STORE_DIR = BASE_DIR / "data"
plan_store = PlanStore(PLAN_STORE_DIR)

frontier_service = FrontierService(str(STORE_ROOT))

@app.post("/dev/reset")
def dev_reset():
    profile_store.clear()
    return {"ok": True}

@app.get("/profile", response_model=ClientProfile)
def get_profile():
    return profile_store.load()


@app.post("/profile/patch", response_model=ClientProfile)
def patch_profile(patch: ProfilePatch):
    result = profile_store.patch(patch)
    try:
        from ai_advisory.db.profile_store_db import save_profile
        save_profile(result.model_dump())
    except Exception as e:
        print(f"[DB] Profile save failed: {e}")
    return result

@app.get("/session", response_model=SessionResponse)
def get_session():
    profile = profile_store.load()
    global MOCK_LOGGED_IN

    positions = getattr(profile, "positions", None) or []
    cash = getattr(profile, "cash_to_invest", None)
    risk = getattr(profile, "risk_score", None)

    has_profile = bool(
        (risk is not None)
        or (cash is not None and float(cash) > 0)
        or (len(positions) > 0)
    )

    return SessionResponse(
        has_profile=has_profile,
        is_logged_in=MOCK_LOGGED_IN,
        profile=profile
    )

@app.post("/login")
def login():
    global MOCK_LOGGED_IN
    MOCK_LOGGED_IN = True
    return {"status": "success", "is_logged_in": True}

@app.post("/logout")
def logout():
    global MOCK_LOGGED_IN
    MOCK_LOGGED_IN = False
    return {"status": "success", "is_logged_in": False}



@app.get("/capital/summary")
def capital_summary():
    profile = profile_store.load()
    return compute_capital_summary(profile)


@app.get("/signals", response_model=SignalsResponse)
def signals():
    profile = profile_store.load()
    sigs = compute_signals(profile)
    return SignalsResponse(signals=sigs)


PROGRAM_MAP = {
    "concentrated_position": ("Concentrated Position Workspace", "Manage large single-stock exposures, risk reduction, and covered calls."),
    "risk_reduction": ("Risk Reduction Workspace", "Monitoring and active adjustments for risk reduction."),
    "tax_optimization": ("Tax Optimization Workspace", "Monitoring and active adjustments for tax optimization."),
    "income_generation": ("Income Generation Workspace", "Monitoring and active adjustments for income generation."),
    "core_allocation": ("Core Allocation Workspace", "Monitoring and active adjustments for core allocation."),
    "anchor_income": ("Anchor Income Strategy", "Tactical income generation with drawdown-based equity swaps.")
}

@app.get("/programs/{program_key}", response_model=ProgramWorkspaceResponse)
def program_workspace(program_key: str):
    profile = profile_store.load()
    sigs = [s for s in compute_signals(profile) if s.program == program_key]

    if program_key not in PROGRAM_MAP:
        raise HTTPException(status_code=404, detail=f"Unknown program_key: {program_key}")

    title, subtitle = PROGRAM_MAP[program_key]

    status = "active"
    if any(s.severity in ("medium", "high") for s in sigs):
        status = "action_required"
    elif sigs:
        status = "monitoring"

    # Reuse a consistent workspace shape (values can be replaced by real engines later)
    summary_cards = []
    if program_key in ["risk_reduction", "concentrated_position"]:
        summary_cards = [
            {"label": "Modeled Volatility", "value": "18%", "tag": "Forecast"},
            {"label": "Modeled Income", "value": "3.8%", "tag": "Moderate"},
            {"label": "Concentration", "value": "25%", "tag": "Max"},
            {"label": "Diversification Score", "value": "72", "tag": "Warning"},
        ]
    elif program_key == "tax_optimization":
        summary_cards = [
            {"label": "Tax Impact (YTD)", "value": "+$12,450", "tag": "Estimated"},
            {"label": "Harvesting Status", "value": "Monitoring", "tag": None},
        ]
    elif program_key == "income_generation":
        summary_cards = [
            {"label": "Income (Quarter)", "value": "$4,250", "tag": "Received"},
            {"label": "Income Target", "value": "On Track", "tag": None},
        ]
    elif program_key == "anchor_income":
        summary_cards = [
            {"label": "Parking Lot Yield", "value": "10.8%", "tag": "Targeted"},
            {"label": "Current Drawdown", "value": "0.0%", "tag": "Monitoring"},
            {"label": "Total Portfolio", "value": "$1,000,000", "tag": "Estimated"},
        ]
    else:  # core_allocation
        summary_cards = [
            {"label": "Alignment", "value": f"{getattr(profile, 'risk_score', 50)}/100", "tag": "Aligned"},
            {"label": "Rebalance", "value": "Monitoring", "tag": None},
        ]

    return ProgramWorkspaceResponse(
        program=program_key,  # ProgramKey enforced by response_model
        status=status,
        summary_title=title,
        summary_subtitle=subtitle,
        summary_cards=summary_cards,
        signals=sigs,
        tabs=["overview", "allocation", "historical", "future", "trades"],
    )

@app.get("/programs/concentrated_position/history")
def get_cp_history():
    history_path = BASE_DIR / "data" / "cp_history.json"
    if history_path.exists():
        try:
            with open(history_path, "r") as f:
                return json.load(f)
        except:
            return None
    return None

class CoreParams(BaseModel):
    initial_shares: int
    cost_basis: float
    starting_cash: float
    ticker: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    tlh_inventory: float = 0.0

class CoveredCallParams(BaseModel):
    coverage_pct: float = 50.0
    target_delta: float = 0.20
    target_dte_days: int = 30
    profit_capture_pct: float = 0.50

class TLHParams(BaseModel):
    harvest_trigger_pct: float = 1.0
    max_shares_per_month: int = 200
    mode: str = "harvest_hold"

class TaxParams(BaseModel):
    tax_mode: str = "OFF"

class ConcentratedSimulatePayload(BaseModel):
    strategy: str
    core: CoreParams
    covered_call: Optional[CoveredCallParams] = None
    strategy_mode: Optional[str] = "harvest"
    share_reduction_trigger_pct: Optional[float] = None
    tlh: Optional[TLHParams] = None
    tax: Optional[TaxParams] = None

def adapt_request(payload: ConcentratedSimulatePayload) -> dict:
    strategy = payload.strategy
    core = payload.core

    params = {
        "initial_shares": core.initial_shares,
        "cost_basis": core.cost_basis,
        "starting_cash": core.starting_cash,
        "ticker": core.ticker,
        "start_date": core.start_date,
        "end_date": core.end_date,
    }

    cc = payload.covered_call
    if cc is not None:
        params["coverage_pct"] = cc.coverage_pct
        params["target_delta"] = cc.target_delta
        params["target_dte_days"] = cc.target_dte_days
        params["profit_capture_pct"] = cc.profit_capture_pct

    tlh = payload.tlh
    if tlh is not None:
        params["stop_loss_multiple"] = tlh.harvest_trigger_pct
        params["max_shares_per_month"] = tlh.max_shares_per_month
        params["loss_handling_mode"] = tlh.mode

    params["strategy_mode"] = payload.strategy_mode
    params["share_reduction_trigger_pct"] = payload.share_reduction_trigger_pct

    tax = payload.tax
    if tax is not None:
        params["tax_mode"] = tax.tax_mode

    return params


@app.post("/programs/concentrated_position/simulate")
def simulate_concentrated_position(payload: ConcentratedSimulatePayload):
    clear_simulation_log()

    reset_trace()
    trace_log("\n" + "="*50)
    trace_log(f"--- [MODULE 1] TRACE START: /programs/concentrated_position/simulate ---")
    
    params = adapt_request(payload)
    
    ticker = params["ticker"]
    initial_shares = params.get("initial_shares", 1000)
    cost_basis = params.get("cost_basis", 0.0)
    starting_cash = params.get("starting_cash", 0.0)
    strategy_mode = params.get("strategy_mode", "harvest")
    
    trigger_pct = (
        payload.share_reduction_trigger_pct
        if payload.share_reduction_trigger_pct is not None
        else 0.3
    )
    
    # Debug print for verification
    print(f"STRATEGY MODE: {strategy_mode}")
    print(f"API INPUT trigger: {trigger_pct}")
    print(f"CONCENTRATED START - Strategy: {payload.strategy} | Ticker: {ticker} | Basis: {cost_basis} | Cash: {starting_cash}")

    profile = profile_store.load()

    end_date_str = params.get("end_date") if params.get("end_date") else datetime.now().strftime("%Y-%m-%d")
    start_date_str = params.get("start_date") if params.get("start_date") else (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

    engine = StrategyUnwindEngine(
        ticker=ticker,
        start_date=start_date_str,
        end_date=end_date_str,
        initial_shares=initial_shares
    )

    result = engine.run_covered_call_overlay(
        coverage_pct=params.get("coverage_pct", 50.0),
        target_dte_days=params.get("target_dte_days", 30),
        target_delta=params.get("target_delta", 0.20),
        profit_capture_pct=params.get("profit_capture_pct", 0.50),
        share_reduction_trigger_pct=trigger_pct,
        cost_basis=cost_basis,
        strategy_mode=strategy_mode,
        starting_cash=starting_cash,
        max_shares_per_month=params.get("max_shares_per_month", 200),
        stop_loss_multiple=params.get("stop_loss_multiple", 1.0)
    )


    print("DEBUG RESULT KEYS:", result.keys())
    print("DEBUG SUMMARY:", result.get("summary"))

    # Convert pandas DataFrame to JSON
    if "time_series" in result:
        result["time_series"] = result["time_series"].to_dict(orient="records")

    summary = result.get("summary", {})

    initial = summary.get("initial_shares")
    final = summary.get("final_shares")

    if initial is not None and final is not None:
        summary["shares_sold"] = int(initial - final)

    result["summary"] = summary

    return result

class OrchestrateRequest(BaseModel):
    total_portfolio_value: float
    cash: float
    concentrated_position_value: float
    income_portfolio_value: float = 0.0
    model_portfolio_value: float = 0.0
    tlh_inventory: float
    risk_score: float
    income_preference: float
    ticker: str = "SPY"
    start_date: str = "2023-01-01"
    end_date: str = "2023-10-01"
    initial_shares: float = 8000.0
    unwind_cost_basis: float = 100.0

@app.post("/api/portfolio/orchestrate")
def api_portfolio_orchestrate(req: OrchestrateRequest):
    # Enforce STRICT concentrated baseline state
    income_val = 0.0
    model_val = 0.0
    total_val = req.concentrated_position_value + req.cash

    state = PortfolioState(
        total_portfolio_value=total_val,
        cash=req.cash,
        ticker=req.ticker,
        shares=req.initial_shares,
        current_price=req.concentrated_position_value / req.initial_shares if req.initial_shares > 0 else 0.0,
        cost_basis=req.unwind_cost_basis,
        market_value=req.concentrated_position_value,
        income_value=income_val,
        annual_income=0.0, # Will be set generically or overridden 
        model_value=model_val,
        tlh_inventory=req.tlh_inventory,
        risk_score=req.risk_score
    )
    res = run_portfolio_cycle(
        state=state,
        ticker=req.ticker,
        start_date=req.start_date,
        end_date=req.end_date,
        initial_shares=req.initial_shares,
        unwind_cost_basis=req.unwind_cost_basis,
        income_preference=req.income_preference
    )
    
    # Save history array to disk for the frontend history timeline tab to fetch
    history_path = BASE_DIR / "data" / "orchestrator_history.json"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(history_path, "w") as f:
            # Cleanly extract the time_series to disk
            ts = res.get("nested_reports", {}).get("concentrated_position", {}).get("time_series", [])
            json.dump(ts, f)
    except Exception as e:
        print(f"Failed to save orchestrator_history: {e}")
        
    return res

@app.get("/api/portfolio/history")
def api_portfolio_history():
    history_path = BASE_DIR / "data" / "orchestrator_history.json"
    if history_path.exists():
        try:
            with open(history_path, "r") as f:
                return json.load(f)
        except:
            return []
    return []

class ProjectionRequest(BaseModel):
    # Current portfolio state
    cp_value:           float
    income_value:       float = 0.0
    model_value:        float = 0.0
    cash:               float = 0.0
    cost_basis:         float           # per-share cost basis
    current_cp_price:   float           # current CP price per share
    ticker:             str = "SPY"

    # Projection parameters
    horizon_years:      int = 20
    income_preference:  float = 0.5     # fraction of proceeds → income sleeve

    # Unwind schedule: {year: fraction_of_remaining_cp_to_sell}
    # e.g. {"1": 0.10, "2": 0.10, ...}
    unwind_schedule:    Dict[str, float] = {}

    # Target concentration unwind (dynamic per-path)
    # If set, overrides unwind_schedule
    target_concentration_pct: Optional[float] = None   # e.g. 0.15 for 15%
    spread_years:             int = 5                  # glide-path window

    # Return/vol/tax overrides — all optional, defaults applied for missing keys
    return_assumptions: Optional[Dict[str, float]] = None


@app.post("/api/portfolio/projection")
def api_portfolio_projection(req: ProjectionRequest):
    """
    Phase 10 — Forward Monte Carlo projection.
    Projects CP, income, model, and total portfolio forward N years.
    Returns 10th / 50th / 90th percentile bands per sleeve.
    """
    from ai_advisory.projection.projection_engine import run_projection
    from ai_advisory.db.price_store import load_prices_from_cache
    import pandas as pd

    # Attempt to load CP price history for auto-fitting return/vol
    cp_price_series = None
    try:
        cached = load_prices_from_cache([req.ticker])
        raw = cached.get(req.ticker, {})
        if len(raw) >= 60:
            s = pd.Series(raw)
            s.index = pd.to_datetime(s.index)
            s = s.sort_index()
            cp_price_series = s.resample("BME").last().dropna()
    except Exception:
        pass

    result = run_projection(
        cp_value=req.cp_value,
        income_value=req.income_value,
        model_value=req.model_value,
        cash=req.cash,
        cost_basis=req.cost_basis,
        current_cp_price=req.current_cp_price,
        horizon_years=req.horizon_years,
        unwind_schedule=req.unwind_schedule,
        target_concentration_pct=req.target_concentration_pct,
        spread_years=req.spread_years,
        income_preference=req.income_preference,
        return_assumptions=req.return_assumptions,
        ticker=req.ticker,
        cp_price_series=cp_price_series,
    )

    return result
class TimeSimulateRequest(OrchestrateRequest):
    horizon_months: int = 12
    gate_overrides: Optional[Dict[str, str]] = None
    # Valid keys: MOMENTUM_GATE, MACRO_GATE, VOLATILITY_GATE,
    #             PRICE_TRIGGER_GATE, CONCENTRATION_GATE,
    #             TLH_CAPACITY_GATE, UNREALIZED_GAIN_GATE
    # Valid value: "suppress"
    # CLIENT_CONSTRAINT is never suppressible.
 
 
@app.post("/api/portfolio/simulate")
def api_portfolio_simulate(req: TimeSimulateRequest):
    clear_simulation_log()
 
    reset_trace()
    trace_log("\n" + "="*50)
    trace_log(f"--- [MODULE 1] TRACE START: /api/portfolio/simulate ---")
    trace_log(f"INPUT RECEIVED: {req.model_dump()}")
    trace_log("="*50 + "\n")
 
    # Enforce STRICT concentrated baseline state
    income_val = 0.0
    model_val = 0.0
    total_val = req.concentrated_position_value + req.cash
 
    state = PortfolioState(
        total_portfolio_value=total_val,
        cash=req.cash,
        ticker=req.ticker,
        shares=req.initial_shares,
        current_price=req.concentrated_position_value / req.initial_shares if req.initial_shares > 0 else 0.0,
        cost_basis=req.unwind_cost_basis,
        market_value=req.concentrated_position_value,
        income_value=income_val,
        annual_income=0.0,
        model_value=model_val,
        tlh_inventory=req.tlh_inventory,
        risk_score=req.risk_score
    )
 
    # Primary simulation run
    spy_prices = _get_spy_prices()
    timeline, monthly_intelligence = simulate_portfolio(
        initial_state=state,
        ticker=req.ticker,
        initial_shares=req.initial_shares,
        cost_basis=req.unwind_cost_basis,
        horizon_months=req.horizon_months,
        income_preference=req.income_preference,
        spy_prices=spy_prices,
    )
 
    # Phase 6 — what-if run when gate_overrides are provided
    monthly_intelligence_whatif = None
    if req.gate_overrides:
        state_whatif = PortfolioState(
            total_portfolio_value=total_val,
            cash=req.cash,
            ticker=req.ticker,
            shares=req.initial_shares,
            current_price=req.concentrated_position_value / req.initial_shares if req.initial_shares > 0 else 0.0,
            cost_basis=req.unwind_cost_basis,
            market_value=req.concentrated_position_value,
            income_value=income_val,
            annual_income=0.0,
            model_value=model_val,
            tlh_inventory=req.tlh_inventory,
            risk_score=req.risk_score
        )
        _, monthly_intelligence_whatif = simulate_portfolio(
            initial_state=state_whatif,
            ticker=req.ticker,
            initial_shares=req.initial_shares,
            cost_basis=req.unwind_cost_basis,
            horizon_months=req.horizon_months,
            income_preference=req.income_preference,
            gate_overrides=req.gate_overrides,
            spy_prices=spy_prices,
        )
 
    total_capital_released = sum(s.get("capital_released_this_step", 0.0) for s in timeline)
    total_allocated_income = sum(s.get("allocation_to_income_this_step", 0.0) for s in timeline)
    total_allocated_model  = sum(s.get("allocation_to_model_this_step", 0.0) for s in timeline)
 
    timeline_series = {
        "total_portfolio": [s.get("total_portfolio_value", 0.0) for s in timeline],
        "concentrated":    [s.get("concentrated_value", 0.0) for s in timeline],
        "income":          [s.get("income_value", 0.0) for s in timeline],
        "model":           [s.get("model_value", 0.0) for s in timeline],
        "cash":            [s.get("cash", 0.0) for s in timeline],
    }
 
    response_dict = {
        "state":                        timeline[-1] if timeline else None,
        "timeline":                     timeline,
        "timeline_series":              timeline_series,
        "monthly_intelligence":         monthly_intelligence,
        "monthly_intelligence_whatif":  monthly_intelligence_whatif,  # None when no overrides
        "summary": {
            "total_capital_released": total_capital_released,
            "total_allocated_income": total_allocated_income,
            "total_allocated_model":  total_allocated_model,
            "final_state":            timeline[-1] if timeline else None,
        }
    }
 
    trace_log("\n" + "="*50)
    trace_log("--- [MODULE 6] OUTPUT TRACE ---")
    trace_log(f"Final step values: {response_dict['summary']}")
    trace_log(f"Reconciliation: {timeline[-1].get('reconciliation') if timeline else 'None'}")
    trace_log("="*50 + "\n")
 
    # Phase 8 — persist to DB (non-blocking, won't affect response)
    try:
        from ai_advisory.db.sim_store import save_simulation, save_whatif
        from ai_advisory.db.gate_store import log_gate_override_run
        save_simulation(req.model_dump(), timeline, monthly_intelligence)
        if req.gate_overrides and monthly_intelligence_whatif:
            save_whatif(req.gate_overrides, monthly_intelligence_whatif)
            log_gate_override_run(req.gate_overrides, monthly_intelligence_whatif)
    except Exception as e:
        print(f"[DB] Simulation persist failed: {e}")
 
    return _sanitize_for_json(response_dict)


@app.get("/api/portfolio/gate-override-history")
def api_gate_override_history():
    from ai_advisory.db.gate_store import load_gate_override_history
    return load_gate_override_history()

class MPSimulatePayload(BaseModel):
    target_weights: dict[str, float]
    initial_capital: float
    start_date: str
    end_date: str

@app.post("/programs/core_allocation/simulate")
def simulate_mp(payload: MPSimulatePayload):
    result = run_mp_backtest(
        target_weights=payload.target_weights,
        initial_capital=payload.initial_capital,
        start_date=payload.start_date,
        end_date=payload.end_date
    )
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
        
    sanitized_result = _sanitize_for_json(result)
        
    history_path = BASE_DIR / "data" / "mp_history.json"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(history_path, "w") as f:
            json.dump(sanitized_result, f, indent=2)
    except Exception as e:
        print(f"Failed to save mp_history: {e}")
        
    return sanitized_result

@app.get("/programs/core_allocation/history")
def get_mp_history():
    history_path = BASE_DIR / "data" / "mp_history.json"
    if history_path.exists():
        try:
            with open(history_path, "r") as f:
                return json.load(f)
        except:
            return None
    return None

class AnchorIncomeSimulatePayload(BaseModel):
    start_date: str
    end_date: str
    initial_capital: float = 1000000.0
    reinvest_pct: float = 0.0

@app.api_route("/programs/anchor_income/simulate", methods=["POST", "OPTIONS"])
async def simulate_anchor_income(payload: AnchorIncomeSimulatePayload):
    try:
        # 3. ENVIRONMENT DUALITY: Hard reset to payload capital
        # REMOVED: Auto-cloning of live account state to prioritize payload start
        initial_capital = payload.initial_capital
        
        engine = AnchorIncomeEngine(
            start_date=payload.start_date,
            end_date=payload.end_date,
            initial_capital=initial_capital,
            reinvest_pct=payload.reinvest_pct
        )
        result = engine.simulate()
        
        sanitized_result = _sanitize_for_json(result)
        
        # Save to history file for persistence in UI tab (Local Cache, not User Account)
        history_path = BASE_DIR / "data" / "anchor_income_history.json"
        history_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(history_path, "w") as f:
                json.dump(sanitized_result, f, indent=2)
        except Exception as e:
            print(f"Failed to save anchor_income_history: {e}")
            
        return sanitized_result
    except Exception as e:
        print(f"Failed to simulate anchor income: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/programs/anchor_income/history")
def get_anchor_income_history():
    history_path = BASE_DIR / "data" / "anchor_income_history.json"
    if history_path.exists():
        try:
            with open(history_path, "r") as f:
                return json.load(f)
        except:
            return None
    return None


@app.post("/api/v1/programs/transition/propose", response_model=CombinedTradePlan)
def propose_transition(req: TransitionRequest):
    """
    Unified transition planner endpoint. 
    1. Simulates the CP unwind using StrategyUnwindEngine.
    2. Extracts net proceeds.
    3. Simulates the MP reinvestment using TransitionManager.
    4. Returns a CombinedTradePlan.
    """
    profile = profile_store.load()
    if not profile.positions:
        raise HTTPException(status_code=400, detail="No concentrated position found")

    # For MVP, just grab the first position
    pos = profile.positions[0]

    end_date_str = datetime.now().strftime("%Y-%m-%d")
    start_date_str = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

    # 1. Step A (The Sell): Call StrategyUnwindEngine
    engine = StrategyUnwindEngine(
        ticker=pos.symbol,
        start_date=start_date_str,
        end_date=end_date_str,
        initial_shares=pos.shares
    )

    unwind_result = engine.run_covered_call_overlay(
        coverage_pct=req.coverage_pct,
        target_dte_days=req.target_dte_days,
        target_delta=req.target_delta,
        share_reduction_trigger_pct=req.share_reduction_trigger_pct,
        cost_basis=pos.cost_basis,
        loss_handling_mode=req.loss_handling_mode,
        starting_cash=req.starting_cash,
        max_shares_per_month=req.max_shares_per_month
    )

    summary = unwind_result.get("summary", {})
    
    # Extract total tax and cash harvested from the summary
    total_tax_estimate = summary.get("estimated_tax", 0.0)
    
    # 2. Step B (The Net): Extract tax and calculate net proceeds
    # Note: We are mocking the proceeds calculation directly from shares sold * current price 
    # since the simulator doesn't give us the clean ending cash balance delta in all scenarios yet.
    # In a full implementation, the UI's inputs or simulator state handles the net cash generated natively.
    initial_shares = summary.get("initial_shares", 0.0)
    final_shares = summary.get("final_shares", 0.0)
    shares_sold = initial_shares - final_shares
    assumed_cp_price = 1000.0 # MVP static price
    gross_proceeds = shares_sold * assumed_cp_price
    net_proceeds = gross_proceeds - total_tax_estimate

    # Construct the Sell Orders plan covering the unwind
    # We aggregate the unwind into a single high-level TradePlan "SELL" action for the proposal
    sell_actions = []
    if shares_sold > 0:
        sell_actions.append(
            TradeAction(
                type="SELL",
                symbol=pos.symbol,
                shares=shares_sold,
                dollars=gross_proceeds,
                notes=f"Overlaid Covered Call Strategy. Tax escrow withholding: ${total_tax_estimate:,.2f}"
            )
        )
        
    sell_plan = TradePlan(
        plan_id=str(uuid.uuid4()),
        program_key="concentrated_position",
        created_at=datetime.utcnow(),
        summary=f"Unwind strategy for {pos.symbol}",
        why=["Execute planned reduction via CC overlay."],
        cash_delta_estimate=net_proceeds, # The net cash joining the core
        actions=sell_actions,
        requires_approval=True
    )

    # 3. Step C (The Buy): Pass net_proceeds into TransitionManager
    store = FileSystemFrontierStore(root=str(STORE_ROOT))
    
    try:
        transition = TransitionManager(
            store=store,
            as_of=end_date_str, # Using today as the 'as_of' for frontier lookup
            model_id=req.model_id
        )
        # Even if net_proceeds is 0, we can still generate an empty set of buy orders 
        # but realistically no net_proceeds means no reinvestments
        buy_orders = transition.get_reinvestment_orders(
            net_proceeds=net_proceeds, 
            risk_score=req.risk_score
        )
    except Exception as e:
        # Fallback if there's no active frontier or data mismatch
        print(f"Failed to generate reinvestments: {e}")
        buy_orders = []

    # 4. Step D (The Result): Wrap it gracefully
    combined = CombinedTradePlan(
        sell_orders=[sell_plan],
        buy_orders=buy_orders,
        total_tax_estimate=total_tax_estimate,
        net_reinvestment_total=net_proceeds
    )

    # Sanitization Layer to strip numpy types and ensure clean FastAPI response
    sanitized_dict = _sanitize_for_json(combined.model_dump())
    
    return CombinedTradePlan(**sanitized_dict)

@app.post("/orchestrate/propose", response_model=OrchestrateResponse)
def orchestrate():
    profile = profile_store.load()
    return orchestrate_propose(profile)

class FrontierProposePayload(BaseModel):
    risk_score: int
    model_id: str = "core"

def get_latest_frontier_date(store_root: Path) -> str:
    if not store_root.exists():
        return datetime.now().strftime("%Y-%m-%d")
    dirs = [d.name for d in store_root.iterdir() if d.is_dir() and d.name.startswith("asof=")]
    if not dirs:
        return datetime.now().strftime("%Y-%m-%d")
    latest_dir = sorted(dirs)[-1]
    return latest_dir.replace("asof=", "")

@app.post("/frontier/propose", response_model=FrontierProposalResponse)
def frontier_propose(payload: FrontierProposePayload):
    as_of_date = get_latest_frontier_date(STORE_ROOT)
    req = FrontierProposalRequest(
        as_of=as_of_date,
        model_id=payload.model_id,
        risk_score=payload.risk_score
    )
    try:
        return frontier_service.propose(req)
    except Exception as e:
        print(f"Frontier Propose Error: {e}. Returning fallback mock data.")
        # Dynamic fallback data based on risk score (1-100)
        base_eq = 0.20 + (payload.risk_score / 100.0) * 0.80  # Scale 20% -> 100% equity
        return FrontierProposalResponse(
            as_of=as_of_date,
            model_id=payload.model_id,
            frontier_version="mock_v1",
            frontier_status="APPROVED",
            risk_score=payload.risk_score,
            exp_return=round(0.04 + (payload.risk_score / 100.0) * 0.08, 3),
            vol=round(0.05 + (payload.risk_score / 100.0) * 0.15, 3),
            sharpe=0.66,
            target_weights={
                "VTI": round(base_eq * 0.7, 3),
                "VXUS": round(base_eq * 0.3, 3),
                "BND": round(1.0 - base_eq, 3)
            }
        )

@app.get("/health")
def health():
    return {
        "status": "ok",
        "ok": True,
        "questionnaire_exists": QUESTIONNAIRE_PATH.exists(),
        "questionnaire_path": str(QUESTIONNAIRE_PATH),
        "store_root_exists": STORE_ROOT.exists(),
        "store_root": str(STORE_ROOT),
    }

class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str
import traceback # Make sure this is at the very top of your server.py file!

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Sends a message to the AI agent and returns the response.
    """
    if not USE_LLM:
        return {
            "status": "disabled",
            "message": "Chatbot disabled (test/dev mode)"
        }

    conversation_id = request.conversation_id
    
    if not conversation_id:
        conversation_id = str(uuid.uuid4())
        
    try:
        # This is where the magic (and currently the crash) happens
        agent_response = await session_manager.send_message(
            message=request.message,
            conversation_id=conversation_id,
            user_id="web-user"
        )
        
        return agent_response
    except Exception as e:
        # THIS IS THE KEY: It prints the 'Internal' error to your terminal
        print("❌ AGENT CRASH DETECTED:")
        traceback.print_exc() 
        
        # This still sends the 500 to the browser
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

@app.post("/risk/score")
def risk_score(payload: dict):
    """
    payload:
      {
        "answers_by_group": { "Group Name": 1 or "label", ... },
        "strict": false
      }
    """
    try:
        from ai_advisory.risk.risk_engine_simplified import (
            load_simplified_questionnaire,
            score_simplified_1_to_100,
        )

        answers = payload.get("answers_by_group", {})
        strict = bool(payload.get("strict", False))

        q = load_simplified_questionnaire(QUESTIONNAIRE_PATH)
        rp = score_simplified_1_to_100(
            answers_by_group=answers,
            questionnaire=q,
            strict=strict,
        )
        return {
            "risk_score": rp.risk_score,
            "confidence": rp.confidence,
            "drivers": rp.drivers,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/plans/propose", response_model=dict)
def propose_plan(payload: dict):
    program_key = payload.get("program_key")
    params = payload.get("params", {})
    
    profile = profile_store.load()
    positions = getattr(profile, "positions", [])
    
    plan_id = str(uuid.uuid4())
    actions = []
    
    # Deterministic price assumptions for v0
    assumed_price = 1.0
    
    if program_key in ("risk_reduction", "concentrated_position"):
        if not positions:
            raise HTTPException(status_code=400, detail="No concentrated position found to reduce.")
            
        target_pos = positions[0] # assuming the first one is the concentrated one
        
        intensity = params.get("intensity", 50) # 0 to 100 
        reduction_pct = (intensity / 100.0) * 0.30
        
        shares_to_sell = target_pos.shares * reduction_pct
        if shares_to_sell <= 0:
            shares_to_sell = 0 # No op
            
        cash_generated = shares_to_sell * assumed_price
        
        if shares_to_sell > 0:
            actions.append(TradeAction(
                type="SELL",
                symbol=target_pos.symbol,
                shares=shares_to_sell,
                dollars=cash_generated,
                notes=f"Reduce {target_pos.symbol} position by {reduction_pct*100:.1f}%"
            ))
            
            actions.append(TradeAction(
                type="ALLOCATE_CASH",
                amount=cash_generated,
                model_key=params.get("reinvest_model_key", "core_v0"),
                notes="Reinvest proceeds into core allocation"
            ))
            
        plan = TradePlan(
            plan_id=plan_id,
            program_key=program_key,
            created_at=datetime.utcnow(),
            summary=f"Risk Reduction Action Plan",
            why=["Concentration risk elevated.", "Cash generated will be diversified."],
            cash_delta_estimate=cash_generated,
            actions=actions
        )
        
    elif program_key == "income_generation" or program_key == "income_generation_v0":
        covered_pct = params.get("covered_pct", 50) / 100.0
        premium_rate = params.get("premium_rate", 0.006)
        withdraw_pct = params.get("withdraw_pct", 0) / 100.0
        
        if not positions:
            raise HTTPException(status_code=400, detail="No positions available to cover.")
            
        target_pos = positions[0]
        position_value = target_pos.shares * assumed_price
        
        notional_covered = position_value * covered_pct
        premium = notional_covered * premium_rate
        net_credit = premium * (1.0 - withdraw_pct)
        
        if premium > 0:
            actions.append(TradeAction(
                type="CASH_CREDIT",
                amount=net_credit,
                notes=f"Credit ${premium:.2f} premium (withdrawing {withdraw_pct*100:.1f}%)"
            ))
            
            if params.get("reinvest_model_key"):
                actions.append(TradeAction(
                    type="ALLOCATE_CASH",
                    amount=net_credit,
                    model_key=params.get("reinvest_model_key"),
                    notes="Reinvest premium into core"
                ))
            
        plan = TradePlan(
            plan_id=plan_id,
            program_key=program_key,
            created_at=datetime.utcnow(),
            summary=f"Income Generation: Harvest ${premium:.2f} premium on {target_pos.symbol}",
            why=["Extracting yield from concentrated position.", f"Withdrawing {withdraw_pct*100:.0f}% of proceeds."],
            cash_delta_estimate=net_credit,
            actions=actions
        )
        
    elif program_key == "core_allocation":
        cash_available = profile.cash_to_invest
        
        if cash_available <= 0:
            raise HTTPException(status_code=400, detail="No cash available to allocate.")
            
        actions.append(TradeAction(
            type="ALLOCATE_CASH",
            amount=cash_available,
            model_key="core_v0",
            notes=f"Deploy ${cash_available:.2f} available cash into long-term Core Model"
        ))
        
        plan = TradePlan(
            plan_id=plan_id,
            program_key=program_key,
            created_at=datetime.utcnow(),
            summary=f"Core Allocation Action Plan",
            why=["Idle cash identified in the portfolio.", "Deploying to target beta exposures."],
            cash_delta_estimate=-cash_available,
            actions=actions
        )
        
    else:
        raise HTTPException(status_code=400, detail=f"Program key {program_key} not supported for proposals.")
        
    plan_store.save_plan(plan)
    return {"plan": plan.model_dump()}


@app.post("/plans/commit/{plan_id}", response_model=dict)
def commit_plan(plan_id: str, mode: str = "paper"):
    plan = plan_store.load_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
        
    profile = profile_store.load()
    assumed_price = 1.0 # deterministic mock override
    
    for action in plan.actions:
        if action.type == "SELL":
            for pos in profile.positions:
                if pos.symbol == action.symbol and action.shares:
                    pos.shares -= action.shares
                    profile.cash_to_invest += (action.shares * assumed_price)
                    break
            # Purge exhausted lots
            profile.positions = [p for p in profile.positions if p.shares > 0]
            
        elif action.type == "CASH_CREDIT":
            if action.amount:
                profile.cash_to_invest += action.amount
            
        elif action.type == "ALLOCATE_CASH":
            from ai_advisory.services.http_models import PositionIn
            amount: float = float(action.amount or 0.0)
            if amount > 0.0:
                profile.cash_to_invest -= amount
                # Mock ETF basket deployment 
                basket = {"VTI": 0.60, "VXUS": 0.30, "BND": 0.10}
                stub_prices = {"VTI": 250.0, "VXUS": 60.0, "BND": 70.0}
                
                for symbol, weight in basket.items():
                    alloc_dollars = amount * weight
                    alloc_shares = alloc_dollars / stub_prices[symbol]
                    
                    existing = next((p for p in profile.positions if p.symbol == symbol), None)
                    if existing:
                        current_cost = existing.cost_basis or stub_prices[symbol]
                        total_value = (existing.shares * current_cost) + alloc_dollars
                        total_shares = existing.shares + alloc_shares
                        existing.cost_basis = total_value / total_shares if total_shares > 0 else stub_prices[symbol]
                        existing.shares = total_shares
                    else:
                        profile.positions.append(PositionIn(
                            symbol=symbol,
                            shares=alloc_shares,
                            cost_basis=stub_prices[symbol],
                            sleeve="core"
                        ))
                    
    profile_store.save(profile)
    
    return {
        "plan": plan.model_dump(),
        "profile": profile.model_dump(),
        "capital_summary": compute_capital_summary(profile).model_dump(),
        "signals": SignalsResponse(signals=compute_signals(profile)).model_dump()
    }