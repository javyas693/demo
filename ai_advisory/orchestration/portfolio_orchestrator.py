from typing import Dict, Any, List
from datetime import datetime
import math

from ai_advisory.portfolio.portfolio_state import PortfolioState
from ai_advisory.strategy.strategy_unwind import StrategyUnwindEngine
from ai_advisory.strategy.anchor_income import AnchorIncomeEngine
from ai_advisory.services.portfolio_analytics import run_mp_backtest
from ai_advisory.orchestration.trace_logger import trace_log

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

    def determine_capital_release_params(self, de_risk_score: float) -> Dict[str, Any]:
        """
        TASK 5: Capital Release Strategy Map
        Maps the de-risk score into operational parameters for the Unwind Engine.
        """
        # Higher de-risk score implies a lower threshold (quicker trigger) to sell shares
        trigger_pct = max(0.05, 0.40 - (de_risk_score / 200.0)) # Maps roughly to 5% - 40% drops
        
        # Max shares to dump per month logically scales with inventory and urgency
        max_shares = 200 if de_risk_score < 40 else 500
        
        params = {
            "strategy_mode": "tax_neutral",
            "enable_tax_loss_harvest": True,
            "share_reduction_trigger_pct": trigger_pct,
            "max_shares_per_month": max_shares
        }
        self._log_decision("MAP_UNWIND_PARAMS", {
            "de_risk_score": round(de_risk_score, 2),
            "mapped_params": params
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
    
    from ai_advisory.portfolio.tlh_budget import TLHBudgetManager
    tlh_manager = TLHBudgetManager(state.tlh_inventory)
    
    # GENERATE SIGNALS
    from ai_advisory.signals.signal_engine import generate_signals
    signals = generate_signals(state, prices)
    
    # 2. EVALUATE CONTINUOUS OVERLAYS
    loss_threshold = 0.10
    concentration_threshold = 0.15
    
    unrealized_loss = getattr(state, 'unrealized_loss', 0.0)
    
    enable_covered_call = True
    enable_tlh = unrealized_loss > loss_threshold
    enable_unwind = state.concentration_pct > concentration_threshold
    
    trace_log("[CP OVERLAY STATUS]")
    trace_log(f"covered_call_active: {enable_covered_call}")
    trace_log(f"tlh_triggered: {enable_tlh}")
    trace_log(f"unwind_triggered: {enable_unwind}")
    
    # Capital release rate mapping
    de_risk_score = orch.determine_de_risk_score()
    unwind_params = orch.determine_capital_release_params(de_risk_score)
    
    # 2. THE CONCENTRATED POSITION OVERLAYS INVOCATION
    trace_log("--- [MODULE 3] STRATEGY CALL TRACE ---")
    trace_log("-> CALLED: CP Strategy Engine (StrategyUnwindEngine.run_covered_call_overlay)")
    orch._log_decision("INVOKE_CONCENTRATED_ENGINE", {"action": "Start", "initial_shares": state.shares})
    
    import pandas as pd
    base_date = pd.to_datetime(start_date)
    current_date = base_date + pd.DateOffset(months=max(0, month - 1))
    calc_start_date = current_date.replace(day=1).strftime('%Y-%m-%d')
    calc_end_date = (current_date + pd.offsets.MonthEnd(0)).strftime('%Y-%m-%d')

    cp_engine = StrategyUnwindEngine(
    ticker=ticker,
    start_date=start_date,
    end_date=end_date,
    initial_shares=state.shares
    )   
    
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
        initial_state=state,
        tlh_manager=tlh_manager
    )
    
    cp_summary = res_cp["summary"]
    strategy_shares_sold = -cp_summary.get("shares_delta", 0.0)
    total_shares_sold = strategy_shares_sold
    updated_shares = state.shares + cp_summary.get("shares_delta", 0.0)
    
    ending_price = cp_summary["ending_price"]
    premium = cp_summary.get("open_option_premium", 0.0)
    option_pnl = cp_summary.get("option_pnl", 0.0)
    
    # 1. APPLY OPTION PREMIUM TO CASH
    # Immediately after StrategyUnwindEngine returns:
    # cash_delta += option_premium (Conceptually handled by taking the true cash_delta from the strategy which already contains it, or explicitly passing it)
    cp_cash_generated = cp_summary.get("cash_delta", 0.0)
    proceeds_from_sales = cp_cash_generated - (premium + option_pnl)
    
    # Check if cash would go negative after option settlement
    projected_cash = state.cash + cp_cash_generated
    if projected_cash < 0:
        # Must sell CP shares to cover deficit
        shares_needed = math.ceil(abs(projected_cash) / ending_price)
        shares_needed = min(shares_needed, int(state.shares))
        deficit_covered = shares_needed * ending_price
        projected_cash += deficit_covered
        # Add forced sale to trades
        if shares_needed > 0:
            trades.append({
                "symbol": ticker,
                "side": "SELL",
                "quantity": shares_needed,
                "price_override": ending_price
            })
            total_shares_sold += shares_needed
            proceeds_from_sales += deficit_covered

    object.__setattr__(state, 'cash', state.cash + premium + option_pnl)
    
    tlh_delta = cp_summary.get("tlh_delta", 0.0)
    tlh_used = cp_summary.get("tlh_used", 0.0)

    
    # Emit Intent: SELL CP SHARES
    if strategy_shares_sold > 0:
        trades.append({
            "symbol": ticker,
            "side": "SELL",
            "quantity": strategy_shares_sold,
            "price_override": ending_price # Strategy decided execution price
        })

    orch._log_decision("UNWIND_COMPLETE", {
        "shares_sold": total_shares_sold,
        "cash_released_from_liquidation": proceeds_from_sales
    })
    
    # 3. SPLIT ALLOCATION ROUTING (Task 7)
    # 2. REMOVE DERIVED CAPITAL
    # Only deploy newly generated capital, preserve existing cash buffer
    new_capital_this_cycle = premium + option_pnl + proceeds_from_sales
    available_capital = max(0.0, new_capital_this_cycle)
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
        # Determine weighting logic via risk_score (B1 3-Band Option)
        from ai_advisory.portfolio.model_portfolio_repo import default_model_portfolio_repo
        repo = default_model_portfolio_repo()
        
        # 3 Bands: conservative (0-33), balanced (34-66), aggressive (67-100)
        risk = int(state.risk_score)
        if risk <= 33:
            model_name = "conservative"
        elif risk <= 66:
            model_name = "core_balanced"
        else:
            model_name = "aggressive"
            
        mp = repo.get(model_name)
        model_weights = mp.weights
        trace_log(f"-> Selected {model_name} from repo for risk {risk}: {model_weights}")
        
        # Emit Intents: BUY MODEL ETFS
        for t, w in model_weights.items():
            if w > 0.0 and prices.get(t, 0) > 0:
                qty = (allocs['model'] * w) / prices[t]
                trades.append({
                    "symbol": t,
                    "side": "BUY",
                    "quantity": qty
                })
                
        # Synthetic backtest logic removed. Values purely derived down stream.
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
        "tlh_remaining": tlh_manager.get_remaining(),
        "tlh_summary": tlh_manager.get_summary(),
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
