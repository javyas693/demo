from datetime import date
from typing import Optional
import pandas as pd
import yfinance as yf
from ai_advisory.db.database import get_db
from ai_advisory.orchestration.trace_logger import trace_log


def get_all_proxy_mappings() -> dict:
    """Returns {ticker: (proxy_ticker, beta, inception_date)} from DB."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT ticker, proxy_ticker, beta, inception_date FROM proxy_map"
        ).fetchall()
    return {
        r["ticker"]: (r["proxy_ticker"], float(r["beta"]), r["inception_date"])
        for r in rows
    }


def is_price_cache_fresh(tickers: list) -> bool:
    """
    Returns True if ALL tickers have today's date in price_cache.
    Morning-refresh gate — if any ticker is stale, full download runs.
    """
    today = date.today().isoformat()
    with get_db() as conn:
        for ticker in tickers:
            row = conn.execute(
                "SELECT 1 FROM price_cache WHERE ticker=? AND date=?",
                (ticker, today)
            ).fetchone()
            if not row:
                trace_log(f"[PRICE_CACHE] Stale or missing: {ticker} for {today}")
                return False
    return True


def load_prices_from_cache(tickers: list) -> dict:
    """
    Returns {ticker: {date_str: close}} for all requested tickers.
    Includes proxy-backfilled rows transparently.
    """
    result = {}
    with get_db() as conn:
        for ticker in tickers:
            rows = conn.execute(
                "SELECT date, close FROM price_cache WHERE ticker=? ORDER BY date ASC",
                (ticker,)
            ).fetchall()
            result[ticker] = {r["date"]: r["close"] for r in rows}
    return result


def write_prices_to_cache(
    prices_by_ticker: dict,
    is_proxy: bool = False,
    proxy_for: Optional[str] = None,
) -> None:
    """
    Bulk upsert prices into price_cache.
    prices_by_ticker: {ticker: {date_str: close}}
    """
    rows = []
    for ticker, date_prices in prices_by_ticker.items():
        for date_str, close in date_prices.items():
            rows.append((ticker, date_str, float(close), int(is_proxy), proxy_for))

    with get_db() as conn:
        conn.executemany("""
            INSERT INTO price_cache (ticker, date, close, is_proxy, proxy_for)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(ticker, date) DO UPDATE SET
                close     = excluded.close,
                is_proxy  = excluded.is_proxy,
                proxy_for = excluded.proxy_for
        """, rows)
    trace_log(f"[PRICE_CACHE] Wrote {len(rows)} rows (is_proxy={is_proxy})")


def apply_proxy_backfill(prices_by_ticker: dict) -> dict:
    """
    For each ticker in proxy_map, backfill dates before inception_date
    using proxy_ticker prices * beta. Writes backfilled rows to price_cache.
    Returns updated prices_by_ticker with backfill applied.
    """
    proxy_mappings = get_all_proxy_mappings()
    result = dict(prices_by_ticker)

    for ticker, (proxy_ticker, beta, inception_date_str) in proxy_mappings.items():
        if ticker not in result or proxy_ticker not in result:
            continue

        inception      = pd.Timestamp(inception_date_str)
        target_prices  = dict(result[ticker])
        proxy_prices   = result[proxy_ticker]

        backfilled = {}
        for date_str, proxy_close in proxy_prices.items():
            if pd.Timestamp(date_str) < inception and date_str not in target_prices:
                backfilled[date_str] = round(proxy_close * beta, 6)

        if backfilled:
            target_prices.update(backfilled)
            result[ticker] = target_prices
            write_prices_to_cache(
                {ticker: backfilled},
                is_proxy=True,
                proxy_for=proxy_ticker,
            )
            trace_log(
                f"[PROXY] Backfilled {len(backfilled)} rows for {ticker} "
                f"from {proxy_ticker} (beta={beta})"
            )

    return result


def load_all_prices(symbols: list) -> dict[str, pd.Series]:
    """
    Main entry point for time_simulator. Implements the full hierarchy:
        1. price_cache DB (if fresh for all symbols)
        2. yfinance download → write to cache → proxy backfill

    Returns {ticker: pd.Series} with a daily DatetimeIndex.
    Raises ValueError if any symbol has no data after all fallbacks.
    """
    # ── 1. Morning-refresh gate ───────────────────────────────────────
    if is_price_cache_fresh(symbols):
        trace_log("[PRICE] Cache fresh — loading all symbols from DB.")
        cached = load_prices_from_cache(symbols)
        return _cache_dict_to_series(cached, symbols)

    # ── 2. Download from yfinance ─────────────────────────────────────
    trace_log(f"[PRICE] Cache stale — downloading {len(symbols)} symbols from yfinance.")
    try:
        df = yf.download(symbols, period="max", progress=False, auto_adjust=True)
    except Exception as e:
        trace_log(f"[PRICE] yfinance download failed: {e}. Falling back to DB cache.")
        cached = load_prices_from_cache(symbols)
        if cached:
            return _cache_dict_to_series(cached, symbols)
        raise ValueError(f"yfinance failed and DB cache empty for symbols: {symbols}") from e

    if df is None or df.empty:
        raise ValueError(f"yfinance returned empty dataframe for symbols: {symbols}")

    # ── 3. Extract close prices ───────────────────────────────────────
    if isinstance(df.columns, pd.MultiIndex):
        close_col = "Close" if "Close" in df.columns.get_level_values(0) else df.columns.get_level_values(0)[0]
        df_close = df[close_col]
    else:
        df_close = df[["Close"]] if "Close" in df.columns else df

    if isinstance(df_close, pd.Series):
        df_close = df_close.to_frame(name=symbols[0])

    df_close = df_close.ffill()

    # ── 4. Write raw prices to cache ──────────────────────────────────
    prices_by_ticker: dict = {}
    for sym in symbols:
        if sym in df_close.columns:
            series = df_close[sym].dropna()
            prices_by_ticker[sym] = {
                d.strftime("%Y-%m-%d"): float(v)
                for d, v in series.items()
            }

    write_prices_to_cache(prices_by_ticker)

    # ── 5. Proxy backfill for short-history ETFs ──────────────────────
    prices_by_ticker = apply_proxy_backfill(prices_by_ticker)

    return _cache_dict_to_series(prices_by_ticker, symbols)


def _cache_dict_to_series(
    prices_by_ticker: dict,
    symbols: list,
) -> dict[str, pd.Series]:
    """
    Convert {ticker: {date_str: close}} → {ticker: pd.Series(DatetimeIndex)}.
    Raises ValueError for any symbol with no data.
    """
    result = {}
    for sym in symbols:
        data = prices_by_ticker.get(sym, {})
        if not data:
            raise ValueError(f"System failed: data not available for symbol {sym}")
        series = pd.Series(data)
        series.index = pd.to_datetime(series.index)
        series = series.sort_index()
        result[sym] = series
    return result
