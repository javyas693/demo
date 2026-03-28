from pathlib import Path
from ai_advisory.db.price_store import (
    is_price_cache_fresh,
    load_prices_from_cache,
    write_prices_to_cache,
    apply_proxy_backfill,
)
from ai_advisory.orchestration.trace_logger import trace_log

# Keep CSV as fallback write for team compatibility
# Fix (file is already in data/):
DATA_DIR = Path(__file__).parent
SPY_CSV  = DATA_DIR / "spy_prices.csv"


def load_spy_prices() -> dict:
    """
    Returns {date_str: close} for SPY.
    Pulls from price_cache DB. Downloads full history if today's date is missing.
    """
    if is_price_cache_fresh(["SPY"]):
        prices = load_prices_from_cache(["SPY"])
        return prices.get("SPY", {})

    return _download_and_cache(["SPY"]).get("SPY", {})


def load_all_prices(tickers: list) -> dict:
    """
    Returns {ticker: {date_str: close}} for all requested tickers.
    Checks DB freshness first — downloads only if stale (morning refresh).
    Proxy backfill applied automatically for known short-history tickers.
    """
    if is_price_cache_fresh(tickers):
        trace_log(f"[PRICE_CACHE] All {len(tickers)} tickers fresh — loading from DB")
        return load_prices_from_cache(tickers)

    trace_log(f"[PRICE_CACHE] Stale — downloading {len(tickers)} tickers via yfinance")
    return _download_and_cache(tickers)


def _download_and_cache(tickers: list) -> dict:
    import yfinance as yf
    import pandas as pd

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    symbols  = tickers if len(tickers) > 1 else tickers[0]
    hist     = yf.download(symbols, period="max", progress=False)

    if hist is None or hist.empty:
        raise ValueError(f"yfinance returned empty data for {tickers}")

    # Normalize MultiIndex or flat columns
    if isinstance(hist.columns, pd.MultiIndex):
        price_df = (
            hist["Adj Close"]
            if "Adj Close" in hist.columns.levels[0]
            else hist["Close"]
        )
    else:
        col = "Adj Close" if "Adj Close" in hist.columns else "Close"
        price_df = hist[[col]]
        if len(tickers) == 1:
            price_df = price_df.rename(columns={col: tickers[0]})

    price_df       = price_df.ffill()
    price_df.index = (
        pd.to_datetime(price_df.index).tz_localize(None).strftime("%Y-%m-%d")
    )

    prices_by_ticker = {}
    for ticker in tickers:
        if ticker in price_df.columns:
            prices_by_ticker[ticker] = price_df[ticker].dropna().to_dict()

    # Write raw prices to DB
    write_prices_to_cache(prices_by_ticker)

    # Apply proxy backfill for known short-history tickers (JEPQ, TLTW, SVOL)
    prices_by_ticker = apply_proxy_backfill(prices_by_ticker)

    # Write SPY CSV as team fallback (non-blocking)
    if "SPY" in prices_by_ticker:
        try:
            import pandas as pd
            spy_series = pd.Series(prices_by_ticker["SPY"], name="Close")
            spy_series.index.name = "Date"
            spy_series.to_csv(SPY_CSV, header=True)
        except Exception as e:
            trace_log(f"[SPY CSV] Fallback CSV write failed: {e}")

    return prices_by_ticker


def get_spy_price_on_or_before(spy_prices: dict, target_date: str) -> float:
    """Returns the SPY close on or before target_date. Finds nearest prior trading day."""
    sorted_dates = sorted(spy_prices.keys())
    candidates   = [d for d in sorted_dates if d <= target_date]
    if not candidates:
        return spy_prices[sorted_dates[0]]
    return spy_prices[candidates[-1]]
