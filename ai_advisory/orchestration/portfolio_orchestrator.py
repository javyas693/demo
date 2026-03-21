from typing import Dict, Any, List, Optional
from datetime import datetime, date as _date

from ai_advisory.portfolio.portfolio_state import PortfolioState
from ai_advisory.strategy.strategy_unwind import StrategyUnwindEngine
from ai_advisory.strategy.anchor_income import AnchorIncomeEngine
from ai_advisory.services.portfolio_analytics import run_mp_backtest
from ai_advisory.orchestration.trace_logger import trace_log

# ─────────────────────────────────────────────────────────────────────────────
# Frontier weight lookup
# ─────────────────────────────────────────────────────────────────────────────

_FRONTIER_STORE_ROOT = "data/frontiers"

def _get_frontier_weights(
    risk_score: int,
    as_of: Optional[str] = None,
    model_id: str = "core",
) -> Dict[str, float]:
    """
    Retrieve target weights for a given risk_score from the persisted frontier.
    Builds the frontier on the fly if none exists for the given as_of date.
    Returns dict of {ticker: weight} summing to 1.0.
    """
    from ai_advisory.frontier.store.fs_store import FileSystemFrontierStore
    from ai_advisory.frontier.trade_flow_compat import weights_for_risk_score

    as_of = as_of or str(_date.today())
    store = FileSystemFrontierStore(root=_FRONTIER_STORE_ROOT)

    latest = store.get_latest(as_of, model_id)
    if not latest or not store.exists(as_of, latest):
        trace_log(f"[FRONTIER] No frontier for as_of={as_of} — building now...")
        _build_and_store_frontier(store, as_of, model_id)
        latest = store.get_latest(as_of, model_id)

    if not latest:
        trace_log("[FRONTIER] Build failed — using balanced proxy")
        return {"SPY": 0.60, "IEF": 0.30, "BIL": 0.10}

    try:
        return weights_for_risk_score(store, as_of, model_id, risk_score)
    except Exception as e:
        trace_log(f"[FRONTIER] Lookup error: {e} — using balanced proxy")
        return {"SPY": 0.60, "IEF": 0.30, "BIL": 0.10}


def _build_and_store_frontier(store, as_of: str, model_id: str) -> None:
    """Build frontier from live yfinance data and persist to store."""
    import os
    from ai_advisory.frontier.engine import build_frontier_from_config
    from ai_advisory.frontier.spec import FrontierSpec, UniverseSpec, ConstraintsSpec
    from ai_advisory.core.frontier_status import FrontierStatus

    spec = FrontierSpec(
        as_of=as_of,
        model_id=model_id,
        universe=UniverseSpec(assets=[]),
        constraints=ConstraintsSpec(bounds={}),
    )
    cache_path = os.path.join(_FRONTIER_STORE_ROOT, "yf_price_cache.pkl")

    try:
        result = build_frontier_from_config(
            spec=spec,
            allocation_sheet="Sub-Assets",
            prices_period="5y",
            cache_path=cache_path,
        )
        store.put(result)
        store.set_status(as_of, result.frontier_version, FrontierStatus.LOCKED)
        store.set_latest(as_of, model_id, result.frontier_version)
        trace_log(f"[FRONTIER] Built + locked: {result.frontier_version} ({len(result.points_sampled)} points)")
    except Exception as e:
        trace_log(f"[FRONTIER] Build error: {e}")

class PortfolioOrchestrator:
    """
    Master controller that sits exactly one level above the specialized engines.
    It does not recreate their math; it purely governs capital flow between them.
    """
    def __init__(self, state: PortfolioState, income_preference: float = 50.0):
        self.state = state
        self.income_preference = income_preference
        self.decision_log: List[Dict[str, Any]] = []
        
    def _log_decision(self, event: str, details: Dict[str, Any]):
        """Append a structured trace log mapping the causal sequence of orchestrator routing."""
        trace_log(f"--- [MODULE 4] LEDGER/EVENT TRACE: {event} ---")
        if event == "ORCHESTRATION_CYCLE_COMPLETE":
            trace_log("Trades explicitly handled via execution_layer.execute_trades")
        self.decision_log.append({
            "timestamp": datetime.now().isoformat(),
            "event": event,
            "details": details
        })

    def determine_de_risk_score(self) -> float:
        """
        TASK 4: De-risk scoring layer
        Calculates how heavily to hit the un-wind engine based on Risk Score and Concentration.
        """
        # A simple deterministic rule: Higher risk score = lower desire to unwind quickly
        # Lower risk score = higher desire to unwind an outsized concentrated position
        
        base_urgency = self.state.concentration_pct * 100.0  # 80% concentration = 80 urgency
        risk_adjustment = (100.0 - self.state.risk_score) / 100.0  # Risk score 20 = 0.8 multiplier
        
        de_risk_score = base_urgency * risk_adjustment
        
        self._log_decision("EVALUATE_RISK_POSTURE", {
            "concentration_pct": round(self.state.concentration_pct, 4),
            "risk_score_input": self.state.risk_score,
            "calculated_de_risk_score": round(de_risk_score, 2)
        })
        return de_risk_score

    def determine_capital_release_params(self, de_risk_score: float, unwind_urgency: float = 0.5) -> Dict[str, Any]:
        """
        TASK 5: Capital Release Strategy Map
        Maps the de-risk score and unwind urgency into operational unwind parameters.

        unwind_urgency (0–1) from signal engine:
          - 0.0 = no urgency (bullish momentum, low concentration)
          - 1.0 = max urgency (bearish momentum, high concentration, risk_off)
        """
        # Trigger: lower threshold = more aggressive selling
        # At urgency=0: trigger requires 30-40% gain before selling
        # At urgency=1: trigger is 5% gain (sell almost immediately)
        base_trigger = max(0.05, 0.40 - (de_risk_score / 200.0))
        trigger_pct  = base_trigger * (1.0 - unwind_urgency * 0.7)  # compress by up to 70%
        trigger_pct  = max(0.05, trigger_pct)

        # Max shares per month scales with urgency
        if de_risk_score < 40 and unwind_urgency < 0.3:
            max_shares = 200       # low urgency, low risk score
        elif unwind_urgency > 0.7 or de_risk_score > 70:
            max_shares = 750       # high urgency — accelerate unwind
        else:
            max_shares = 400       # mid range
        
        params = {
            "strategy_mode": "tax_neutral",
            "enable_tax_loss_harvest": True,
            "share_reduction_trigger_pct": trigger_pct,
            "max_shares_per_month": max_shares,
        }
        self._log_decision("MAP_UNWIND_PARAMS", {
            "de_risk_score":    round(de_risk_score, 2),
            "unwind_urgency":   round(unwind_urgency, 3),
            "trigger_pct":      round(trigger_pct, 4),
            "max_shares":       max_shares,
            "mapped_params":    params,
        })
        return params

    def determine_allocations(self, released_cash: float) -> Dict[str, float]:
        """
        TASK 7: Allocation Decision
        Deterministic split based strictly on user preference vectors.
        """
        income_weight = self.income_preference / 100.0
        model_weight = 1.0 - income_weight
        
        alloc_to_income = released_cash * income_weight
        alloc_to_model = released_cash * model_weight
        
        self._log_decision("SPLIT_RELEASED_CAPITAL", {
            "released_cash": released_cash,
            "income_preference_pct": self.income_preference,
            "allocation_to_income": alloc_to_income,
            "allocation_to_model": alloc_to_model
        })
        
        return {
            "income": alloc_to_income,
            "model": alloc_to_model
        }


def run_portfolio_cycle(
    state: PortfolioState,
    ticker: str,
    start_date: str,
    end_date: str,
    initial_shares: float,
    unwind_cost_basis: float = 100.0,
    income_preference: float = 50.0,
    prices: Dict[str, float] = None,
    available_cash: float = None,
    month: int = 0
) -> Dict[str, Any]:
    """
    TASK 3: Main Orchestrator Entrypoint executing the required Sequential Logic Flow (Task 9).
    TASK 10: Consolidated Output Schema.
    """
    prices = prices or {}
    trades = []
    
    # 1. INITIALIZE GLOBAL ORCHESTRATOR
    orch = PortfolioOrchestrator(state, income_preference)
    
    # GENERATE SIGNALS (with real price history for momentum)
    from ai_advisory.signals.signal_engine import generate_signals
    price_history = prices.get("__cp_history__", None)  # injected by time_simulator when available
    signals = generate_signals(state, prices, price_history=price_history)

    # 2. EVALUATE CONTINUOUS OVERLAYS
    concentration_threshold = 0.15
    tlh_min_threshold       = 1_000.0   # need at least $1k TLH to enable unwind
    option_is_open          = getattr(state, "open_option", None) is not None

    unrealized_loss = getattr(state, "unrealized_loss", 0.0)
    tlh_inventory   = getattr(state, "tlh_inventory", 0.0)
    momentum        = signals.get("momentum_score", 0.0)
    unwind_urgency  = signals.get("unwind_urgency", 0.0)

    enable_covered_call = True

    # TLH: trigger when unrealized losses exceed threshold OR we have existing inventory
    enable_tlh = (unrealized_loss > 0.10) or (tlh_inventory > tlh_min_threshold)

    # Intelligent unwind gate — four conditions must align:
    #   1. Concentration above threshold
    #   2. TLH inventory available (we need offset capacity to sell tax-efficiently)
    #   3. Momentum not strongly bullish (don't force-sell into a rising stock)
    #   4. No open covered call this period (call premium is working; let it run)
    concentrated_enough = state.concentration_pct > concentration_threshold
    has_tlh_capacity    = tlh_inventory >= tlh_min_threshold
    momentum_allows     = momentum < 0.5    # sell unless strongly bullish (>0.5)
    call_not_blocking   = not option_is_open  # don't unwind same period as collecting premium

    enable_unwind = concentrated_enough and has_tlh_capacity and momentum_allows and call_not_blocking

    trace_log(f"[UNWIND DECISION]")
    trace_log(f"concentrated_enough: {concentrated_enough} ({state.concentration_pct*100:.1f}% > {concentration_threshold*100:.0f}%)")
    trace_log(f"has_tlh_capacity: {has_tlh_capacity} (inventory={tlh_inventory:.0f})")
    trace_log(f"momentum_allows: {momentum_allows} (score={momentum:.3f})")
    trace_log(f"call_not_blocking: {call_not_blocking}")
    
    trace_log("[CP OVERLAY STATUS]")
    trace_log(f"covered_call_active: {enable_covered_call}")
    trace_log(f"tlh_triggered: {enable_tlh}")
    trace_log(f"unwind_triggered: {enable_unwind}")
    trace_log(f"unwind_urgency: {unwind_urgency:.3f}")
    
    # Capital release rate mapping — urgency now drives both trigger and share cap
    de_risk_score  = orch.determine_de_risk_score()
    unwind_params  = orch.determine_capital_release_params(de_risk_score, unwind_urgency)
    
    # 2. THE CONCENTRATED POSITION OVERLAYS INVOCATION
    trace_log("--- [MODULE 3] STRATEGY CALL TRACE ---")
    trace_log("-> CALLED: CP Strategy Engine (StrategyUnwindEngine.run_covered_call_overlay)")
    orch._log_decision("INVOKE_CONCENTRATED_ENGINE", {"action": "Start", "initial_shares": initial_shares})
    
    cp_engine = StrategyUnwindEngine(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
        initial_shares=initial_shares
    )
    
    # The CP engine must only work with TLH it generates this step (tlh_delta).
    # Pre-existing tlh_inventory is owned by the simulator/ledger — not the engine.
    # Zeroing it out on the state view enforces the boundary: engine reports what
    # it generated and consumed; the simulator applies that to the running balance.
    import copy
    cp_state_view = copy.copy(state)
    object.__setattr__(cp_state_view, 'tlh_inventory', 0.0)

    res_cp = cp_engine.run_covered_call_overlay(
        enable_covered_call=enable_covered_call,
        enable_tlh=enable_tlh,
        enable_unwind=enable_unwind,
        share_reduction_trigger_pct=unwind_params["share_reduction_trigger_pct"],
        cost_basis=unwind_cost_basis,
        coverage_pct=50.0,
        target_dte_days=30,
        target_delta=0.20,
        profit_capture_pct=0.50,
        max_shares_per_month=unwind_params["max_shares_per_month"],
        starting_cash=state.cash,
        initial_state=cp_state_view  # <-- cp_state_view, not state
    )
    
    cp_summary = res_cp["summary"]
    shares_sold = -cp_summary.get("shares_delta", 0.0)
    updated_shares = state.shares + cp_summary.get("shares_delta", 0.0)
    
    ending_price = cp_summary["ending_price"]
    premium = cp_summary.get("open_option_premium", 0.0)
    option_pnl = cp_summary.get("option_pnl", 0.0)
    
    # 1. APPLY OPTION PREMIUM TO CASH
    # Immediately after StrategyUnwindEngine returns:
    # cash_delta += option_premium (Conceptually handled by taking the true cash_delta from the strategy which already contains it, or explicitly passing it)
    cp_cash_generated = cp_summary.get("cash_delta", 0.0)
    proceeds_from_sales = cp_cash_generated - (premium + option_pnl)
    
    object.__setattr__(state, 'cash', state.cash + premium + option_pnl)
    
    tlh_delta = cp_summary.get("tlh_delta", 0.0)
    tlh_used = cp_summary.get("tlh_used", 0.0)

    
    # Emit Intent: SELL CP SHARES
    if shares_sold > 0:
        trades.append({
            "symbol": ticker,
            "side": "SELL",
            "quantity": shares_sold,
            "price_override": ending_price # Strategy decided execution price
        })

    orch._log_decision("UNWIND_COMPLETE", {
        "shares_sold": shares_sold,
        "cash_released_from_liquidation": proceeds_from_sales
    })
    
    # 3. SPLIT ALLOCATION ROUTING (Task 7)
    # 2. REMOVE DERIVED CAPITAL
    # Use state.cash for all allocation logic
    available_capital = state.cash + proceeds_from_sales
    allocs = orch.determine_allocations(available_capital)
    
    allocation_to_income = allocs['income']
    allocation_to_model = allocs['model']
    requested_total = allocation_to_income + allocation_to_model
    
    # [CAPITAL CONSTRAINT] MODULE 2: CAP ALLOCATION
    # 3. FIX EXECUTION FUNDING - Execution must ONLY use: state.cash
    total_allocatable = available_capital
    scale_factor = 1.0

    if requested_total > total_allocatable and requested_total > 0:
        scale_factor = total_allocatable / requested_total
        allocation_to_income *= scale_factor
        allocation_to_model *= scale_factor
    
    # [CAPITAL CONSTRAINT] MODULE 5: TRACE LOGGING
    trace_log("[CAPITAL CONSTRAINT]")
    trace_log(f"Month: {month}")
    trace_log(f"Requested: {requested_total:.2f}")
    trace_log(f"Available: {total_allocatable:.2f}")
    trace_log(f"Scale Factor: {scale_factor:.4f}")
    
    # Update allocs dictionary with the capped amounts
    allocs['income'] = allocation_to_income
    allocs['model'] = allocation_to_model
    
    # 4. EXECUTE ANCHOR INCOME ALLOCATION (Task 8)
    res_income = None
    delta_income_value = 0.0
    inc_res = None
    income_weights = {}
    if allocs['income'] > 0.01:
        trace_log("-> CALLED: Income Strategy Engine (AnchorIncomeEngine.simulate)")
        orch._log_decision("INVOKE_INCOME_ENGINE", {"capital_injected": allocs['income']})
        inc_engine = AnchorIncomeEngine(
            start_date=start_date,
            end_date=end_date,
            initial_capital=allocs['income'],
            reinvest_pct=100.0 # Standardize re-investment for compounded pipeline growth
        )
        income_weights = inc_engine.parking_lot_target_weights
        
        # Emit Intents: BUY INCOME ETFS
        for t, w in income_weights.items():
            if w > 0.0 and prices.get(t, 0) > 0:
                qty = (allocs['income'] * w) / prices[t]
                trades.append({
                    "symbol": t,
                    "side": "BUY",
                    "quantity": qty
                })
        
        # Synthetic simulation removed. Values purely derived in time_simulator.
        res_income = None
        inc_res = None

    # 5. EXECUTE MODEL PORTFOLIO ALLOCATION (Task 8)
    res_mp = None
    delta_model_value = 0.0
    mp_res = None
    model_weights = {}
    if allocs['model'] > 0.01:
        trace_log("-> CALLED: Model Strategy Engine (frontier portfolio)")
        orch._log_decision("INVOKE_MODEL_PORTFOLIO_ENGINE", {"capital_injected": allocs['model']})

        model_weights = _get_frontier_weights(
            risk_score=int(round(state.risk_score)),
            as_of=start_date[:10],
            model_id="core",
        )
        trace_log(f"-> Frontier weights: {model_weights}")

        # Emit BUY intents for each frontier holding
        for t, w in model_weights.items():
            if w > 0.0 and prices.get(t, 0) > 0:
                qty = (allocs['model'] * w) / prices[t]
                trades.append({
                    "symbol": t,
                    "side": "BUY",
                    "quantity": qty,
                })

        mp_res = None
        res_mp = None

    # 6. STRUCTURAL STATE EVOLUTION
    # Removed direct state mutation. Trades are now emitted as intents for the Execution Layer.

    orch._log_decision("ORCHESTRATION_CYCLE_COMPLETE", {
        "capital_released": proceeds_from_sales
    })

    # Legacy test assumption mapping
    cp_final = cp_summary.get("final_portfolio_value", 0.0)
    legacy_eco_value = cp_final
    
    purchases = allocs['income'] + allocs['model']
    # The true cash delta mapping: we've already permanently modified state.cash with premium and pnl
    # So the remaining delta is just proceeds from sales minus purchases
    cash_delta = proceeds_from_sales - purchases

    orch_summary = {
        "status": "success",
        "cash_delta": cash_delta,
        "capital_released": proceeds_from_sales,
        "allocation_to_income": allocs['income'],
        "allocation_to_model": allocs['model'],
        "income_weights": income_weights,
        "model_weights": model_weights,
        "true_final_ecosystem_value": legacy_eco_value, # Backwards compat
        "tlh_delta": tlh_delta,
        "tlh_used": tlh_used,
        "option_pnl": option_pnl
    }

    nested_reports = {
        "concentrated_position": res_cp,
        "income": inc_res,
        "model_portfolio": mp_res
    }

    return {
        "trades": trades,
        "orch_summary": orch_summary,
        "decision_log": orch.decision_log,
        
        # We pass through the raw nested reports so UI layers can render the details untouched
        "nested_reports": {
            "concentrated_position": res_cp,
            "income": res_income,
            "model_portfolio": res_mp
        },
        "metadata": {
            "concentrated_position": res_cp,
            "income": res_income,
            "model_portfolio": res_mp
        }
    }
