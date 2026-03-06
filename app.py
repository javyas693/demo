import streamlit as st

from ai_advisory.strategy.engine import run_real_price_simulation, DataFetchError
from ai_advisory.strategy.strategy_unwind import run_strategy_comparison
from ui.sidebar import build_sidebar_inputs
from ui.formatters import fmt_money, fmt_pct
from viz.charts_main import make_two_line_portfolio_chart
from viz.charts_advanced import make_advanced_chart


def pick(d: dict, *keys, default=None):
    """Return the first non-None value found for keys in dict d."""
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] is not None:
            return d[k]
    return default


def overlay_summary_adapter(summary: dict) -> dict:
    """
    Normalize overlay summary keys across legacy and v1.

    v1 canonical fields (expected):
      - final_portfolio_value
      - total_return
      - final_shares
      - shares_reduced
      - realized_option_loss

    Legacy fields (may exist in older engine versions):
      - final_value_with_options
      - total_return_pct
      - option_pnl
      - total_pnl
      - cumulative_taxes
    """
    final_value = pick(summary, "final_portfolio_value", "final_value", "final_value_with_options")
    total_return = pick(summary, "total_return", "total_return_pct")
    final_shares = pick(summary, "final_shares", "ending_shares")
    shares_reduced = pick(summary, "shares_reduced", default=0)

    # v1: realized_option_loss might exist (positive loss)
    # legacy: option_pnl might exist (positive/negative pnl)
    realized_loss = pick(summary, "realized_option_loss", "realized_loss")
    realized_pnl = pick(summary, "realized_option_pnl", "option_pnl")

    if realized_loss is None and realized_pnl is not None:
        # If pnl is negative, loss is abs(negative pnl); otherwise 0
        realized_loss = abs(realized_pnl) if realized_pnl < 0 else 0.0

    return {
        "final_value": final_value,
        "total_return": total_return,
        "final_shares": final_shares,
        "shares_reduced": shares_reduced,
        "realized_option_loss": realized_loss,
        "__debug_trigger__": summary.get("__debug_trigger__"),
        # legacy carry-through (display only, never required)
        "option_pnl_legacy": pick(summary, "option_pnl"),
        "total_pnl_legacy": pick(summary, "total_pnl"),
        "cumulative_taxes_legacy": pick(summary, "cumulative_taxes"),
        # optional diagnostics passthrough (if engine still provides)
        "final_stock_value": pick(summary, "final_stock_value"),
        "final_cash_proceeds": pick(summary, "final_cash_proceeds"),
        "shares_sold_on_call_loss": pick(summary, "shares_sold_on_call_loss"),
        "__debug_trigger__": summary.get("__debug_trigger__"),
        "__debug_code_fingerprint__": summary.get("__debug_code_fingerprint__"),
    }


# ✅ MUST be first Streamlit call
st.set_page_config(page_title="Concentrated Position Advisory", layout="wide")

VERSION = "Feb 20 - Stable Unwind Demo"
st.caption(f"VERSION: {VERSION}")


st.title("📊 Concentrated Position Advisory Platform")
st.markdown("Analyze stock performance and evaluate concentrated position risks")

# -------------------------
# Session state (persist across reruns)
# -------------------------
st.session_state.setdefault("basic_result", None)
st.session_state.setdefault("unwind_results", None)
st.session_state.setdefault("advanced_choice", "Shares held over time")
st.session_state.setdefault("last_run", {"mode": None, "ticker": None, "start": None, "end": None})

# Sidebar params (includes analyze_button)
params = build_sidebar_inputs()

st.sidebar.write("DEBUG state ui trigger:",
                 st.session_state.get("share_reduction_trigger_pct_ui"))
st.sidebar.write("DEBUG state old trigger:",
                 st.session_state.get("share_reduction_trigger_pct"))
st.sidebar.write("DEBUG params trigger:",
                 params.get("share_reduction_trigger_pct"))

# -------------------------
# Run analysis ONLY when Analyze clicked
# -------------------------
if params.get("analyze_button", False):
    st.session_state.last_run = {
        "mode": params.get("analysis_mode"),
        "ticker": params.get("ticker"),
        "start": params.get("start"),
        "end": params.get("end"),
    }

    # Clear other mode cached output
    if params.get("analysis_mode") == "Basic Performance":
        st.session_state.unwind_results = None
    else:
        st.session_state.basic_result = None

    # -------------------------
    # Basic Performance
    # -------------------------
    if params.get("analysis_mode") == "Basic Performance":
        with st.spinner(f"Fetching {params['ticker'].upper()}..."):
            try:
                st.session_state.basic_result = run_real_price_simulation(
                    ticker=params["ticker"].upper(),
                    start=params["start"],
                    end=params["end"],
                )
                st.success(f"✅ Analyzed {params['ticker'].upper()} from {params['start']} to {params['end']}")
            except DataFetchError as e:
                st.session_state.basic_result = None
                st.error(f"❌ Data Fetch Error: {str(e)}")
            except Exception as e:
                st.session_state.basic_result = None
                st.error(f"❌ Unexpected Error: {str(e)}")

    # -------------------------
    # Unwind Strategy
    # -------------------------
    else:
        with st.spinner(f"Running unwind simulation for {params['ticker'].upper()}..."):
            try:
                st.session_state.unwind_results = run_strategy_comparison(
                    ticker=params["ticker"].upper(),
                    start_date=params["start"],
                    end_date=params["end"],
                    initial_shares=params["initial_shares"],
                    call_moneyness_pct=params["call_moneyness_pct"],
                    dte_days=params["dte_days"],
                    roll_frequency_days=params["roll_frequency_days"],
                    coverage_pct=params["coverage_pct"],
                    enable_tax_loss_harvest=params["enable_tax_loss_harvest"],
                    position_reduction_pct_per_quarter=params["position_reduction_pct"],
                    reduction_threshold_pct=params["reduction_threshold_pct"],
                    sell_shares_on_call_loss=params.get("sell_shares_on_call_loss", False),
                    sell_shares_on_call_loss_pct=params.get("sell_shares_on_call_loss_pct", 0.0),
                    min_call_loss_to_trigger=params.get("min_call_loss_to_trigger", 0.0),
                    share_reduction_trigger_pct=params.get("share_reduction_trigger_pct", 0.0),
                )
                st.success(f"✅ Simulated unwind strategy for {params['ticker'].upper()}")
            except ValueError as e:
                st.session_state.unwind_results = None
                st.error(f"❌ Data Error: {str(e)}")
            except Exception as e:
                st.session_state.unwind_results = None
                st.error(f"❌ Unexpected Error: {str(e)}")

# -------------------------
# Render UI from cached results
# -------------------------
mode = params.get("analysis_mode", "Basic Performance")

# =========================
# BASIC PERFORMANCE VIEW
# =========================
if mode == "Basic Performance":
    result = st.session_state.basic_result
    if result is None:
        st.info("👈 Choose a mode on the left, then tap **Analyze**.")
        st.stop()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Starting Price", fmt_money(result["start_price"]))
    c2.metric("Ending Price", fmt_money(result["end_price"]))
    c3.metric("Total Return", fmt_pct(result["total_return_pct"]))
    c4.metric("Data Points", f"{result['data_points']:,}")

    st.subheader("Price History")
    price_history = result.get("price_history")
    if price_history is not None and not price_history.empty:
        st.line_chart(price_history.set_index("Date")["Price"], use_container_width=True)
        with st.expander("View raw data"):
            st.dataframe(price_history, use_container_width=True)
    else:
        st.warning("No price history returned.")

# =========================
# UNWIND STRATEGY VIEW
# =========================
else:
    results = st.session_state.unwind_results
    if results is None:
        st.info("👈 Choose a mode on the left, then tap **Analyze**.")
        st.stop()

    baseline = results.get("baseline", {})
    overlay = results.get("overlay", {})

    baseline_ts = baseline.get("time_series")
    overlay_ts = overlay.get("time_series")

    summary_b = baseline.get("summary", {}) or {}
    summary_o_raw = overlay.get("summary", {}) or {}
    summary_o = overlay_summary_adapter(summary_o_raw)

    # --- Audit Log (short) ---
    audit_log = summary_o_raw.get("audit_log", []) or []

    if audit_log:
        with st.expander("🔎 Tax-Neutral Reduction Audit Log", expanded=False):
            for line in audit_log[-200:]:  # show last 200 lines max
                st.text(line)
    else:
        # optional: keep silent if none
        pass

    # Temporary: schema debug (remove once stable)
    # st.write("Overlay summary keys:", list(summary_o_raw.keys()))
    st.write("Engine version:", overlay.get("summary", {}).get("__engine_version__"))
    st.write("final_cash_proceeds:", overlay["summary"].get("final_cash_proceeds"))
    st.write("cumulative_taxes:", overlay["summary"].get("cumulative_taxes"))

    st.markdown("### Strategy Comparison")
    left, right = st.columns(2)

    with left:
        st.markdown("**🏦 Buy & Hold**")
        a, b = st.columns(2)

        b_final_value = pick(summary_b, "final_value")
        b_final_shares = pick(summary_b, "final_shares")
        b_total_return = pick(summary_b, "total_return_pct", "total_return")
        b_total_pnl = pick(summary_b, "total_pnl")

        a.metric("Final Value", fmt_money(b_final_value) if b_final_value is not None else "—")
        b.metric("Final Shares", f"{int(b_final_shares):,}" if b_final_shares is not None else "—")
        a.metric("Total Return", fmt_pct(b_total_return) if b_total_return is not None else "—")
        b.metric("Total P&L", fmt_money(b_total_pnl) if b_total_pnl is not None else "—")

    with right:
        st.markdown("**📈 Covered Call Strategy**")
        a, b = st.columns(2)

        a.metric("Final Value", fmt_money(summary_o["final_value"]) if summary_o["final_value"] is not None else "—")
        b.metric("Final Shares", f"{int(summary_o['final_shares']):,}" if summary_o["final_shares"] is not None else "—")
        a.metric("Total Return", fmt_pct(summary_o["total_return"]) if summary_o["total_return"] is not None else "—")

        # v1 headline discipline metric
        if summary_o["realized_option_loss"] is not None:
            b.metric("Realized Option Loss", fmt_money(summary_o["realized_option_loss"]))
        elif summary_o["shares_reduced"] is not None:
            b.metric("Shares Reduced", f"{int(summary_o['shares_reduced']):,}")
        else:
            b.metric("Realized Option Loss", "—")

    st.markdown("### Portfolio Value Over Time")
    fig_main = make_two_line_portfolio_chart(baseline_ts, overlay_ts)
    if fig_main is None:
        st.warning("Could not build portfolio value chart (missing expected columns).")
    else:
        st.plotly_chart(fig_main, use_container_width=True)

    with st.expander("Strategy details (quick)"):
        d1, d2, d3 = st.columns(3)

        d1.metric("Shares Reduced", f"{int(summary_o.get('shares_reduced') or 0):,}")

        total_pnl_legacy = summary_o.get("total_pnl_legacy")
        d2.metric("Total P&L", fmt_money(total_pnl_legacy) if total_pnl_legacy is not None else "—")

        taxes_legacy = summary_o.get("cumulative_taxes_legacy")
        d3.metric("Tax Impact", fmt_money(taxes_legacy) if taxes_legacy is not None else "—")

        # Optional diagnostics (only show if present)
        dd1, dd2, dd3 = st.columns(3)
        dd1.metric("Final Stock Value", fmt_money(summary_o.get("final_stock_value")) if summary_o.get("final_stock_value") is not None else "—")
        dd2.metric("Final Income Cash Balance", 
            fmt_money(summary_o.get("final_cash_proceeds")) 
            if summary_o.get("final_cash_proceeds") is not None else "—")
        dd3.metric("Shares Sold on Call Loss", f"{int(summary_o.get('shares_sold_on_call_loss')):,}" if summary_o.get("shares_sold_on_call_loss") is not None else "—")
        
        st.write("Fingerprint:", summary_o.get("__debug_code_fingerprint__"))
        st.write("DEBUG trigger pct:", summary_o.get("__debug_trigger__"))
        
    with st.expander("Advanced details"):
        choice = st.selectbox(
            "Choose a chart",
            ["Shares held over time", "Total P&L over time", "Stock vs Option P&L", "Cumulative tax impact"],
            key="advanced_choice",
        )
        fig_adv = make_advanced_chart(choice, baseline_ts, overlay_ts)
        if fig_adv is not None:
            st.plotly_chart(fig_adv, use_container_width=True)

        with st.expander("View detailed time series data"):
            tab1, tab2 = st.tabs(["Baseline", "Overlay"])
            with tab1:
                st.dataframe(baseline_ts, use_container_width=True)
            with tab2:
                st.dataframe(overlay_ts, use_container_width=True)

    st.markdown("### Insights")

    overlay_return = summary_o.get("total_return")
    baseline_return = pick(summary_b, "total_return_pct", "total_return")

    if overlay_return is None or baseline_return is None:
        st.warning("Missing return metrics in summary; cannot compute outperformance.")
        st.stop()

    diff = overlay_return - baseline_return
    shares_reduced_val = summary_o.get("shares_reduced") or 0
    shares_reduced_pct = (shares_reduced_val / float(params["initial_shares"])) * 100.0

    if diff >= 0:
        st.success(f"Overlay outperformed by {diff:.2f}% and reduced the position by {shares_reduced_pct:.1f}%.")
    else:
        st.info(f"Overlay underperformed by {abs(diff):.2f}% but reduced the position by {shares_reduced_pct:.1f}%.")

    # v1: taxes are not modeled; only show if legacy field exists
    taxes_legacy = summary_o.get("cumulative_taxes_legacy")
    if params.get("enable_tax_loss_harvest", False) and (taxes_legacy is not None) and taxes_legacy < 0:
        st.info(f"Tax-loss harvesting benefit (approx): {fmt_money(abs(taxes_legacy))}")

    st.caption("Disclaimer: Educational simulation only. Simplified assumptions for options pricing/taxes. Not financial advice.")
