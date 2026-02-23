"""
Formatting helpers for money and percentage values.
"""


def fmt_money(x) -> str:
    """Format a number as money with $ and commas."""
    try:
        return f"${float(x):,.2f}"
    except (ValueError, TypeError):
        return str(x)


def fmt_pct(x) -> str:
    """Format a number as a percentage with + sign."""
    try:
        return f"{float(x):+.2f}%"
    except (ValueError, TypeError):
        return str(x)
