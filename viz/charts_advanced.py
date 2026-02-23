"""
Advanced charts for detailed analysis.
"""
import pandas as pd
import plotly.graph_objects as go

from .charts_main import CHART_COLORS


_REQUIRED = {
    "Shares held over time": ["Date", "Shares"],
    "Total P&L over time": ["Date", "Total_PnL"],
    "Stock vs Option P&L": ["Date", "Stock_PnL", "Option_PnL"],
    "Cumulative tax impact": ["Date", "Cumulative_Taxes"],
}


def _missing_columns(choice: str, baseline_ts: pd.DataFrame, overlay_ts: pd.DataFrame) -> list[str]:
    required_cols = _REQUIRED.get(choice, ["Date"])
    missing = []

    # For each required col, accept it if it's in either dataframe (some charts use overlay only)
    for col in required_cols:
        if (col not in baseline_ts.columns) and (col not in overlay_ts.columns):
            missing.append(col)

    return missing


def make_advanced_chart(choice: str, baseline_ts: pd.DataFrame, overlay_ts: pd.DataFrame):
    """
    Create an advanced chart based on user selection.
    Always returns a Plotly Figure (never None).
    """
    fig = go.Figure()

    # ✅ Validate columns safely INSIDE the function
    missing = _missing_columns(choice, baseline_ts, overlay_ts)
    if missing:
        fig.update_layout(
            title=f"Missing columns for '{choice}': {', '.join(missing)}",
            height=250,
            margin=dict(l=16, r=16, t=40, b=16),
        )
        return fig

    if choice == "Shares held over time":
        fig.add_trace(
            go.Scatter(
                x=baseline_ts["Date"],
                y=baseline_ts["Shares"],
                name="Baseline Shares",
                line=dict(color=CHART_COLORS["baseline"], width=3),
            )
        )
        fig.add_trace(
            go.Scatter(
                x=overlay_ts["Date"],
                y=overlay_ts["Shares"],
                name="Overlay Shares",
                line=dict(color=CHART_COLORS["overlay"], width=3),
            )
        )
        fig.update_layout(yaxis_title="Shares")

    elif choice == "Total P&L over time":
        fig.add_trace(
            go.Scatter(
                x=baseline_ts["Date"],
                y=baseline_ts["Total_PnL"],
                name="Baseline Total P&L",
                line=dict(color=CHART_COLORS["baseline"], width=3),
            )
        )
        fig.add_trace(
            go.Scatter(
                x=overlay_ts["Date"],
                y=overlay_ts["Total_PnL"],
                name="Overlay Total P&L",
                line=dict(color=CHART_COLORS["overlay"], width=3),
            )
        )
        fig.update_layout(yaxis_title="P&L ($)")

    elif choice == "Stock vs Option P&L":
        fig.add_trace(
            go.Scatter(
                x=overlay_ts["Date"],
                y=overlay_ts["Stock_PnL"],
                name="Stock P&L",
                line=dict(color=CHART_COLORS["stock_pnl"], width=3),
            )
        )
        fig.add_trace(
            go.Scatter(
                x=overlay_ts["Date"],
                y=overlay_ts["Option_PnL"],
                name="Option P&L",
                line=dict(color=CHART_COLORS["option_pnl"], width=3),
            )
        )
        fig.update_layout(yaxis_title="P&L ($)")

    elif choice == "Cumulative tax impact":
        fig.add_trace(
            go.Scatter(
                x=overlay_ts["Date"],
                y=overlay_ts["Cumulative_Taxes"],
                name="Tax Impact",
                line=dict(color=CHART_COLORS["tax"], width=3),
            )
        )
        fig.update_layout(yaxis_title="Tax ($)")

    fig.update_layout(
        height=420,
        margin=dict(l=16, r=16, t=24, b=16),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
        ),
        xaxis_title="Date",
        hovermode="x unified",
    )

    return fig
