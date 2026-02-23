"""
Main portfolio chart for comparing two strategies.
"""
import pandas as pd
import plotly.graph_objects as go


# Color palette for charts
CHART_COLORS = {
    "baseline": "blue",
    "overlay": "green",
    "stock_pnl": "purple",
    "option_pnl": "orange",
    "tax": "red",
}


def _safe_series(df: pd.DataFrame, col: str):
    """Return series from dataframe if column exists, else None."""
    return df[col] if col in df.columns else None


def _portfolio_value_series(df: pd.DataFrame):
    """
    Build a portfolio value series robustly without assuming exact column names.
    Uses: initial Stock_Value + Total_PnL (if available).
    Falls back to Stock_Value if Total_PnL missing.
    """
    if df is None or df.empty:
        return None

    stock_val = _safe_series(df, "Stock_Value")
    total_pnl = _safe_series(df, "Total_PnL")

    if stock_val is not None and total_pnl is not None:
        initial_val = float(stock_val.iloc[0])
        return initial_val + total_pnl.astype(float)

    # fallback 1: direct portfolio value column if present
    for c in ["Portfolio Value", "Portfolio_Value", "PortfolioValue", "Total_Value", "TotalValue"]:
        if c in df.columns:
            return df[c].astype(float)

    # fallback 2: stock value only
    if stock_val is not None:
        return stock_val.astype(float)

    return None


def make_two_line_portfolio_chart(baseline_ts: pd.DataFrame, overlay_ts: pd.DataFrame):
    """
    Create a 2-line portfolio value chart comparing baseline and overlay strategies.
    
    Args:
        baseline_ts: Time series dataframe for baseline strategy
        overlay_ts: Time series dataframe for overlay strategy
    
    Returns:
        Plotly Figure object or None if required data columns are missing
    """
    y_base = _portfolio_value_series(baseline_ts)
    y_over = _portfolio_value_series(overlay_ts)

    if y_base is None or y_over is None:
        return None

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=baseline_ts["Date"],
            y=y_base,
            name="Buy & Hold",
            line=dict(color=CHART_COLORS["baseline"], width=3),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=overlay_ts["Date"],
            y=y_over,
            name="Covered Call Strategy",
            line=dict(color=CHART_COLORS["overlay"], width=3),
        )
    )

    fig.update_layout(
        height=420,
        margin=dict(l=16, r=16, t=24, b=16),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        yaxis_title="Portfolio Value ($)",
        xaxis_title="Date",
        hovermode="x unified",
    )
    return fig
