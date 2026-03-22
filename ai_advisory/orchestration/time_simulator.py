import math
import os
import json
import csv
import pandas as pd
from ai_advisory.portfolio.portfolio_state import PortfolioState
from ai_advisory.orchestration.portfolio_orchestrator import run_portfolio_cycle
from ai_advisory.orchestration.reconciliation import reconcile_step
from ai_advisory.orchestration.trace_logger import trace_log
from ai_advisory.orchestration.execution_layer import execute_trades

# ─────────────────────────────────────────────────────────
# Strategy Engine Constants
# ─────────────────────────────────────────────────────────
INCOME_YIELD_ANNUAL = 0.06   # 6% annual yield target on income portfolio

_YF_CACHE = {}


def simulate_portfolio(
    initial_state: PortfolioState,
    ticker: str,
    initial_shares: float,
    cost_basis: float,
    horizon_months: int = 12,
    income_preference: float = 50.0,
    income_yield_annual: float = INCOME_YIELD_ANNUAL,
    export_reconciliation: bool = False,
    export_chart_timeline: bool = False,
) -> list[dict]:
    """
    Deterministically simulates the portfolio over N periods using historical prices.

    Each step:
      1. Orchestrator executes unwind / reallocation decision via DecisionService.
      2. Income engine value updates based on real historical prices.
      3. Model engine value updates based on real historical prices.
      4. Concentrated position price updates based on real historical prices.

    Key changes from prior version:
      - tlh_delta read from res_summary["tlh_delta_this_step"] (renamed)
      - tlh_used removed — DecisionService owns TLH consumption; simulator
        only adds tlh_delta_this_step to the running tlh_inventory balance
      - shares_sold read from res_summary["shares_to_sell"] (DecisionResult)
        not from nested_cp["shares_delta"] (CP engine no longer owns sell decisions)
      - cash invariant updated to match new orch_summary key names
      - TLH invariant simplified: inventory_after == inventory_before + tlh_delta_this_step
      - open_option carried forward on PortfolioState for OptionsLedger restoration
      - client_constraint carried on PortfolioState (new field, default SELL_OPTIONAL)
    """

    current_state  = initial_state
    current_shares = initial_shares
    current_price  = initial_state.current_price

    # Cumulative trackers
    total_trades_executed       = 0
    cumulative_income_generated = 0.0
    cumulative_income_allocated = 0.0
    cumulative_model_allocated  = 0.0
    cumulative_model_growth     = 0.0
    cumulative_value_sold       = 0.0
    initial_cp_value            = initial_state.market_value
    initial_portfolio_value     = initial_state.total_portfolio_value

    import yfinance as yf
    global _YF_CACHE

    all_etfs = [
        "JEPQ", "TLTW", "SVOL", "VTI", "TLT", "VWO", "VEA",
        "SHY", "LEMB", "HYG", "VCLT", "PGX", "SPY", "IJH",
        "IWM", "IAU", "SCHH", "BIL", "BTC-USD",
    ]
    all_symbols  = [ticker] + all_etfs
    cache_path   = os.path.join(os.path.dirname(__file__), "..", "..", "data", "yf_cache.pkl")
    cache_key    = tuple(sorted(all_symbols))

    df_hist = None
    if cache_key in _YF_CACHE:
        df_hist = _YF_CACHE[cache_key]
    else:
        try:
            df_hist = yf.download(all_symbols, period="max", progress=False)
            if df_hist is not None and not df_hist.empty:
                _YF_CACHE[cache_key] = df_hist
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                df_hist.to_pickle(cache_path)
        except Exception as e:
            trace_log(f"yfinance download exception: {e}")

    if (df_hist is None or df_hist.empty) and os.path.exists(cache_path):
        try:
            df_hist = pd.read_pickle(cache_path)
            trace_log("Recovered historical pricing from disk cache due to yfinance failure.")
        except Exception:
            pass

    if df_hist is None or df_hist.empty:
        raise ValueError(f"yfinance returned empty dataframe for symbols {all_symbols}")

    # Price extraction
    if isinstance(df_hist.columns, pd.MultiIndex):
        df_target = df_hist['Adj Close'] if 'Adj Close' in df_hist.columns.levels[0] else df_hist['Close']
    else:
        if 'Adj Close' in df_hist.columns:
            df_target = df_hist['Adj Close']
        elif 'Close' in df_hist.columns:
            df_target = df_hist['Close']
        else:
            df_target = df_hist

    if isinstance(df_target, pd.Series):
        df_target = df_target.to_frame(name=all_symbols[0])

    df_target  = df_target.ffill()
    df_monthly = df_target.resample('BME').last().dropna(how='all')

    required_len = horizon_months + 1
    if len(df_monthly) > required_len:
        df_monthly = df_monthly.iloc[-required_len:]

    historical_prices: dict = {}
    for sym in all_symbols:
        if sym in df_monthly.columns:
            series = df_monthly[sym]
            if series.isna().all():
                raise ValueError(f"Symbol {sym} has no valid price data (all NaN)")
            historical_prices[sym] = series.ffill().bfill().tolist()
        else:
            raise ValueError(f"System failed: data not available for symbol {sym}")

    current_prices: dict = {}
    for t in all_etfs:
        current_prices[t] = float(historical_prices[t][0])

    # Align CP initial price
    current_price = float(historical_prices[ticker][0])
    object.__setattr__(initial_state, 'current_price', current_price)
    object.__setattr__(initial_state, 'market_value', current_price * current_shares)
    initial_portfolio_value = (
        initial_state.market_value + initial_state.cash
        + initial_state.income_value + initial_state.model_value
    )
    object.__setattr__(initial_state, 'total_portfolio_value', initial_portfolio_value)
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

    timeline: list[dict] = []

    # ------------------------------------------------------------------
    # Snapshot builder
    # ------------------------------------------------------------------
    def build_snapshot(
        month_idx, state,
        shares_sold, capital_released, to_income, to_model,
        income_generated, model_growth, cp_price,
        decision_log=None,
    ):
        return {
            "step_index":  month_idx,
            "year_index":  math.floor(month_idx / 12),
            "month":       month_idx,
            "date":        "Baseline" if month_idx == 0 else f"Month {month_idx}",

            "total_portfolio_value": state.total_portfolio_value,
            "total_ecosystem_value": state.total_portfolio_value,
            "cash":                  state.cash,
            "concentration_pct":     state.concentration_pct * 100.0,

            "concentrated_value":    state.market_value,
            "income_value":          state.income_value,
            "model_value":           state.model_value,
            "shares":                state.shares,

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
                    "holdings":          dict(state.income_holdings),
                },
                "model": {
                    "value":             state.model_value,
                    "capital_allocated": to_model,
                    "growth_generated_this_step": model_growth,
                    "holdings":          dict(state.model_holdings),
                },
            },

            "capital_released_this_step":     capital_released,
            "allocation_to_income_this_step": to_income,
            "allocation_to_model_this_step":  to_model,

            "total_return_index":      state.total_portfolio_value / initial_portfolio_value if initial_portfolio_value > 0 else 1.0,
            "income_generated_to_date": state.income_value - cumulative_income_allocated,
            "model_growth_to_date":     state.model_value - cumulative_model_allocated,

            "income_generated_this_step": income_generated,
            "cumulative_income_generated": cumulative_income_generated,
            "model_growth_this_step":     model_growth,
            "cp_price":                   cp_price,

            "attr_income_allocated":  cumulative_income_allocated,
            "attr_income_generated":  cumulative_income_generated,
            "attr_model_allocated":   cumulative_model_allocated,
            "attr_model_growth":      cumulative_model_growth,
            "attr_cp_initial_value":  initial_cp_value,
            "attr_cp_value_sold":     cumulative_value_sold,

            "decision_trace": decision_log or [],
        }

    # ------------------------------------------------------------------
    # Snapshot 0: Baseline
    # ------------------------------------------------------------------
    baseline_snapshot = build_snapshot(
        0, current_state, 0.0, 0.0, 0.0, 0.0,
        income_generated=0.0, model_growth=0.0, cp_price=current_price,
    )
    baseline_snapshot["reconciliation"] = {
        "flow_delta": 0.0, "sum_delta": 0.0,
        "is_flow_valid": True, "is_sum_valid": True, "details": {},
    }

    reconciliation_report = []
    if export_reconciliation:
        reconciliation_report.append({
            "month": 0,
            "start_value": current_state.total_portfolio_value,
            "end_value":   current_state.total_portfolio_value,
            "cp_change": 0.0, "income_change": 0.0, "model_change": 0.0, "cash_change": 0.0,
            "flow_delta": 0.0, "sum_delta": 0.0,
            "is_flow_valid": True, "is_sum_valid": True,
            "concentrated_value": current_state.market_value,
            "income_value": current_state.income_value,
            "model_value": current_state.model_value,
            "cash": current_state.cash,
        })

    print(f"Month 0 | Flow Δ: 0.0 | Sum Δ: 0.0 | Valid: true")
    timeline.append(baseline_snapshot)

    previous_option_open = False

    # ------------------------------------------------------------------
    # Main simulation loop
    # ------------------------------------------------------------------
    for month in range(1, horizon_months + 1):
        trace_log(f"\n--- [MODULE 2] START MONTH {month} ---")
        trace_log(
            f"CURRENT STATE - Cash: {current_state.cash:.2f}, "
            f"CP: {current_state.market_value:.2f}, "
            f"Income: {current_state.income_value:.2f}, "
            f"Model: {current_state.model_value:.2f}"
        )

        shares_before        = current_state.shares
        tlh_inventory_before = current_state.tlh_inventory
        cash_before          = current_state.cash
        available_cash       = current_state.cash

        # Inject CP price history for momentum signal
        safe_idx_pre      = min(month, len(historical_prices[ticker]) - 1)
        cp_history_window = historical_prices[ticker][max(0, safe_idx_pre - 5): safe_idx_pre + 1]
        current_prices["__cp_history__"] = cp_history_window

        # ── STEP 1: Orchestrator ──────────────────────────────────────
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
            month=month,
        )

        res_summary = orch_res["orch_summary"]
        trades      = orch_res["trades"]
        current_prices.pop("__cp_history__", None)

        # ── STEP 2: Execution layer ───────────────────────────────────
        execution_res   = execute_trades(current_state, trades, current_prices, month)
        total_trades_executed += len(trades)

        capital_released = res_summary["capital_released"]
        to_income        = res_summary["allocation_to_income"]
        to_model         = res_summary["allocation_to_model"]

        # TLH: orchestrator reports what was generated this step only.
        # DecisionService owns TLH consumption; simulator adds delta to inventory.
        tlh_delta_this_step = res_summary.get("tlh_delta_this_step", 0.0)

        # Shares sold: comes from DecisionResult via orch_summary, not CP engine
        shares_sold = res_summary.get("shares_to_sell", 0)

        cumulative_income_allocated += to_income
        cumulative_model_allocated  += to_model
        cumulative_value_sold       += shares_sold * current_price

        delta_income_holdings = execution_res["new_income_holdings"]
        delta_model_holdings  = execution_res["new_model_holdings"]
        new_shares            = execution_res["new_shares"]

        # ── STEP 3: Advance time & apply historical prices ────────────
        safe_idx      = min(month, len(historical_prices[ticker]) - 1)
        current_price = float(historical_prices[ticker][safe_idx])
        current_shares = new_shares
        new_cp_value  = current_shares * current_price
        trace_log(f"[PRICE SOURCE]\nMonth: {month}\nSymbol: {ticker} price: {current_price}")

        for t in all_etfs:
            if t in historical_prices:
                p = float(historical_prices[t][safe_idx])
                current_prices[t] = p
                trace_log(f"[PRICE SOURCE]\nMonth: {month}\nSymbol: {t} price: {p}")

        # ── STEP 4: Revalue holdings ──────────────────────────────────
        new_income_value = sum(
            qty * current_prices.get(t, 0.0) for t, qty in delta_income_holdings.items()
        )
        new_model_value = sum(
            qty * current_prices.get(t, 0.0) for t, qty in delta_model_holdings.items()
        )

        income_generated = new_income_value - (current_state.income_value + to_income)
        model_growth     = new_model_value  - (current_state.model_value  + to_model)

        cumulative_income_generated += income_generated
        cumulative_model_growth     += model_growth
        new_annual_income = new_income_value * income_yield_annual

        # ── STEP 5: Rebuild state from holdings ──────────────────────
        cash_delta    = res_summary["cash_delta"]
        computed_cash = current_state.cash + cash_delta
        if -1e-8 < computed_cash < 1e-8:
            computed_cash = 0.0

        # Carry open_option forward so orchestrator can restore OptionsLedger
        # state on the next step. CP engine puts new-style OptionPos (with
        # position_id + expiry_date) in cp_summary; read from nested_reports.
        nested_cp_summary = orch_res["metadata"]["concentrated_position"]["summary"]
        new_open_option   = nested_cp_summary.get("open_option", None)

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
            # TLH inventory: prior balance + delta generated this step.
            # DecisionService consumed TLH internally; simulator only adds what
            # was generated. No tlh_used subtraction needed here.
            tlh_inventory=current_state.tlh_inventory + tlh_delta_this_step,
            risk_score=current_state.risk_score,
            client_constraint=current_state.client_constraint,
            open_option=new_open_option,
            applied_event_ids=current_state.applied_event_ids,
        )
        current_state = new_state

        # ── [CP AUDIT] Logging & Validation ──────────────────────────
        shares_after         = new_state.shares
        option_open          = nested_cp_summary.get("is_option_open", False)
        option_premium       = nested_cp_summary.get("open_option_premium", 0.0)
        tlh_realized_this_step = nested_cp_summary.get("realized_option_loss", 0.0)
        tlh_inventory_after  = new_state.tlh_inventory

        trace_log("\n[CP AUDIT]")
        trace_log(f"month: {month}")
        trace_log(f"shares_before: {shares_before}")
        trace_log(f"shares_sold: {shares_sold}")
        trace_log(f"shares_after: {shares_after}\n")
        trace_log(f"option_open: {option_open}")
        trace_log(f"option_premium: {option_premium:.2f}\n")
        trace_log(f"tlh_inventory_before: {tlh_inventory_before:.2f}")
        trace_log(f"tlh_delta_this_step: {tlh_delta_this_step:.2f}")
        trace_log(f"tlh_inventory_after: {tlh_inventory_after:.2f}\n")

        warnings = []

        if tlh_inventory_after < tlh_inventory_before:
            warnings.append("tlh_inventory decreased (unexpected without a sell)")

        if previous_option_open and not option_open:
            if (
                nested_cp_summary.get("realized_option_pnl", 0.0) == 0.0
                and nested_cp_summary.get("option_buyback_cost", 0.0) == 0.0
            ):
                warnings.append("option disappearance — no realized pnl or buyback cost recorded")

        # Cash invariant: cash_after == cash_before + option_income + sales - purchases
        # option_pnl key is now in orch_summary (net_option_result from CP engine)
        option_income_step = res_summary.get("option_income", 0.0)
        purchases          = to_income + to_model
        expected_cash      = cash_before + option_income_step + capital_released - purchases

        assert abs(new_state.cash - expected_cash) < 0.01, (
            f"Cash Invariant Failed: {new_state.cash:.4f} != {expected_cash:.4f} "
            f"(before={cash_before:.2f}, option_income={option_income_step:.2f}, "
            f"released={capital_released:.2f}, purchases={purchases:.2f})"
        )

        # TLH invariant: inventory_after == inventory_before + delta_this_step
        # DecisionService manages internal consumption; simulator only adds generated delta.
        expected_tlh = tlh_inventory_before + tlh_delta_this_step
        assert abs(tlh_inventory_after - expected_tlh) < 0.01, (
            f"TLH Invariant Failed: {tlh_inventory_after:.4f} != "
            f"{tlh_inventory_before:.4f} + {tlh_delta_this_step:.4f}"
        )

        if warnings:
            trace_log("\n[CP WARNING]")
            for w in warnings:
                trace_log(f"* {w}")

        previous_option_open = option_open

        trace_log(f"--- [MODULE 5] STATE MUTATION TRACE ---")
        trace_log(f"Income generated: {income_generated:.2f} -> New Income Value: {current_state.income_value:.2f}")
        trace_log(f"Model growth: {model_growth:.2f} -> New Model Value: {current_state.model_value:.2f}")
        trace_log(f"New CP Value: {current_state.market_value:.2f}")
        trace_log(f"Cash Delta: {cash_delta:.2f}")
        trace_log(f"Shares Sold: {shares_sold}")

        trace_log(f"\n[STATE CHECK]")
        trace_log(f"Month: {month}")
        trace_log(f"Computed Value: {new_income_value + new_model_value + new_cp_value:.2f}")
        trace_log(f"Reported Value: {new_state.income_value + new_state.model_value + new_state.market_value:.2f}\n")

        # ── STEP 6: Capture snapshot ──────────────────────────────────
        snapshot = build_snapshot(
            month, current_state,
            shares_sold, capital_released, to_income, to_model,
            income_generated=income_generated,
            model_growth=model_growth,
            cp_price=current_price,
            decision_log=orch_res.get("orch_summary", {}).get("decision_log", []),
        )

        # ── STEP 7: Reconciliation ────────────────────────────────────
        prev_snapshot = timeline[-1]
        recon         = reconcile_step(prev_snapshot, snapshot)
        snapshot["reconciliation"] = recon

        is_valid = recon["is_flow_valid"] and recon["is_sum_valid"]
        print(f"Month {month} | Flow Δ: {recon['flow_delta']} | Sum Δ: {recon['sum_delta']} | Valid: {str(is_valid).lower()}")

        if not is_valid:
            print(f"  WARNING: Reconciliation failed for Month {month}")
            print(f"  Details: {recon['details']}")

        if export_reconciliation:
            details = recon.get("details", {})
            reconciliation_report.append({
                "month":        month,
                "start_value":  details.get("start_value", 0.0),
                "end_value":    details.get("end_value", 0.0),
                "cp_change":    details.get("cp_change", 0.0),
                "income_change": details.get("income_change", 0.0),
                "model_change": details.get("model_change", 0.0),
                "cash_change":  details.get("cash_change", 0.0),
                "flow_delta":   recon.get("flow_delta", 0.0),
                "sum_delta":    recon.get("sum_delta", 0.0),
                "is_flow_valid": recon.get("is_flow_valid", True),
                "is_sum_valid":  recon.get("is_sum_valid", True),
                "concentrated_value": details.get("concentrated_value", 0.0),
                "income_value": details.get("income_value", 0.0),
                "model_value":  details.get("model_value", 0.0),
                "cash":         details.get("cash", 0.0),
            })

        timeline.append(snapshot)

        # ── STEP 8: Ledger trace & validation ─────────────────────────
        from ai_advisory.orchestration.ledger import get_ledger
        current_ledger = get_ledger()

        trace_log("[LEDGER]")
        trace_log(f"Month: {month}")
        trace_log(f"Events Recorded: {len(current_ledger)}")

        if len(current_ledger) < total_trades_executed:
            trace_log(
                f"WARNING: LEDGER MISMATCH - "
                f"Expected at least {total_trades_executed} trades, got {len(current_ledger)}"
            )

        if current_shares <= 0.001:
            break

        os.makedirs("outputs", exist_ok=True)

        try:
            with open("outputs/reconciliation_report.json", "w") as f:
                json.dump(reconciliation_report, f, indent=2)
        except Exception as e:
            print(f"Failed to write reconciliation JSON: {e}")

        try:
            with open("outputs/reconciliation_report.csv", "w", newline='') as f:
                if reconciliation_report:
                    csv_cols = [
                        "month", "start_value", "end_value", "cp_change",
                        "income_change", "model_change", "cash_change",
                        "flow_delta", "sum_delta", "is_flow_valid", "is_sum_valid",
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

    for step in timeline:
        trace = step.get("decision_trace", [])
        blocking = next(
            (e for e in trace if e.get("rule") == "FINAL_DECISION"), {}
        )
        trace_log(
            f"Month {step['month']:>2} | "
            f"mode={step.get('decision_mode','?'):<30} | "
            f"sold={step['strategies']['concentrated']['shares_sold']:>6} | "
            f"blocked_by={blocking.get('blocking_reason','none')}"
        )

    return timeline
