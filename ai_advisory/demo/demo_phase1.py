import json
from pathlib import Path
from datetime import datetime, date

import pandas as pd
import streamlit as st

from ai_advisory.core.ids import new_id
from ai_advisory.core.ledger import LedgerEvent, apply_event
from ai_advisory.portfolio.portfolio_state import PortfolioState


# ----------------------------
# Frontier helpers
# ----------------------------
def _list_as_of_dates(store_root: str) -> list[str]:
    root = Path(store_root)
    if not root.exists():
        return []
    dates = []
    for p in root.glob("asof=*"):
        if p.is_dir():
            dates.append(p.name.replace("asof=", ""))
    return sorted(dates)


def _load_latest_models(store_root: str, as_of: str) -> dict:
    p = Path(store_root) / f"asof={as_of}" / "latest.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8")).get("models", {})


@st.cache_data(show_spinner=False)
def _load_frontier_artifacts(store_root: str, as_of: str, frontier_version: str):
    base = Path(store_root) / f"asof={as_of}" / f"frontier_version={frontier_version}"
    points = pd.read_parquet(base / "points.parquet").sort_values("risk_score")
    weights = pd.read_parquet(base / "weights.parquet").sort_values("risk_score")
    spec = json.loads((base / "spec.json").read_text(encoding="utf-8"))
    return points, weights, spec


# ----------------------------
# Phase 1 demo: build a sample state
# ----------------------------
def build_demo_state() -> PortfolioState:
    state = PortfolioState(
        schema_version="v1",
        engine_version="0.1.0",
        id=new_id("state"),
        user_id="u_123",
        as_of=date.today(),
        created_at=datetime.now(),
    )

    # Deposit 10,000
    apply_event(state, LedgerEvent(
        schema_version="v1",
        id=new_id("event"),
        user_id="u_123",
        created_at=datetime.now(),
        as_of=date.today(),
        engine_version="0.1.0",
        event_type="deposit",
        sleeve="core",
        amount=10000.0,
    ))

    # Buy 10 shares of SPY at 500
    apply_event(state, LedgerEvent(
        schema_version="v1",
        id=new_id("event"),
        user_id="u_123",
        created_at=datetime.now(),
        as_of=date.today(),
        engine_version="0.1.0",
        event_type="buy_fill",
        sleeve="core",
        symbol="SPY",
        quantity=10,
        price=500.0,
    ))

    # Buy 5 shares of IEF at 100
    apply_event(state, LedgerEvent(
        schema_version="v1",
        id=new_id("event"),
        user_id="u_123",
        created_at=datetime.now(),
        as_of=date.today(),
        engine_version="0.1.0",
        event_type="buy_fill",
        sleeve="core",
        symbol="IEF",
        quantity=5,
        price=100.0,
    ))

    # Sell 2 shares of SPY at 510
    apply_event(state, LedgerEvent(
        schema_version="v1",
        id=new_id("event"),
        user_id="u_123",
        created_at=datetime.now(),
        as_of=date.today(),
        engine_version="0.1.0",
        event_type="sell_fill",
        sleeve="core",
        symbol="SPY",
        quantity=2,
        price=510.0,
    ))

    return state


# ----------------------------
# Streamlit UI
# ----------------------------
st.set_page_config(page_title="AI Advisory Demo", layout="wide")
st.title("AI Advisory Demo")

tab1, tab2 = st.tabs(["Phase 1: Portfolio Ledger", "Phase 2: Efficient Frontier"])

with tab1:
    st.header("Phase 1: Portfolio Ledger (event-sourced)")

    state = build_demo_state()

    c1, c2, c3 = st.columns(3)
    c1.metric("Cash", f"${state.cash_total():,.2f}")
    c2.metric("Total Value", f"${state.total_portfolio_value():,.2f}")
    c3.metric("Positions", f"{len(state.positions)}")

    st.subheader("Positions")
    pos_rows = [{
        "Symbol": p.symbol,
        "Sleeve": p.sleeve,
        "Quantity": p.quantity,
        "Market Value": p.market_value,
    } for p in state.positions]
    st.dataframe(pd.DataFrame(pos_rows), use_container_width=True)

with tab2:
    st.header("Phase 2: Efficient Frontier Viewer")

    store_root = st.text_input("Frontier Store Root", value="data/frontiers")

    as_of_dates = _list_as_of_dates(store_root)
    if not as_of_dates:
        st.warning(f"No frontiers found under: {store_root}")
        st.stop()

    default_asof = as_of_dates[-1]
    as_of = st.selectbox("As-Of Date", options=as_of_dates, index=as_of_dates.index(default_asof))

    models = _load_latest_models(store_root, as_of)
    if not models:
        st.warning(f"No latest.json models found for as_of={as_of}")
        st.stop()

    model_ids = sorted(models.keys())
    default_model = "core" if "core" in model_ids else model_ids[0]
    model_id = st.selectbox("Model ID", options=model_ids, index=model_ids.index(default_model))

    frontier_version = models[model_id]
    st.caption(f"frontier_version: `{frontier_version}`")

    points, weights, spec = _load_frontier_artifacts(store_root, as_of, frontier_version)

    st.subheader("Frontier Curve (Volatility → Expected Return)")
    chart_df = points[["vol", "exp_return"]].copy().set_index("vol")
    st.line_chart(chart_df)

    st.subheader("Select Portfolio")
    risk_score = st.slider(
        "Risk Score",
        int(points["risk_score"].min()),
        int(points["risk_score"].max()),
        value=50,
        step=1
    )

    row_p = points[points["risk_score"] == risk_score].iloc[0]
    st.write(
        f"**Risk Score {risk_score}** | "
        f"Vol: **{row_p['vol']:.2%}** | "
        f"Exp Return: **{row_p['exp_return']:.2%}**"
    )

    row_w = weights[weights["risk_score"] == risk_score].drop(columns=["risk_score"]).iloc[0]
    w_df = row_w.reset_index()
    w_df.columns = ["Ticker", "Weight"]
    w_df["Weight"] = w_df["Weight"].astype(float)
    w_df = w_df.sort_values("Weight", ascending=False)

    left, right = st.columns([1, 1])
    with left:
        st.subheader("Top Weights")
        st.dataframe(w_df[w_df["Weight"] > 0.0001].head(25), use_container_width=True)
    with right:
        st.subheader("Weights (bar)")
        st.bar_chart(w_df.set_index("Ticker")["Weight"])

    with st.expander("Show Frontier Spec"):
        st.json(spec)