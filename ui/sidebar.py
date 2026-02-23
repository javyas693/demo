import streamlit as st


def build_sidebar_inputs() -> dict:
    st.sidebar.caption("SIDEBAR LOADED ✅ (ui/sidebar.py)")
    st.sidebar.header("Analysis Parameters")

    ticker = st.sidebar.text_input("Ticker", value="AAPL", key="ticker")
    start = st.sidebar.text_input("Start Date (YYYY-MM-DD)", value="2020-01-01", key="start")
    end = st.sidebar.text_input("End Date (YYYY-MM-DD)", value="2026-01-01", key="end")

    st.sidebar.header("Mode")
    analysis_mode = st.sidebar.radio(
        "Mode",
        ["Basic Performance", "Unwind Strategy"],
        key="analysis_mode",
        label_visibility="collapsed",
    )

    # Defaults so app.py can always read them safely
    params = {
        "ticker": ticker,
        "start": start,
        "end": end,
        "analysis_mode": analysis_mode,
        "initial_shares": 10000,
        "coverage_pct": 50.0,
        "call_moneyness_pct": 5.0,
        "dte_days": 45,
        "roll_frequency_days": 30,
        "enable_tax_loss_harvest": True,
        "position_reduction_pct": 0.0,
        "reduction_threshold_pct": None,

        # Legacy UI defaults (still passed by app.py)
        "sell_shares_on_call_loss": False,
        "sell_shares_on_call_loss_pct": 5.0,
        "min_call_loss_to_trigger": 400.0,

        # NEW: trigger for tax-neutral reduction (0.10 = 10%)
        "share_reduction_trigger_pct": 0.0,
    }

    if analysis_mode == "Unwind Strategy":
        st.sidebar.header("Strategy (Unwind)")

        params["initial_shares"] = st.sidebar.number_input(
            "Initial Shares",
            min_value=100,
            max_value=1_000_000,
            value=10_000,
            step=100,
            key="initial_shares",
        )

        params["coverage_pct"] = st.sidebar.slider(
            "Coverage %",
            min_value=0.0,
            max_value=100.0,
            value=50.0,
            step=5.0,
            key="coverage_pct",
        )

        params["call_moneyness_pct"] = st.sidebar.slider(
            "Call Moneyness % (OTM)",
            min_value=1.0,
            max_value=20.0,
            value=5.0,
            step=1.0,
            key="call_moneyness_pct",
        )

        params["dte_days"] = st.sidebar.slider(
            "Days to Expiration (DTE)",
            min_value=15,
            max_value=90,
            value=45,
            step=5,
            key="dte_days",
        )

        params["roll_frequency_days"] = st.sidebar.slider(
            "Roll Frequency (days)",
            min_value=7,
            max_value=60,
            value=30,
            step=7,
            key="roll_frequency_days",
        )

        params["enable_tax_loss_harvest"] = st.sidebar.checkbox(
            "Enable Tax-Loss Harvesting",
            value=True,
            key="enable_tax_loss_harvest",
        )

        # --- Legacy UI section (kept for backwards compatibility, engine ignores these now) ---
        st.sidebar.subheader("Call-Loss Driven Reduction (Legacy UI)")
        params["sell_shares_on_call_loss"] = st.sidebar.checkbox(
            "Sell shares when call is bought back at a loss",
            value=False,
            key="sell_shares_on_call_loss",
        )
        params["sell_shares_on_call_loss_pct"] = st.sidebar.slider(
            "Sell % of shares when triggered",
            min_value=0.0,
            max_value=50.0,
            value=5.0,
            step=1.0,
            key="sell_shares_on_call_loss_pct",
        )
        params["min_call_loss_to_trigger"] = st.sidebar.number_input(
            "Minimum option loss to trigger ($)",
            min_value=0.0,
            value=400.0,
            step=50.0,
            key="min_call_loss_to_trigger",
        )

        # --- NEW trigger for tax-neutral reduction ---
        st.sidebar.subheader("Tax-Neutral Reduction Trigger")
        params["share_reduction_trigger_pct"] = (
            st.sidebar.slider(
                "Sell shares only if price is up by at least (%) vs cost basis",
                min_value=0.0,
                max_value=50.0,
                value=0.0,
                step=1.0,
                key="share_reduction_trigger_pct",
            ) / 100.0
        )

        # --- Optional scheduled reduction rules (engine supports these) ---
        st.sidebar.subheader("Other Reduction Rules")
        reduction_method = st.sidebar.radio(
            "Method",
            ["None", "Quarterly %", "Price Threshold"],
            key="reduction_method",
        )

        if reduction_method == "Quarterly %":
            params["position_reduction_pct"] = st.sidebar.slider(
                "Quarterly Reduction %",
                min_value=0.0,
                max_value=25.0,
                value=5.0,
                step=1.0,
                key="position_reduction_pct",
            )
            params["reduction_threshold_pct"] = None

        elif reduction_method == "Price Threshold":
            params["reduction_threshold_pct"] = st.sidebar.slider(
                "Price Gain Threshold %",
                min_value=10.0,
                max_value=100.0,
                value=20.0,
                step=5.0,
                key="reduction_threshold_pct",
            )
            params["position_reduction_pct"] = 0.0

        else:
            params["position_reduction_pct"] = 0.0
            params["reduction_threshold_pct"] = None

    st.sidebar.markdown("---")
    params["analyze_button"] = st.sidebar.button(
        "Analyze",
        type="primary",
        use_container_width=True,
        key="analyze_button",
    )

    return params
