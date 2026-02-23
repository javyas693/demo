import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, Any


class DataFetchError(Exception):
    """Custom exception for data fetch failures."""
    pass


def run_real_price_simulation(ticker="AAPL", start="2020-01-01", end="2023-01-01") -> Dict[str, Any]:
    """
    Fetch historical price data and compute return metrics.
    
    Args:
        ticker: Stock ticker symbol
        start: Start date in YYYY-MM-DD format
        end: End date in YYYY-MM-DD format
        
    Returns:
        Dictionary containing ticker, prices, return metrics, and price history
        
    Raises:
        DataFetchError: When data cannot be fetched or is invalid
    """
    try:
        # Download with progress disabled to avoid cluttering output
        df = yf.download(ticker, start=start, end=end, progress=False)
        
        # Check if download failed (empty dataframe)
        if df is None or df.empty:
            raise DataFetchError(
                f"No data returned for ticker '{ticker}'. "
                f"Please verify the ticker symbol and date range."
            )
        
        # yfinance sometimes returns a Series in edge cases
        if isinstance(df, pd.Series):
            df = df.to_frame()
        
        # Check for required columns
        if "Adj Close" in df.columns:
            col = "Adj Close"
        elif "Close" in df.columns:
            col = "Close"
        else:
            available_cols = ", ".join(df.columns.tolist()) if not df.empty else "none"
            raise DataFetchError(
                f"Required price columns not found for ticker '{ticker}'. "
                f"Available columns: {available_cols}"
            )
        
        # Extract price series
        s = df[col].copy()
        
        # Check if we have enough data
        if len(s) < 2:
            raise DataFetchError(
                f"Insufficient data for ticker '{ticker}'. "
                f"Need at least 2 data points, got {len(s)}."
            )
        
        # Drop any NaN values
        s = s.dropna()
        
        if len(s) < 2:
            raise DataFetchError(
                f"Insufficient valid data for ticker '{ticker}' after removing missing values."
            )
        
        # Ensure scalar floats (avoid numpy scalar types that may cause issues)
        start_price = float(s.iloc[0])
        end_price = float(s.iloc[-1])
        
        # Calculate total return
        total_return = (end_price / start_price) - 1.0
        
        # Prepare price history for charting
        price_history = s.reset_index()
        price_history.columns = ['Date', 'Price']
        
        return {
            "ticker": ticker,
            "start_price": start_price,
            "end_price": end_price,
            "total_return_pct": round(total_return * 100, 2),
            "price_history": price_history,
            "data_points": len(s),
        }
        
    except DataFetchError:
        # Re-raise our custom errors
        raise
    except Exception as e:
        # Catch any other unexpected errors
        raise DataFetchError(
            f"Unexpected error fetching data for ticker '{ticker}': {str(e)}"
        ) from e
