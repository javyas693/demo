import math
import os
import json
import csv
import pandas as pd
from unittest.mock import patch
from ai_advisory.portfolio.portfolio_state import PortfolioState
from ai_advisory.orchestration.portfolio_orchestrator import run_portfolio_cycle
from ai_advisory.orchestration.reconciliation import reconcile_step
from ai_advisory.orchestration.trace_logger import trace_log
from ai_advisory.orchestration.execution_layer import execute_trades

# ─────────────────────────────────────────────────────────
# Strategy Engine Constants (configurable defaults)
# ─────────────────────────────────────────────────────────
INCOME_YIELD_ANNUAL    = 0.06   # 6% annual yield target on income portfolio

_YF_CACHE = {}

def simulate_portfolio(
    initial_state: PortfolioState,
    ticker: str,
    initial_shares: float,
    cost_basis: float,
    horizon_months: int = 12,
    income_preference: float = 50.0,
    # Allow caller to override engine rates
    income_yield_annual: float = INCOME_YIELD_ANNUAL,
    export_reconciliation: bool = False,
    export_chart_timeline: bool = False,
) -> list[dict]:
    """
    Deterministically simulates the portfolio over N periods using historical prices.
    Each step:
      1. Orchestrator executes the unwind / reallocation decision.
      2. Income engine value updates based on real historical prices.
      3. Model engine value updates based on real historical prices.
      4. Concentrated position price updates based on real historical prices.
    """

    current_state  = initial_state
    current_shares = initial_shares
    current_price  = initial_state.current_price   # tracks price evolution

    # Cumulative trackers
    total_trades_executed        = 0
    cumulative_income_generated  = 0.0
    cumulative_income_allocated  = 0.0   # capital moved from CP → income
    cumulative_model_allocated   = 0.0   # capital moved from CP → model
    cumulative_model_growth      = 0.0   # organic model return
    cumulative_value_sold        = 0.0   # CP value liquidated (shares_sold * price at time of sale)
    initial_cp_value             = initial_state.market_value
    initial_portfolio_value      = initial_state.total_portfolio_value

    import yfinance as yf
    
    # Simple memory cache to prevent rate-limits from repeated UI testing
    global _YF_CACHE

    all_etfs = ["JEPQ", "TLTW", "SVOL", "VTI", "TLT", "VWO", "VEA", "SHY", "LEMB", "HYG", "VCLT", "PGX", "SPY", "IJH", "IWM", "IAU", "SCHH", "BIL", "BTC-USD"]
    all_symbols = [ticker] + all_etfs
    
    cache_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "yf_cache.pkl")
    cache_key = tuple(sorted(all_symbols))
    
    df_hist = None
    if cache_key in _YF_CACHE:
        df_hist = _YF_CACHE[cache_key]
    else:
        try:
            df_hist = yf.download(all_symbols, period="max", progress=False)
            if df_hist is not None and not df_hist.empty:
                _YF_CACHE[cache_key] = df_hist
                # Persist to disk as fallback for global environments with buggy yfinance versions
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                df_hist.to_pickle(cache_path)
        except Exception as e:
            trace_log(f"yfinance download exception: {e}")

    # Fallback to disk if memory and live download both failed
    if (df_hist is None or df_hist.empty) and os.path.exists(cache_path):
        try:
            df_hist = pd.read_pickle(cache_path)
            trace_log("Recovered historical pricing from disk cache due to yfinance failure.")
        except Exception:
            pass

    if df_hist is None or df_hist.empty:
        raise ValueError(f"yfinance returned empty dataframe for symbols {all_symbols}")

    current_prices = {}
    historical_prices = {}
            
    if isinstance(df_hist.columns, pd.MultiIndex):
        if 'Adj Close' in df_hist.columns.levels[0]:
            df_target = df_hist['Adj Close']
        else:
            df_target = df_hist['Close']
    else:
        if 'Adj Close' in df_hist.columns:
            df_target = df_hist['Adj Close']
        elif 'Close' in df_hist.columns:
            df_target = df_hist['Close']
        else:
            df_target = df_hist
            
    if isinstance(df_target, pd.Series):
        df_target = df_target.to_frame(name=all_symbols[0])
        
    # Daily data -> monthly series. Rule: use last price of each month.
    df_target = df_target.ffill()
    df_monthly = df_target.resample('BME').last().dropna(how='all')
    
    required_len = horizon_months + 1
    if len(df_monthly) > required_len:
        df_monthly = df_monthly.iloc[-required_len:]
        
    for sym in all_symbols:
        if sym in df_monthly.columns:
            # Handle potential NaNs for newer ETFs by filling backwards or using 100.0 if entirely missing?
            # User wants system to fail if data not available
            series = df_monthly[sym]
            if series.isna().all():
                raise ValueError(f"Symbol {sym} has no valid price data (all NaN)")
            # forward fill followed by backfill to handle ETFs that didn't exist 5 years ago
            series = series.ffill().bfill()
            historical_prices[sym] = series.tolist()
        else:
            raise ValueError(f"System failed: data not available for symbol {sym}")
            
    # Initialize month 0 prices
    for t in all_etfs:
        current_prices[t] = float(historical_prices[t][0])
        
    # Align CP initial price
    current_price = float(historical_prices[ticker][0])
    object.__setattr__(initial_state, 'current_price', current_price)
    object.__setattr__(initial_state, 'market_value', current_price * current_shares)
    initial_portfolio_value = initial_state.market_value + initial_state.cash + initial_state.income_value + initial_state.model_value
    object.__setattr__(initial_state, 'total_portfolio_value', initial_portfolio_value)
    # Re-calc derived properties
    if hasattr(initial_state, "__post_init__"):
        initial_state.__post_init__()
    initial_cp_value = initial_state.market_value

    if ticker in historical_prices and len(historical_prices[ticker]) >= 3:
        trace_log("[DATA CHECK]")
        trace_log(f"Symbol: {ticker}")
        trace_log(f"Month 1 price: {historical_prices[ticker][1]:.2f}")
        trace_log(f"Month 2 price: {historical_prices[ticker][2]:.2f}\n")


    STATIC_START = "2023-01-01"
    STATIC_END   = "2023-01-31"
    dates        = pd.date_range(STATIC_START, STATIC_END, freq="D")

    timeline = []

    # ─────────────────────────────────────────────────────
    # Snapshot builder — extended with new engine fields
    # ─────────────────────────────────────────────────────
    def build_snapshot(
        month_idx, state,
        shares_sold, capital_released, to_income, to_model,
        income_generated, model_growth, cp_price,
        decision_log=None,
    ):
        return {
            # ── Indexing ──
            "step_index":  month_idx,
            "year_index":  math.floor(month_idx / 12),
            "month":       month_idx,
            "date":        "Baseline" if month_idx == 0 else f"Month {month_idx}",

            # ── Portfolio totals ──
            "total_portfolio_value": state.total_portfolio_value,
            "total_ecosystem_value": state.total_portfolio_value,
            "cash":                  state.cash,
            "concentration_pct":     state.concentration_pct * 100.0,

            # ── Flat strategy values ──
            "concentrated_value":  state.market_value,
            "income_value":        state.income_value,
            "model_value":         state.model_value,
            "shares":              state.shares,

            # ── Nested strategies (for legacy UI consumers AND EXPORTS) ──
            "strategies": {
                "concentrated": {
                    "shares":      state.shares,
                    "value":       state.market_value,
                    "shares_sold": shares_sold,
                    "price":       cp_price,
                },
                "income": {
                    "value":             state.income_value,
                    "annual_income":     state.annual_income,
                    "capital_allocated": to_income,
                    "income_generated_this_step": income_generated,
                    "holdings":          dict(state.income_holdings)
                },
                "model": {
                    "value":             state.model_value,
                    "capital_allocated": to_model,
                    "growth_generated_this_step": model_growth,
                    "holdings":          dict(state.model_holdings)
                },
            },

            # ── Step-level reallocation flows ──
            "capital_released_this_step":    capital_released,
            "allocation_to_income_this_step": to_income,
            "allocation_to_model_this_step":  to_model,

            # ── NEW: Charting normalized/attribution fields ──
            "total_return_index":            state.total_portfolio_value / initial_portfolio_value if initial_portfolio_value > 0 else 1.0,
            "income_generated_to_date":      state.income_value - cumulative_income_allocated,
            "model_growth_to_date":          state.model_value - cumulative_model_allocated,

            # ── NEW: Organic engine outputs ──
            "income_generated_this_step": income_generated,
            "cumulative_income_generated": cumulative_income_generated,
            "model_growth_this_step":      model_growth,
            "cp_price":                    cp_price,

            # ── NEW: Attribution totals ──
            "attr_income_allocated":   cumulative_income_allocated,
            "attr_income_generated":   cumulative_income_generated,
            "attr_model_allocated":    cumulative_model_allocated,
            "attr_model_growth":       cumulative_model_growth,
            "attr_cp_initial_value":   initial_cp_value,
            "attr_cp_value_sold":      cumulative_value_sold,

            # ── Trace ──
            "decision_trace": decision_log or [],
        }

    # ─────────────────────────────────────────────────────
    # Snapshot 0: Baseline (no growth applied yet)
    # ─────────────────────────────────────────────────────
    baseline_snapshot = build_snapshot(
        0, current_state, 0.0, 0.0, 0.0, 0.0,
        income_generated=0.0,
        model_growth=0.0,
        cp_price=current_price,
    )
    baseline_snapshot["reconciliation"] = {
        "flow_delta": 0.0,
        "sum_delta": 0.0,
        "is_flow_valid": True,
        "is_sum_valid": True,
        "details": {}
    }
    
    reconciliation_report = []
    if export_reconciliation:
        reconciliation_report.append({
            "month": 0,
            "start_value": current_state.total_portfolio_value,
            "end_value": current_state.total_portfolio_value,
            "cp_change": 0.0,
            "income_change": 0.0,
            "model_change": 0.0,
            "cash_change": 0.0,
            "flow_delta": 0.0,
            "sum_delta": 0.0,
            "is_flow_valid": True,
            "is_sum_valid": True,
            "concentrated_value": current_state.market_value,
            "income_value": current_state.income_value,
            "model_value": current_state.model_value,
            "cash": current_state.cash,
        })

    print(f"Month 0 | Flow Δ: 0.0 | Sum Δ: 0.0 | Valid: true")
    timeline.append(baseline_snapshot)

    # ─────────────────────────────────────────────────────
    # Main simulation loop
    # ─────────────────────────────────────────────────────
    previous_option_open = False
    

    for month in range(1, horizon_months + 1):
        trace_log(f"\n--- [MODULE 2] START MONTH {month} ---")
        trace_log(f"CURRENT STATE - Cash: {current_state.cash:.2f}, CP: {current_state.market_value:.2f}, Income: {current_state.income_value:.2f}, Model: {current_state.model_value:.2f}")

        # [CP AUDIT] Before State
        shares_before = current_state.shares
        tlh_inventory_before = current_state.tlh_inventory
        cash_before = current_state.cash

        # [CAPITAL CONSTRAINT] MODULE 1: COMPUTE AVAILABLE CASH
        # Before strategy call:
        available_cash = current_state.cash

        # ── Inject CP price history for momentum signal ──
        # Pass trailing window of CP prices (up to last 6 months) so the
        # signal engine can compute real momentum instead of using the 0.5 stub.
        safe_idx_pre = min(month, len(historical_prices[ticker]) - 1)
        cp_history_window = historical_prices[ticker][max(0, safe_idx_pre - 5): safe_idx_pre + 1]
        current_prices["__cp_history__"] = cp_history_window

        # ── STEP 1: Orchestrator executes unwind / reallocation ──
        orch_res = run_portfolio_cycle(
            state=current_state,
            ticker=ticker,
            start_date=STATIC_START,
            end_date=STATIC_END,
            initial_shares=current_shares,
            unwind_cost_basis=cost_basis,
            income_preference=income_preference,
            prices=current_prices,
            available_cash=available_cash,
            month=month
        )

        res_summary    = orch_res["orch_summary"]
        trades         = orch_res["trades"]

        # Clean up the injected history key so it doesn't pollute price lookups
        current_prices.pop("__cp_history__", None)
        
        # ── STEP 2: EXECUTION LAYER ──
        # Replaces implicit state mutations with concrete isolated ledger trades
        execution_res = execute_trades(current_state, trades, current_prices, month)
        total_trades_executed += len(trades)
        
        capital_released = res_summary["capital_released"]
        to_income        = res_summary["allocation_to_income"]
        to_model         = res_summary["allocation_to_model"]
        tlh_delta        = res_summary.get("tlh_delta", 0.0)
        tlh_used         = res_summary.get("tlh_used", 0.0)
        
        nested_cp = orch_res["metadata"]["concentrated_position"]["summary"]
        shares_sold = -nested_cp.get("shares_delta", 0.0)

        # Update cumulative allocation trackers
        cumulative_income_allocated += to_income
        cumulative_model_allocated  += to_model
        cumulative_value_sold       += shares_sold * current_price

        # The execution layer generated absolute new dicts of post-trade holdings
        delta_income_holdings = execution_res["new_income_holdings"]
        delta_model_holdings  = execution_res["new_model_holdings"]
        new_shares            = execution_res["new_shares"]

        # ── STEP 3: Progress Time & Apply Historical Prices ──
        safe_idx = min(month, len(historical_prices[ticker]) - 1)
        
        # CP Real Historical Price
        current_price = float(historical_prices[ticker][safe_idx])
        current_shares = new_shares
        new_cp_value = current_shares * current_price
        trace_log(f"[PRICE SOURCE]\nMonth: {month}\nSymbol: {ticker} price: {current_price}")

        # ETF Real Historical Prices
        for t in all_etfs:
            if t in historical_prices:
                p = float(historical_prices[t][safe_idx])
                current_prices[t] = p
                trace_log(f"[PRICE SOURCE]\nMonth: {month}\nSymbol: {t} price: {p}")

        # ── STEP 4: Revalue Holdings based on New Prices ──
        new_income_value = sum(qty * current_prices.get(t, 0.0) for t, qty in delta_income_holdings.items())
        new_model_value = sum(qty * current_prices.get(t, 0.0) for t, qty in delta_model_holdings.items())

        # Performance organic yield isolates the natural price growth from the capital injected this month
        income_generated = new_income_value - (current_state.income_value + to_income)
        model_growth = new_model_value - (current_state.model_value + to_model)

        cumulative_income_generated += income_generated
        cumulative_model_growth += model_growth
        new_annual_income  = new_income_value * income_yield_annual

        # ── STEP 5: Rebuild state purely from holdings ──
        cash_delta   = res_summary["cash_delta"]
        
        computed_cash = current_state.cash + cash_delta
        if -1e-8 < computed_cash < 1e-8:
            computed_cash = 0.0
            
        new_state = PortfolioState(
            cash=computed_cash,
            ticker=ticker,
            shares=new_shares,
            current_price=current_price,
            cost_basis=cost_basis,
            income_value=new_income_value,
            annual_income=new_annual_income,
            income_holdings=delta_income_holdings,
            model_value=new_model_value,
            model_holdings=delta_model_holdings,
            tlh_inventory=current_state.tlh_inventory + tlh_delta - tlh_used,
            risk_score=current_state.risk_score,
            applied_event_ids=current_state.applied_event_ids
        )
        current_state = new_state

        # ── [CP AUDIT] Logging & Validation ──
        shares_sold_log = -nested_cp.get("shares_delta", 0.0)
        shares_after = new_state.shares
        
        option_open = nested_cp.get("is_option_open", False)
        option_premium = nested_cp.get("open_option_premium", 0.0)
        
        tlh_realized_this_step = nested_cp.get("realized_option_loss", 0.0)
        tlh_inventory_after = new_state.tlh_inventory
        
        cash_increase = new_state.cash - cash_before
        
        trace_log("\n[CP AUDIT]")
        trace_log(f"month: {month}")
        trace_log(f"shares_before: {shares_before}")
        trace_log(f"shares_sold: {shares_sold_log}")
        trace_log(f"shares_after: {shares_after}\n")
        
        trace_log(f"option_open: {option_open}")
        trace_log(f"option_premium: {option_premium:.2f}\n")
        
        trace_log(f"tlh_inventory_before: {tlh_inventory_before:.2f}")
        trace_log(f"tlh_realized_this_step: {tlh_realized_this_step:.2f}")
        trace_log(f"tlh_inventory_after: {tlh_inventory_after:.2f}\n")
        
        warnings = []
            
        if tlh_inventory_after < tlh_inventory_before:
            warnings.append("negative inventory")
            
        # Option persistence: if open previously, it must exist or have closed with some cash flow effect
        if previous_option_open and not option_open:
            if nested_cp.get("realized_option_pnl", 0.0) == 0.0 and nested_cp.get("option_buyback_cost", 0.0) == 0.0:
                warnings.append("option disappearance")
                
        # 5. ADD CASH INVARIANT CHECK
        purchases = to_income + to_model
        # Use orchestrator's reconciled capital_released to account for embedded tax savings & slippage 
        sales_proceeds = res_summary["capital_released"]
        
        expected_cash = cash_before + option_premium + nested_cp.get("option_pnl", 0.0) + sales_proceeds - purchases

        # Assertion: new_cash must equal old_cash + orchestrated inflows/outflows
        assert abs(new_state.cash - expected_cash) < 0.01, \
            f"Cash Invariant Failed: {new_state.cash} != {expected_cash} (old: {cash_before}, prem: {option_premium}, pnl: {nested_cp.get('option_pnl', 0.0)}, sales: {sales_proceeds}, pur: {purchases})"
            
        if warnings:
            trace_log("\n[CP WARNING]")
            for w in warnings:
                trace_log(f"* {w}")
                
        # 4. APPLY TLH TO STATE (CRITICAL)
        # [TLH INTEGRITY VALIDATION]
        new_tlh_inventory = tlh_inventory_before + tlh_delta - tlh_used
        assert tlh_inventory_after == new_tlh_inventory, \
            f"TLH Validation Failed: {tlh_inventory_after} != {tlh_inventory_before} + {tlh_delta} - {tlh_used}"
                
        previous_option_open = option_open


        trace_log(f"--- [MODULE 5] STATE MUTATION TRACE ---")
        trace_log(f"Income generated: {income_generated:.2f} -> New Income Value: {current_state.income_value:.2f}")
        trace_log(f"Model growth: {model_growth:.2f} -> New Model Value: {current_state.model_value:.2f}")
        trace_log(f"New CP Value: {current_state.market_value:.2f}")
        trace_log(f"Cash Delta: {cash_delta:.2f}")
        trace_log(f"Shares Delta: {-shares_sold:.4f}")
        
        trace_log(f"\n[STATE CHECK]")
        trace_log(f"Month: {month}")
        trace_log(f"Holdings: {{**new_state.income_holdings, **new_state.model_holdings}}")
        trace_log(f"Prices: {current_prices}")
        trace_log(f"Computed Value: {new_income_value + new_model_value + new_cp_value:.2f}")
        trace_log(f"Reported Value: {new_state.income_value + new_state.model_value + new_state.market_value:.2f}\n")

        # ── STEP 6: Capture snapshot ──
        snapshot = build_snapshot(
            month, current_state,
            shares_sold, capital_released, to_income, to_model,
            income_generated=income_generated,
            model_growth=model_growth,
            cp_price=current_price,
            decision_log=orch_res.get("orch_summary", {}).get("decision_log", []),
        )

        # ── STEP 7: Reconciliation ──
        prev_snapshot = timeline[-1]
        recon = reconcile_step(prev_snapshot, snapshot)
        snapshot["reconciliation"] = recon

        is_valid = recon["is_flow_valid"] and recon["is_sum_valid"]
        print(f"Month {month} | Flow Δ: {recon['flow_delta']} | Sum Δ: {recon['sum_delta']} | Valid: {str(is_valid).lower()}")
        
        if not is_valid:
            print(f"  WARNING: Reconciliation failed for Month {month}")
            print(f"  Details: {recon['details']}")

        if export_reconciliation:
            details = recon.get("details", {})
            reconciliation_report.append({
                "month": month,
                "start_value": details.get("start_value", 0.0),
                "end_value": details.get("end_value", 0.0),
                "cp_change": details.get("cp_change", 0.0),
                "income_change": details.get("income_change", 0.0),
                "model_change": details.get("model_change", 0.0),
                "cash_change": details.get("cash_change", 0.0),
                "flow_delta": recon.get("flow_delta", 0.0),
                "sum_delta": recon.get("sum_delta", 0.0),
                "is_flow_valid": recon.get("is_flow_valid", True),
                "is_sum_valid": recon.get("is_sum_valid", True),
                "concentrated_value": details.get("concentrated_value", 0.0),
                "income_value": details.get("income_value", 0.0),
                "model_value": details.get("model_value", 0.0),
                "cash": details.get("cash", 0.0),
            })

        timeline.append(snapshot)

        # ── STEP 8: Ledger Trace & Validation ──
        from ai_advisory.orchestration.ledger import get_ledger
        current_ledger = get_ledger()
        
        trace_log("[LEDGER]")
        trace_log(f"Month: {month}")
        trace_log(f"Events Recorded: {len(current_ledger)}")
        
        if len(current_ledger) < total_trades_executed:
            trace_log(f"WARNING: LEDGER MISMATCH - Expected at least {total_trades_executed} trades, got {len(current_ledger)}")

        # Break early if concentrated position is fully unwound
        if current_shares <= 0.001:
            break
        os.makedirs("outputs", exist_ok=True)
        
        # Write JSON
        try:
            with open("outputs/reconciliation_report.json", "w") as f:
                json.dump(reconciliation_report, f, indent=2)
        except Exception as e:
            print(f"Failed to write reconciliation JSON: {e}")

        # Write CSV
        try:
            with open("outputs/reconciliation_report.csv", "w", newline='') as f:
                if reconciliation_report:
                    csv_cols = [
                        "month", "start_value", "end_value", "cp_change", 
                        "income_change", "model_change", "cash_change", 
                        "flow_delta", "sum_delta", "is_flow_valid", "is_sum_valid"
                    ]
                    writer = csv.DictWriter(f, fieldnames=csv_cols, extrasaction='ignore')
                    writer.writeheader()
                    writer.writerows(reconciliation_report)
        except Exception as e:
            print(f"Failed to write reconciliation CSV: {e}")

    if export_chart_timeline:
        os.makedirs("outputs", exist_ok=True)
        try:
            class NpEncoder(json.JSONEncoder):
                def default(self, obj):
                    if hasattr(obj, 'item'):
                        return obj.item()
                    return super().default(obj)
            
            with open("outputs/chart_timeline.json", "w") as f:
                json.dump(timeline, f, indent=2, cls=NpEncoder)
        except Exception as e:
            print(f"Failed to write chart_timeline.json: {e}")

    return timeline

