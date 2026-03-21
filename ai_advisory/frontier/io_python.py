"""
io_python.py — Python-native replacement for io_xlsx.py

Provides the same two data structures the engine expects:
  1. allocation_config()  →  dict matching load_allocation_workbook() output
  2. load_prices_from_yfinance()  →  pd.DataFrame matching load_prices_matrix() output

Universe is derived from the OptimizedPortfolios.xlsx sample run:
  Top-Level:  SPY, IEF, IAU, SCHH, PGX, BTC-USD, BIL
  Sub-Assets: SPY, IJH, IWM, VWO, VEA, IEF, SHY, TLT, LEMB, HYG, VCLT, IAU, SCHH, PGX, BTC-USD, BIL

To add or remove tickers, edit UNIVERSE_SUB_ASSETS below.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
# Universe metadata
# Each entry: (asset_class, sub_asset_class, name, yield, expense_ratio, min_w, max_w)
# ─────────────────────────────────────────────────────────────────────────────

_TICKER_META: Dict[str, dict] = {
    # ── Equities ──────────────────────────────────────────────────────────────
    "SPY": dict(
        asset_class="Equities", sub_asset_class="Large-Cap U.S.",
        name="SPDR S&P 500 ETF",
        yield_=0.013, expense_ratio=0.0009,
        min_w=0.00, max_w=0.97,
    ),
    "IJH": dict(
        asset_class="Equities", sub_asset_class="Mid-Cap U.S.",
        name="iShares Core S&P Mid-Cap ETF",
        yield_=0.012, expense_ratio=0.0005,
        min_w=0.00, max_w=0.20,
    ),
    "IWM": dict(
        asset_class="Equities", sub_asset_class="Small-Cap U.S.",
        name="iShares Russell 2000 ETF",
        yield_=0.011, expense_ratio=0.0019,
        min_w=0.00, max_w=0.20,
    ),
    "VWO": dict(
        asset_class="Equities", sub_asset_class="Emerging Markets",
        name="Vanguard FTSE Emerging Markets ETF",
        yield_=0.030, expense_ratio=0.0008,
        min_w=0.00, max_w=0.20,
    ),
    "VEA": dict(
        asset_class="Equities", sub_asset_class="Developed Markets",
        name="Vanguard FTSE Developed Markets ETF",
        yield_=0.030, expense_ratio=0.0005,
        min_w=0.00, max_w=0.20,
    ),
    # ── Fixed Income ──────────────────────────────────────────────────────────
    "IEF": dict(
        asset_class="Fixed Income", sub_asset_class="Intermediate Treasury",
        name="iShares 7-10 Year Treasury Bond ETF",
        yield_=0.038, expense_ratio=0.0015,
        min_w=0.00, max_w=0.80,
    ),
    "SHY": dict(
        asset_class="Fixed Income", sub_asset_class="Short-Term Treasury",
        name="iShares 1-3 Year Treasury Bond ETF",
        yield_=0.050, expense_ratio=0.0015,
        min_w=0.00, max_w=0.80,
    ),
    "TLT": dict(
        asset_class="Fixed Income", sub_asset_class="Long-Term Treasury",
        name="iShares 20+ Year Treasury Bond ETF",
        yield_=0.034, expense_ratio=0.0015,
        min_w=0.00, max_w=0.40,
    ),
    "LEMB": dict(
        asset_class="Fixed Income", sub_asset_class="EM Local Currency",
        name="iShares EM Local Currency Bond ETF",
        yield_=0.060, expense_ratio=0.0030,
        min_w=0.00, max_w=0.15,
    ),
    "HYG": dict(
        asset_class="Fixed Income", sub_asset_class="High-Yield Corporate",
        name="iShares iBoxx High Yield Corporate Bond ETF",
        yield_=0.066, expense_ratio=0.0048,
        min_w=0.00, max_w=0.15,
    ),
    "VCLT": dict(
        asset_class="Fixed Income", sub_asset_class="Long-Term Corporate",
        name="Vanguard Long-Term Corporate Bond ETF",
        yield_=0.055, expense_ratio=0.0004,
        min_w=0.00, max_w=0.20,
    ),
    # ── Alternatives ──────────────────────────────────────────────────────────
    "IAU": dict(
        asset_class="Alternatives", sub_asset_class="Commodities",
        name="iShares Gold Trust",
        yield_=0.000, expense_ratio=0.0025,
        min_w=0.00, max_w=0.10,
    ),
    "SCHH": dict(
        asset_class="Real Estate", sub_asset_class="Real Estate",
        name="Schwab U.S. REIT ETF",
        yield_=0.030, expense_ratio=0.0007,
        min_w=0.00, max_w=0.10,
    ),
    "PGX": dict(
        asset_class="Preferred Stocks", sub_asset_class="Preferred Stocks",
        name="Invesco Preferred ETF",
        yield_=0.060, expense_ratio=0.0052,
        min_w=0.00, max_w=0.10,
    ),
    "BTC-USD": dict(
        asset_class="Alternatives", sub_asset_class="Alternatives",
        name="Bitcoin",
        yield_=0.000, expense_ratio=0.000,
        min_w=0.00, max_w=0.03,
    ),
    # ── Cash ──────────────────────────────────────────────────────────────────
    "BIL": dict(
        asset_class="Cash", sub_asset_class="Cash",
        name="SPDR Bloomberg 1-3 Month T-Bill ETF",
        yield_=0.053, expense_ratio=0.0014,
        min_w=0.00, max_w=0.30,
    ),
}

# Top-level (asset class) universe — fewer, broader ETFs
UNIVERSE_ASSET_CLASS: List[str] = ["SPY", "IEF", "IAU", "SCHH", "PGX", "BTC-USD", "BIL"]

# Sub-asset universe — full granularity
UNIVERSE_SUB_ASSETS: List[str] = list(_TICKER_META.keys())


# ─────────────────────────────────────────────────────────────────────────────
# Allocation config builder
# Returns the same dict shape that load_allocation_workbook() produces so the
# rest of engine.py needs zero changes.
# ─────────────────────────────────────────────────────────────────────────────

def _build_alloc_obj(tickers: List[str]) -> dict:
    bounds: Dict[str, Tuple[float, float]] = {}
    asset_class_map: Dict[str, str] = {}
    sub_asset_class_map: Dict[str, str] = {}
    name_map: Dict[str, str] = {}
    yield_map: Dict[str, float] = {}
    expense_ratio_map: Dict[str, float] = {}

    for t in tickers:
        m = _TICKER_META[t]
        bounds[t] = (m["min_w"], m["max_w"])
        asset_class_map[t] = m["asset_class"]
        sub_asset_class_map[t] = m["sub_asset_class"]
        name_map[t] = m["name"]
        yield_map[t] = m["yield_"]
        expense_ratio_map[t] = m["expense_ratio"]

    return {
        "assets": tickers,
        "bounds": bounds,
        "asset_class_map": asset_class_map,
        "sub_asset_class_map": sub_asset_class_map,
        "name_map": name_map,
        "yield_map": yield_map,
        "expense_ratio_map": expense_ratio_map,
    }


def allocation_config() -> dict:
    """
    Drop-in replacement for load_allocation_workbook().
    Returns dict with keys: asset_class, sub_assets.
    """
    return {
        "asset_class": _build_alloc_obj(UNIVERSE_ASSET_CLASS),
        "sub_assets":  _build_alloc_obj(UNIVERSE_SUB_ASSETS),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Prices from yfinance
# Returns daily close price DataFrame indexed by Date — same shape as
# load_prices_matrix() so compute_historical_cov() needs zero changes.
# ─────────────────────────────────────────────────────────────────────────────

def load_prices_from_yfinance(
    tickers: Optional[List[str]] = None,
    period: str = "5y",
    cache_path: Optional[str] = None,
) -> pd.DataFrame:
    """
    Fetch historical daily close prices for the universe via yfinance.

    Parameters
    ----------
    tickers    : list of tickers to fetch (defaults to full UNIVERSE_SUB_ASSETS)
    period     : yfinance period string, e.g. "5y", "3y", "max"
    cache_path : optional path to a pickle file — read if exists, write after fetch.
                 Useful for test runs / environments with rate limits.

    Returns
    -------
    pd.DataFrame  rows=dates, columns=tickers, values=adjusted close prices
    """
    import yfinance as yf

    if tickers is None:
        tickers = UNIVERSE_SUB_ASSETS

    # BTC-USD is in the universe; yfinance handles it natively
    symbols = list(tickers)

    # ── Try cache first ───────────────────────────────────────────────────────
    if cache_path:
        import os
        if os.path.exists(cache_path):
            try:
                df = pd.read_pickle(cache_path)
                # Validate: must contain all requested tickers
                missing = [t for t in symbols if t not in df.columns]
                if not missing:
                    return df
            except Exception:
                pass  # corrupt cache — re-fetch

    # ── Fetch from yfinance ───────────────────────────────────────────────────
    raw = yf.download(symbols, period=period, progress=False, auto_adjust=True)

    if raw is None or raw.empty:
        raise ValueError(f"yfinance returned empty data for {symbols}")

    # Handle MultiIndex columns (Close / Adj Close level)
    if isinstance(raw.columns, pd.MultiIndex):
        if "Close" in raw.columns.get_level_values(0):
            prices = raw["Close"]
        else:
            prices = raw.iloc[:, raw.columns.get_level_values(0) == raw.columns.get_level_values(0)[0]]
    else:
        prices = raw

    if isinstance(prices, pd.Series):
        prices = prices.to_frame(name=symbols[0])

    prices = prices.ffill().dropna(how="all")

    # Warn about any missing tickers but don't fail — engine will intersect
    missing = [t for t in symbols if t not in prices.columns]
    if missing:
        import warnings
        warnings.warn(f"io_python: tickers not returned by yfinance: {missing}")

    # ── Persist cache ─────────────────────────────────────────────────────────
    if cache_path:
        import os
        os.makedirs(os.path.dirname(os.path.abspath(cache_path)), exist_ok=True)
        try:
            prices.to_pickle(cache_path)
        except Exception:
            pass

    return prices
