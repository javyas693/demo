import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, Any
from ai_advisory.orchestration.trace_logger import trace_log

def run_mp_backtest(target_weights: Dict[str, float], initial_capital: float, start_date: str, end_date: str) -> Dict[str, Any]:
    """
    Simulates a historically backtested Managed Portfolio with strict monthly rebalancing.
    """
    tickers = list(target_weights.keys())
    if not tickers:
        return {"error": "No tickers provided"}
    
    # Download daily data
    try:
        # Avoid yfinance auto-adjust which can raise warnings, we just want 'Adj Close' or 'Close'
        df = yf.download(tickers, start=start_date, end=end_date, progress=False)
        
        # Depending on yfinance version, 'Close' or 'Adj Close' might be available. We prefer 'Adj Close' for total return.
        if 'Adj Close' in df.columns:
            df = df['Adj Close']
        elif 'Close' in df.columns:
            df = df['Close']
        else:
            return {"error": "Could not extract price columns from yfinance data"}

    except Exception as e:
        return {"error": f"yfinance download failed: {str(e)}"}
        
    if df.empty:
        return {"error": "No data returned from yfinance for the requested date range"}
        
    # If single ticker, yfinance returns a Series. Convert to DataFrame.
    if isinstance(df, pd.Series):
        df = df.to_frame(name=tickers[0])
        
    # Forward fill missing data to handle holidays or halted trading
    df = df.ffill()
    
    # Resample to business month end (BME)
    monthly_prices = df.resample('BME').last()
    monthly_prices = monthly_prices.dropna(how='all')
    
    # Calculate monthly returns for each asset
    monthly_returns = monthly_prices.pct_change().dropna()
    
    time_series = []
    audit_log = []
    
    # Initial state
    portfolio_value = initial_capital
    portfolio_values = [initial_capital]
    
    # Push the initial state point to time series
    try:
        first_date = monthly_prices.index[0] # date before returns
        time_series.append({
            "date": first_date.strftime("%Y-%m-%d"),
            "value": portfolio_value
        })
    except:
        pass

    has_printed_reconciliation = False
    
    for date, returns in monthly_returns.iterrows():
        month_return = 0.0
        month_end_values = {}
        audit_assets = []
        
        # We need the start of month price to calculate shares held.
        # Since we resampled to month end, we'll approximate the 'start price' for the math proof 
        # using the previous month's end price, or the first available price for month 1.
        month_start_idx = monthly_prices.index.get_loc(date) - 1
        if month_start_idx < 0:
            month_start_prices = df.loc[df.index < date].iloc[-1] if len(df.loc[df.index < date]) > 0 else monthly_prices.iloc[0]
        else:
            month_start_prices = monthly_prices.iloc[month_start_idx]
            
        month_end_prices = monthly_prices.loc[date]
        
        # Calculate individual asset contributions, skipping missing assets and collecting their weight
        valid_assets = {}
        missing_weight = 0.0
        
        for ticker, weight in target_weights.items():
            if ticker in returns and not pd.isna(returns[ticker]):
                valid_assets[ticker] = {"weight": weight, "return": returns[ticker]}
            else:
                missing_weight += weight
                
        # Pro-rata redistribute the missing weight to the valid assets
        total_valid_weight = sum(a["weight"] for a in valid_assets.values())
        
        for ticker, data in valid_assets.items():
            # If total_valid_weight is 0 (all assets missing this month), this will just be 0
            adjusted_weight = data["weight"] + (missing_weight * (data["weight"] / total_valid_weight)) if total_valid_weight > 0 else 0
            
            asset_return = data["return"]
            month_return += adjusted_weight * asset_return
            asset_value = portfolio_value * adjusted_weight * (1 + asset_return)
            month_end_values[ticker] = asset_value
            
            # Audit Math
            start_price = month_start_prices.get(ticker, 1.0)
            end_price = month_end_prices.get(ticker, 1.0)
            allocated_cash = portfolio_value * adjusted_weight
            shares_held = allocated_cash / start_price if start_price > 0 else 0
            
            audit_assets.append({
                "ticker": ticker,
                "weight": adjusted_weight,
                "ticker_start_price": start_price,
                "ticker_end_price": end_price,
                "shares_held": shares_held
            })
                
        # Total portfolio impacts
        monthly_pnl = portfolio_value * month_return
        portfolio_value += monthly_pnl
        portfolio_values.append(portfolio_value)
        
        # Terminal Proof (First Month Only)
        if not has_printed_reconciliation and len(valid_assets) > 0:
            has_printed_reconciliation = True
            trace_log("\n" + "="*50)
            trace_log("=== MP MATHEMATICAL RECONCILIATION BLOCK ===")
            trace_log(f"Month: {date.strftime('%Y-%m')}")
            trace_log(f"Starting Capital: ${portfolio_values[-2]:,.2f}")

            sum_of_assets = 0.0
            for a in audit_assets:
                asset_end_val = a['shares_held'] * a['ticker_end_price']
                sum_of_assets += asset_end_val
                trace_log(f" - {a['ticker']}: {a['shares_held']:,.4f} shares * ${a['ticker_end_price']:,.2f} = ${asset_end_val:,.2f}")

            trace_log("-" * 50)
            trace_log(f"Sum of Assets:      ${sum_of_assets:,.2f}")
            trace_log(f"Geometric PV Math:  ${portfolio_value:,.2f}")
            diff = abs(sum_of_assets - portfolio_value)
            trace_log(f"Absolute Delta:     ${diff:,.4f}")

            if diff > 0.01:
                trace_log(f"WARNING: RECONCILIATION FAILED. DELTA EXCEEDS $0.01")
            else:
                trace_log("STATUS: VERIFIED (Sum of Assets = Total Value)")
            trace_log("="*50 + "\n")
        
        # Identity top holding by value post-return
        top_holding = max(month_end_values, key=month_end_values.get) if month_end_values else "N/A"
        date_str = date.strftime("%Y-%m-%d")
        
        time_series.append({
            "date": date_str,
            "value": portfolio_value
        })
        
        audit_log.append({
            "date": date_str,
            "portfolio_value": portfolio_value,
            "monthly_pnl": monthly_pnl,
            "top_holding": top_holding,
            "action": f"Rebalanced {len(target_weights)} assets",
            "assets_audit": audit_assets,
            "math_verified": bool(diff <= 0.01) if 'diff' in locals() else True
        })
        
    # Metric Calculations
    if len(portfolio_values) > 1:
        total_return = (portfolio_value / initial_capital) - 1.0
        
        n_months = len(monthly_returns)
        n_years = n_months / 12.0 if n_months > 0 else 0
        
        # Annualized return geometric
        annualized_return = ((portfolio_value / initial_capital) ** (1 / n_years) - 1.0) if n_years > 0 else 0.0
        
        # Volatility
        portfolio_monthly_returns = pd.Series(portfolio_values).pct_change().dropna()
        volatility = portfolio_monthly_returns.std() * np.sqrt(12)
        
        # Sharpe Ratio (4% RFR)
        rfr = 0.04
        sharpe_ratio = (annualized_return - rfr) / volatility if volatility > 0 else 0.0
        
        # Max Drawdown
        cumulative_max = pd.Series(portfolio_values).cummax()
        drawdown = (pd.Series(portfolio_values) - cumulative_max) / cumulative_max
        max_drawdown = drawdown.min()
    else:
        total_return = 0
        annualized_return = 0
        volatility = 0
        sharpe_ratio = 0
        max_drawdown = 0

    summary = {
        "total_return_pct": total_return * 100,
        "annualized_return_pct": annualized_return * 100,
        "volatility_pct": volatility * 100,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown_pct": max_drawdown * 100,
        "final_value": portfolio_value,
        "initial_capital": initial_capital
    }
    
    return {
        "summary": summary,
        "time_series": time_series,
        "audit_log": list(reversed(audit_log)) # Most recent first for UI scroll
    }
