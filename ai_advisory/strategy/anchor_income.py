import math
import logging
import numpy as np
import pandas as pd
import yfinance as yf
from dataclasses import dataclass
from typing import Any, Dict, Optional
from ai_advisory.orchestration.trace_logger import trace_log

@dataclass
class TickerSimInfo:
    ticker: str
    proxy_ticker: str
    beta: float
    targeted_yield: float
    inception_date: pd.Timestamp

class AnchorIncomeEngine:
    # Monthly yield rates for each income ETF (strategy engine owns this math)
    MONTHLY_YIELDS: Dict[str, float] = {
        "JEPQ": 0.0100,   # ~12% annual
        "TLTW": 0.0150,   # ~18% annual
        "SVOL": 0.0080,   # ~9.6% annual
    }

    def __init__(
        self,
        start_date: str,
        end_date: str,
        initial_capital: float = 1_000_000.0,
        reinvest_pct: float = 0.0
    ):
        self.start_date = pd.to_datetime(start_date)
        self.end_date = pd.to_datetime(end_date)
        self.initial_capital = initial_capital
        self.reinvest_pct = reinvest_pct
        self.events = []

        self.tickers_info = {
            "JEPQ": TickerSimInfo("JEPQ", "QQQ", 0.75, 0.105, pd.to_datetime("2022-05-03")),
            "TLTW": TickerSimInfo("TLTW", "TLT", 0.60, 0.120, pd.to_datetime("2022-08-18")),
            "SVOL": TickerSimInfo("SVOL", "SPY", 0.81, 0.160, pd.to_datetime("2021-05-12")),
        }

        self.parking_lot_target_weights = {
            "JEPQ": 0.70,
            "TLTW": 0.20,
            "SVOL": 0.10
        }

    @classmethod
    def compute_monthly_distributions(
        cls,
        income_holdings: Dict[str, float],
        prices: Dict[str, float],
    ) -> float:
        """
        Computes monthly income distributions from current holdings.

        The income engine owns this yield math so the orchestrator and
        time_simulator never have to hard-code yield rates.

        All distributions are assumed reinvested (added to sleeve value, not cash).
        Returns total distributions in dollars.
        """
        return sum(
            float(income_holdings.get(t, 0)) * prices.get(t, 0.0) * y
            for t, y in cls.MONTHLY_YIELDS.items()
        )

    def _download_data(self) -> pd.DataFrame:
        all_tickers = ["JEPQ", "QQQ", "TLTW", "TLT", "SVOL", "SPY"]
        df_raw = yf.download(all_tickers, start=self.start_date, end=self.end_date, progress=False)
        
        if isinstance(df_raw.columns, pd.MultiIndex):
            if "Adj Close" in df_raw.columns.levels[0]:
                df_prices = df_raw["Adj Close"]
            else:
                df_prices = df_raw["Close"]
        else:
            df_prices = df_raw

        if isinstance(df_prices, pd.Series):
            df_prices = df_prices.to_frame()

        return df_prices.dropna(how="all").ffill()
        
    def _prepare_daily_returns(self, df_prices: pd.DataFrame) -> pd.DataFrame:
        df_returns = df_prices.pct_change()
        
        for tgt, info in self.tickers_info.items():
            if tgt not in df_returns.columns or info.proxy_ticker not in df_returns.columns:
                continue
                
            mask_backfill = df_returns.index < info.inception_date
            proxy_ret = df_returns.loc[mask_backfill, info.proxy_ticker]
            df_returns.loc[mask_backfill, tgt] = proxy_ret * info.beta
            df_returns[tgt] = df_returns[tgt].fillna(0.0)
 
        if "QQQ" in df_returns.columns:
            df_returns["QQQ"] = df_returns["QQQ"].fillna(0.0)
            
        return df_returns

    def _calc_qqq_drawdown(self, df_prices: pd.DataFrame) -> pd.Series:
        qqq_prices = df_prices["QQQ"]
        running_max = qqq_prices.cummax()
        drawdown = (qqq_prices - running_max) / running_max
        return drawdown

    def simulate(self) -> Dict[str, Any]:
        df_prices = self._download_data()
        df_returns = self._prepare_daily_returns(df_prices)
        qqq_drawdown = self._calc_qqq_drawdown(df_prices)
        
        # Call the Pure Function
        result = run_simulation(
            start_date=self.start_date,
            end_date=self.end_date,
            initial_capital=self.initial_capital,
            reinvest_pct=self.reinvest_pct,
            tickers_info=self.tickers_info,
            target_weights=self.parking_lot_target_weights,
            df_returns=df_returns,
            qqq_drawdown=qqq_drawdown,
            monthly_yields=AnchorIncomeEngine.MONTHLY_YIELDS,
        )
        
        self.events = result["events"]
        return result

def run_simulation(
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    initial_capital: float,
    reinvest_pct: float,
    tickers_info: Dict[str, TickerSimInfo],
    target_weights: Dict[str, float],
    df_returns: pd.DataFrame,
    qqq_drawdown: pd.Series,
    monthly_yields: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Pure Function for running the Anchor Income simulation.
    All simulation variables are declared inside function scope.
    Constraint: Do NOT read from or write to any global state or persistent storage.
    """
    if monthly_yields is None:
        monthly_yields = {'JEPQ': 0.0100, 'TLTW': 0.0150, 'SVOL': 0.0080}

    # 2. THE "CLEAN SLATE" INITIALIZATION
    History_Log = []
    History_Log.append({
        "date": start_date.strftime("%Y-%m-%d"),
        "event_type": "Initialize",
        "description": f"--- SIMULATION INITIALIZED: ${initial_capital:,.2f} ---",
        "portfolio_value": initial_capital,
        "cash_balance": 0.0
    })

    # 1. SCOPE ISOLATION: Simulation variables declared inside
    # HARD RESET: Force starting capital to override any snapshots
    val_jepq: float = initial_capital * 0.70
    val_tltw: float = initial_capital * 0.20
    val_svol: float = initial_capital * 0.10
    val_qqq: float = 0.0
    val_cash: float = 0.0
    Total_Withdrawn: float = 0.0

    Peak_Value: float = initial_capital
    Current_Date = start_date
    
    num_days = len(df_returns)
    dates = df_returns.index
    
    portfolio_value_series = np.zeros(num_days)
    pure_qqq_value_series = np.zeros(num_days)
    cumulative_income_series = np.zeros(num_days)
    withdrawn_income_series = np.zeros(num_days)
    
    current_cumulative_income_val: float = 0.0
    pure_qqq_capital: float = initial_capital
    
    portfolio_value_series[0] = initial_capital
    pure_qqq_value_series[0] = initial_capital
    
    current_qqq_swap_target = 0.0
    
    qqq_returns = df_returns["QQQ"].values
    ret_jepq = df_returns["JEPQ"].values
    ret_tltw = df_returns["TLTW"].values
    ret_svol = df_returns["SVOL"].values
    
    qqq_peak = initial_capital
    portfolio_max_dd = 0.0
    qqq_max_dd = 0.0

    for i in range(1, num_days):
        date_str = dates[i].strftime("%Y-%m-%d")
        Current_Date = dates[i]
        
        # --- 1. Apply Market Returns ---
        val_jepq *= (1.0 + ret_jepq[i])
        val_tltw *= (1.0 + ret_tltw[i])
        val_svol *= (1.0 + ret_svol[i])
        val_qqq *= (1.0 + qqq_returns[i])
        
        pure_qqq_capital *= (1.0 + qqq_returns[i])
        pure_qqq_value_series[i] = pure_qqq_capital
        
        # --- QQQ Drawdown Tracking ---
        qqq_peak = max(qqq_peak, pure_qqq_capital)
        current_qqq_dip = (pure_qqq_capital - qqq_peak) / qqq_peak if qqq_peak > 0 else 0
        qqq_max_dd = min(qqq_max_dd, current_qqq_dip)

        # 4. PORTFOLIO IDENTITY RE-VALIDATION: Strictly derived sum at every step
        current_capital = val_jepq + val_tltw + val_svol + val_qqq + val_cash
        
        # --- 2. Yield Calculation (Monthly) ---
        if i % 30 == 0:
            y_jepq = val_jepq * monthly_yields['JEPQ']
            y_tltw = val_tltw * monthly_yields['TLTW']
            y_svol = val_svol * monthly_yields['SVOL']
            
            cash_income = y_jepq + y_tltw + y_svol
            monthly_inc = cash_income  # plug into existing behavior
            
            sleeve_value = val_jepq + val_tltw + val_svol
            monthly_yield = cash_income / sleeve_value if sleeve_value > 0 else 0.0
            annualized = monthly_yield * 12.0
        
            if monthly_inc > 0:
                current_cumulative_income_val += monthly_inc
                
                reinvest_amt = monthly_inc * (reinvest_pct / 100.0)
                withdrawn_amt = monthly_inc - reinvest_amt
                
                val_cash += reinvest_amt
                Total_Withdrawn += withdrawn_amt
                
                # RE-VALIDATE: Recalculate after cash adjustment
                current_capital = val_jepq + val_tltw + val_svol + val_qqq + val_cash
                
                History_Log.append({
                    "date": date_str,
                    "event_type": "Income",
                    "description": f"Dividend Received: ${monthly_inc:,.2f} (Reinvested: ${reinvest_amt:,.2f}, Withdrawn: ${withdrawn_amt:,.2f}) [JEPQ: ${val_jepq:,.0f}, TLTW: ${val_tltw:,.0f}, SVOL: ${val_svol:,.0f}, QQQ: ${val_qqq:,.0f}, Cash: ${val_cash:,.0f}]",
                    "portfolio_value": current_capital,
                    "cash_balance": val_cash,
                    "withdrawn": withdrawn_amt
                })

        # --- 3. Tactical Swap Logic ---
        dd = qqq_drawdown.iloc[i]
        target_swap = 0.0
        if dd <= -0.30:
            target_swap = 0.30
        elif dd <= -0.20:
            target_swap = 0.20
        elif dd <= -0.10:
            target_swap = 0.10
            
        if dd >= 0.0: # ATH reached
            target_swap = 0.0

        # --- 3a. Swap Trigger (Buy QQQ) ---
        if target_swap > current_qqq_swap_target:
            additional_qqq_frac = target_swap - current_qqq_swap_target
            qqq_needed = additional_qqq_frac * current_capital

            step_num = int(target_swap * 10)
            History_Log.append({
                "date": date_str,
                "event_type": "Trigger",
                "description": f"Tactical Step {step_num} Activated: {dd*100:.0f}% QQQ Drawdown detected. [JEPQ: ${val_jepq:,.0f}, TLTW: ${val_tltw:,.0f}, SVOL: ${val_svol:,.0f}, QQQ: ${val_qqq:,.0f}, Cash: ${val_cash:,.0f}]",
                "portfolio_value": current_capital,
                "cash_balance": val_cash
            })

            sources_str = []
            
            # Priority 1: Cash
            take_cash = min(val_cash, qqq_needed)
            val_cash -= take_cash
            qqq_needed -= take_cash
            if take_cash > 0: sources_str.append(f"${take_cash:,.0f} Cash")
            
            # Priority 2: TLTW (Bonds)
            if qqq_needed > 0:
                take_tltw = min(val_tltw, qqq_needed)
                val_tltw -= take_tltw
                qqq_needed -= take_tltw
                if take_tltw > 0: sources_str.append(f"${take_tltw:,.0f} TLTW")
            
            # Priority 3: JEPQ & SVOL (Proportional)
            if qqq_needed > 0:
                total_jepq_svol = val_jepq + val_svol
                if total_jepq_svol > 0:
                    jepq_ratio = val_jepq / total_jepq_svol
                    svol_ratio = val_svol / total_jepq_svol
                    
                    take_jepq = min(val_jepq, qqq_needed * jepq_ratio)
                    take_svol = min(val_svol, qqq_needed * svol_ratio)
                    
                    val_jepq -= take_jepq
                    val_svol -= take_svol
                    qqq_needed -= (take_jepq + take_svol)
                    
                    if take_jepq > 0: sources_str.append(f"${take_jepq:,.0f} JEPQ")
                    if take_svol > 0: sources_str.append(f"${take_svol:,.0f} SVOL")
            
            # Add funded amount to QQQ
            added_qqq = (additional_qqq_frac * current_capital) - qqq_needed
            val_qqq += added_qqq
            current_qqq_swap_target = target_swap
            
            # RE-VALIDATE: Recalculate after trades
            current_capital = val_jepq + val_tltw + val_svol + val_qqq + val_cash
            
            if added_qqq > 0:
                sold_desc = ", ".join(sources_str)
                History_Log.append({
                    "date": date_str,
                    "event_type": "Trade",
                    "description": f"Sold {sold_desc}. Purchased ${added_qqq:,.0f} QQQ. [JEPQ: ${val_jepq:,.0f}, TLTW: ${val_tltw:,.0f}, SVOL: ${val_svol:,.0f}, QQQ: ${val_qqq:,.0f}, Cash: ${val_cash:,.0f}]",
                    "portfolio_value": current_capital,
                    "cash_balance": val_cash
                })
                
        # --- 3b. Reset (Snap-Back to Base Camp) ---
        elif target_swap == 0.0 and current_qqq_swap_target > 0:
            pre_reset_capital = val_jepq + val_tltw + val_svol + val_qqq + val_cash
            
            val_jepq = pre_reset_capital * target_weights["JEPQ"]
            val_tltw = pre_reset_capital * target_weights["TLTW"]
            val_svol = pre_reset_capital * target_weights["SVOL"]
            val_qqq = 0.0
            val_cash = 0.0
            current_qqq_swap_target = 0.0
            
            # RE-VALIDATE
            current_capital = val_jepq + val_tltw + val_svol + val_qqq + val_cash
                
            History_Log.append({
                "date": date_str,
                "event_type": "Reset",
                "description": f"QQQ ATH reached. Rebalancing to Parking Lot. [JEPQ: ${val_jepq:,.0f}, TLTW: ${val_tltw:,.0f}, SVOL: ${val_svol:,.0f}, QQQ: ${val_qqq:,.0f}, Cash: ${val_cash:,.0f}]",
                "portfolio_value": current_capital,
                "cash_balance": val_cash
            })

        # FINAL RE-VALIDATION AT EOD
        final_cap = val_jepq + val_tltw + val_svol + val_qqq + val_cash
        portfolio_value_series[i] = final_cap
        
        # --- Portfolio MDD Tracking ---
        Peak_Value = max(Peak_Value, final_cap)
        current_dip = (final_cap - Peak_Value) / Peak_Value if Peak_Value > 0 else 0
        portfolio_max_dd = min(portfolio_max_dd, current_dip)

        cumulative_income_series[i] = current_cumulative_income_val
        withdrawn_income_series[i] = Total_Withdrawn
    _sleeve_vals = {'JEPQ': val_jepq, 'TLTW': val_tltw, 'SVOL': val_svol}
    cash_income_log = sum(
        _sleeve_vals.get(ticker, 0) * yield_rate
        for ticker, yield_rate in monthly_yields.items()
        if ticker in _sleeve_vals
    )
    sleeve_value_log = sum(
        _sleeve_vals.get(t, 0)
        for t in _sleeve_vals
        if t in _sleeve_vals
    )
    monthly_yield_log = cash_income_log / sleeve_value_log if sleeve_value_log > 0 else 0
    annualized_log = monthly_yield_log * 12
    trace_log(f"[INCOME YIELD] Cash Income: {cash_income_log:.2f} | Sleeve Value: {sleeve_value_log:.2f} | Monthly Yield: {monthly_yield_log:.2%} | Annualized: {annualized_log:.2%}")

    df_out = pd.DataFrame({
        "Date": dates.strftime("%Y-%m-%d"),
        "Strategy_Value": portfolio_value_series,
        "Pure_QQQ_Value": pure_qqq_value_series,
        "Cumulative_Income": cumulative_income_series,
        "Total_Withdrawn": withdrawn_income_series,
        "QQQ_Drawdown": qqq_drawdown.values
    })
    
    total_alpha = (portfolio_value_series[-1] + Total_Withdrawn) - pure_qqq_value_series[-1]
    
    return {
        "summary": {
            "initial_value": initial_capital,
            "final_strategy_value": portfolio_value_series[-1],
            "final_qqq_value": pure_qqq_value_series[-1],
            "total_strategy_return_pct": (((portfolio_value_series[-1] + Total_Withdrawn) / initial_capital) - 1.0) * 100,
            "total_qqq_return_pct": ((pure_qqq_value_series[-1] / initial_capital) - 1.0) * 100,
            "final_cumulative_income": current_cumulative_income_val,
            "total_withdrawn_income": Total_Withdrawn,
            "total_alpha": total_alpha,
            "portfolio_max_drawdown": portfolio_max_dd * 100,
            "qqq_max_drawdown": qqq_max_dd * 100
        },
        "time_series": df_out.to_dict(orient="records"),
        "events": History_Log
    }
