"""
Concentrated Position Unwind Strategy Module (Streamlit MVP)

Implements:
1) Buy-and-hold baseline
2) Covered call overlay strategy (v1: 20Δ / 30D, single option, EOD)
3) Deterministic early exits with strict priority:
    1) CLOSE_ASSIGNMENT_PREVENT (ITM + extrinsic <= threshold% of premium_open_per_share)
    2) CLOSE_PROFIT (profit >= profit_capture_pct of premium)
    3) CLOSE_STOP (loss >= stop_loss_multiple * premium)
    4) EXPIRE (dte <= 0)
4) Optional scheduled position reductions (quarterly %, threshold)
5) NEW: On option loss, optionally reduce shares ONLY if price is up by X% vs cost basis,
        and do so in a tax-neutral way under a single-lot basis.

Key accounting discipline (v1):
- Premium is added at OPEN (cash inflow)
- Cost-to-close is subtracted at CLOSE/EXPIRE (cash outflow)
- Option PnL is tracked separately as (premium_open_total - close_cost_total)

Taxes / TLH (MVP simplification):
- We do NOT model the $3,000 cap or carryforward mechanics.
- We track TLH as dollars in `cumulative_tlh`.
- `cumulative_taxes` is treated as estimated tax liability from realized gains:
    - Option profits taxed at short_term_tax_rate
    - Stock gains taxed at long_term_tax_rate
  (Option losses do not create immediate "negative taxes" in this MVP.)

Simplified assumptions:
- European options (for pricing approximation only)
- Option pricing uses Black-Scholes approximation
- No transaction costs, dividends, or vol regimes
- Uses yfinance for historical prices
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from math import floor
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
import yfinance as yf
from scipy.stats import norm
import logging

logger = logging.getLogger(__name__)

from backend.engine.strategy_runner import StrategyRunner
class SimState:
    def __init__(self, shares, cost_basis, cash, price):
        self.shares = shares
        self.cost_basis = cost_basis
        self.cash = cash
        self.price = price

class SimParams:
    def __init__(self, sell_shares, option_loss_available, tax_rate, trigger_percent):
        self.sell_shares = sell_shares
        self.shares_required = sell_shares  # Alias for strategies
        self.option_loss_available = option_loss_available
        self.tax_rate = tax_rate
        self.trigger_percent = trigger_percent
# -----------------------------
# Data structures
# -----------------------------

@dataclass
class OptionPos:
    open_date: pd.Timestamp
    dte_open: int
    strike: float
    covered_shares: int
    premium_open_per_share: float
    premium_open_total: float  # premium_open_per_share * covered_shares


@dataclass
class OverlayState:
    shares: float
    cost_basis: float
    cash: float
    open_option: Optional[OptionPos]

    cumulative_taxes: float
    cumulative_tlh: float
    realized_option_pnl: float
    realized_stock_gain: float

    last_close_date: Optional[pd.Timestamp]
    open_next_day: bool


# -----------------------------
# Engine
# -----------------------------

class StrategyUnwindEngine:
    """Engine for simulating concentrated position unwind strategies."""

    def __init__(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        initial_shares: int = 1000,
        risk_free_rate: float = 0.04,
        short_term_tax_rate: float = 0.37,
        long_term_tax_rate: float = 0.20,
    ):
        self.ticker = ticker
        self.start_date = start_date
        self.end_date = end_date
        self.initial_shares = int(initial_shares)
        self.risk_free_rate = float(risk_free_rate)
        self.short_term_tax_rate = float(short_term_tax_rate)
        self.long_term_tax_rate = float(long_term_tax_rate)

        self.price_data = self._load_price_data()

    # -----------------------------
    # Data load
    # -----------------------------

    def _load_price_data(self) -> pd.DataFrame:
        df = yf.download(
            self.ticker,
            start=self.start_date,
            end=self.end_date,
            progress=False,
        )

        if df is None or df.empty:
            raise ValueError(f"No data available for {self.ticker}")

        # Prefer adjusted close
        if "Adj Close" in df.columns:
            df = df[["Adj Close"]].copy()
            df.columns = ["Price"]
        elif "Close" in df.columns:
            df = df[["Close"]].copy()
            df.columns = ["Price"]
        else:
            raise ValueError("No price column found in data")

        df = df.dropna()
        if isinstance(df, pd.Series):
            df = df.to_frame(name="Price")

        df.index = pd.to_datetime(df.index)
        return df

    # -----------------------------
    # Option math
    # -----------------------------

    def black_scholes_call(self, S: float, K: float, T: float, r: float, sigma: float) -> float:
        """European call approximation."""
        if T <= 0:
            return max(S - K, 0.0)

        sigma = max(float(sigma), 1e-6)
        S = max(float(S), 1e-9)
        K = max(float(K), 1e-9)

        d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)

        call_price = S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
        return max(float(call_price), 0.0)

    def estimate_volatility(self, lookback_days: int = 60) -> float:
        """Simple deterministic vol estimate from log returns."""
        prices = self.price_data["Price"].values
        if len(prices) < 3:
            return 0.30

        window = prices[-min(lookback_days, len(prices)) :]
        rets = np.diff(np.log(window))
        if len(rets) < 2:
            return 0.30

        daily_vol = float(np.std(rets))
        annual_vol = daily_vol * math.sqrt(252)
        return max(annual_vol, 0.10)

    def strike_for_target_delta(
        self, S: float, T: float, r: float, sigma: float, target_delta: float = 0.20
    ) -> float:
        """
        Deterministic Black-Scholes strike solver from target call delta.
        For European call: delta = N(d1) => d1 = N^{-1}(delta)
        K = S * exp(-(d1*sigma*sqrt(T) - (r+0.5*sigma^2)*T))
        """
        T = max(float(T), 1e-9)
        sigma = max(float(sigma), 1e-6)
        td = min(max(float(target_delta), 1e-6), 1 - 1e-6)

        d1 = float(norm.ppf(td))
        exponent = -(d1 * sigma * math.sqrt(T) - (r + 0.5 * sigma * sigma) * T)
        K = float(S) * math.exp(exponent)
        return max(K, 0.01)

    # -----------------------------
    # Baseline
    # -----------------------------

    def run_baseline(self) -> Dict[str, Any]:
        df = self.price_data.copy()
        df["Shares"] = float(self.initial_shares)
        df["Stock_Value"] = df["Price"] * df["Shares"]

        initial_value = float(df["Stock_Value"].iloc[0])
        df["Stock_PnL"] = df["Stock_Value"] - initial_value
        df["Option_PnL"] = 0.0
        df["Total_PnL"] = df["Stock_PnL"]
        df["Cumulative_Taxes"] = 0.0
        df["Covered_Shares"] = 0.0
        df["Strike_Price"] = 0.0

        final_value = float(df["Stock_Value"].iloc[-1])
        total_return = (final_value / initial_value - 1.0) * 100.0

        summary = {
            "strategy": "Buy-and-Hold Baseline",
            "initial_shares": self.initial_shares,
            "final_shares": self.initial_shares,
            "initial_value": initial_value,
            "final_value": final_value,
            "total_return_pct": total_return,
            "stock_pnl": float(df["Stock_PnL"].iloc[-1]),
            "option_pnl": 0.0,
            "total_pnl": float(df["Total_PnL"].iloc[-1]),
            "cumulative_taxes": 0.0,
        }

        return {"time_series": df.reset_index(), "summary": summary}

    # -----------------------------
    # Overlay helpers
    # -----------------------------

    def _init_overlay_state(self, cost_basis: float) -> OverlayState:
        return OverlayState(
            shares=float(self.initial_shares),
            cost_basis=float(cost_basis),
            cash=0.0,
            open_option=None,
            cumulative_taxes=0.0,
            cumulative_tlh=0.0,
            realized_option_pnl=0.0,
            realized_stock_gain=0.0,
            last_close_date=None,
            open_next_day=True,
        )

    @staticmethod
    def _portfolio_value(state: OverlayState, price: float) -> float:
        return state.shares * price + state.cash

    @staticmethod
    def _evaluate_exit_reason(
        intrinsic: float,
        extrinsic: float,
        premium_open_per_share: float,
        option_mark: float,
        dte_remaining: int,
        profit_capture_pct: float,
        stop_loss_multiple: float,
        extrinsic_threshold_pct: float,
    ) -> str:
        """
        Strict v1 priority:
          1) CLOSE_ASSIGNMENT_PREVENT (ITM + extrinsic <= threshold% of premium_open_per_share)
          2) CLOSE_PROFIT (>= profit_capture_pct * premium)
          3) CLOSE_STOP (<= -stop_loss_multiple * premium)
          4) EXPIRE (dte <= 0)
        """
        premium_open_per_share = max(float(premium_open_per_share), 1e-9)
        profit_if_close_per_share = premium_open_per_share - float(option_mark)

        # 1) Assignment prevention
        if intrinsic > 0 and extrinsic <= float(extrinsic_threshold_pct) * premium_open_per_share:
            return "CLOSE_ASSIGNMENT_PREVENT"

        # 2) Profit capture
        if profit_capture_pct < 1.0: # If it's 1.0 (100%), we never capture early
            if profit_capture_pct <= 0.0:
                # 0% edge case: capture the second it is strictly profitable
                if profit_if_close_per_share > 0.0:
                    return "CLOSE_PROFIT"
            else:
                # Normal capture logic
                if profit_if_close_per_share >= float(profit_capture_pct) * premium_open_per_share:
                    return "CLOSE_PROFIT"

        # 3) Stop loss
        if profit_if_close_per_share <= -float(stop_loss_multiple) * premium_open_per_share:
            return "CLOSE_STOP"

        # 4) Expiration
        if int(dte_remaining) <= 0:
            return "EXPIRE"

        return ""

    def _handle_option_loss_tax_neutral_single_lot(
            self,
            state: OverlayState,
            option_loss_abs: float,
            current_price: float,
            share_reduction_trigger_pct: float,
    ) -> int:
        result, new_shares, new_cash, tlh_delta = handle_option_loss_tax_neutral_single_lot(
            shares=state.shares,
            cost_basis=state.cost_basis,
            cash=state.cash,
            option_loss_abs=option_loss_abs,
            current_price=current_price,
            share_reduction_trigger_pct=share_reduction_trigger_pct,
        )

        # Update state from returned values
        state.shares = float(new_shares)
        state.cash = float(new_cash)

        # Realized stock gain (used for reporting + taxes)
        if result.realized_stock_gain > 0:
            state.realized_stock_gain += float(result.realized_stock_gain)
            state.cumulative_taxes += (float(result.realized_stock_gain) * self.long_term_tax_rate
            )

        # TLH delta from handler
        if tlh_delta > 0:
            state.cumulative_tlh += float(tlh_delta)

        return int(result.shares_sold)
    # -----------------------------
    # Covered call overlay (v1 + new trigger logic)
    # -----------------------------

    def run_covered_call_overlay(
        self,
        # Legacy params (kept for UI compatibility; v1 does NOT use moneyness/roll-frequency)
        call_moneyness_pct: float = 5.0,
        dte_days: int = 45,
        roll_frequency_days: int = 30,
        coverage_pct: float = 50.0,
        enable_tax_loss_harvest: bool = True,  # kept for UI toggle; TLH is tracked, not converted to tax dollars
        position_reduction_pct_per_quarter: float = 0.0,
        reduction_threshold_pct: Optional[float] = None,

        # NEW: share-reduction trigger percent (X% above basis)
        share_reduction_trigger_pct: float = 0.0,

        # Single-lot basis for MVP (if None, defaults to initial price)
        cost_basis: Optional[float] = None,

        # ---- v1 deterministic overlay params ----
        target_dte_days: int = 30,
        target_delta: float = 0.20,
        profit_capture_pct: float = 0.50,
        stop_loss_multiple: float = 1.00,
        extrinsic_threshold_pct: float = 0.05,

        # Reporting counters (v1)
        total_realized_option_loss=0.0,
        total_shares_sold_on_call_loss = 0,

        total_realized_option_pnl = 0.0,
        audit_log: list[str] = [],
        loss_handling_mode: str = "harvest_hold",
        cash_return_mode: str = "underlying",  # v1: cash grows at underlying return
        starting_cash: float = 0.0,
        max_shares_per_month: int = 200,
    ) -> Dict[str, Any]:
        runner = StrategyRunner()
        # map loss_handling_mode -> StrategyRunner key
        strategy_key = "tax_neutral" if loss_handling_mode == "tax_neutral_sell" else "harvest"
        
        df = self.price_data.copy()

        # Initialize columns
        df["Shares"] = 0.0
        df["Covered_Shares"] = 0.0
        df["Stock_Value"] = 0.0
        df["Stock_PnL"] = 0.0
        df["Option_PnL"] = 0.0
        df["Total_PnL"] = 0.0
        df["Cumulative_Taxes"] = 0.0
        df["Strike_Price"] = 0.0
        df["Option_Premium"] = 0.0

        # Debug/verification columns (safe for viz to ignore)
        df["Cash"] = 0.0
        df["Portfolio_Value"] = 0.0
        df["Option_Mark"] = 0.0
        df["Intrinsic"] = 0.0
        df["Extrinsic"] = 0.0
        df["Exit_Reason"] = ""
        df["Cumulative_TLH"] = 0.0
        df["Realized_Stock_Gain"] = 0.0

        # Initials
        initial_price = float(df["Price"].iloc[0])
        initial_value = initial_price * float(self.initial_shares)

        basis = float(cost_basis) if cost_basis is not None else initial_price
        state = self._init_overlay_state(cost_basis=basis)
        state.cash = starting_cash

        # Volatility (deterministic)
        volatility = self.estimate_volatility()

        # Scheduled reduction tracking (kept)
        last_reduction_date = df.index[0]
        reduction_triggered = False

        prev_price: Optional[float] = None

        # Reporting counters (v1)
        total_realized_option_loss = 0.0
        total_shares_sold_on_call_loss = 0
        total_realized_option_pnl = 0.0
        
        # Audit log initialization
        audit_log = [
            f"{df.index[0].date()} | INITIALIZE | CONCENTRATED START\n"
            f"Basis: ${state.cost_basis:,.2f} | Cash: ${state.cash:,.2f} | Shares: {int(state.shares)}"
        ]
        
        # Monthly sale tracking
        shares_sold_this_month = 0
        current_month = None
        
        for date, row in df.iterrows():
            current_price = float(row["Price"])
            exit_reason = ""
            
            # Reset monthly counter
            month = (date.year, date.month)
            if current_month != month:
                current_month = month
                shares_sold_this_month = 0

            # -----------------------------
            # Step 1: cash accrual at underlying return (Removed for MVP)
            # -----------------------------
            # Cash should simply act as cash, PV reflects stock dropping.

            # -----------------------------
            # Optional scheduled reductions (kept)
            # NOTE: This MVP does not tax these scheduled reductions.
            # -----------------------------
            if position_reduction_pct_per_quarter > 0:
                days_since = (date - last_reduction_date).days
                if days_since >= 90:
                    reduction_amount = int(state.shares * (position_reduction_pct_per_quarter / 100.0))
                    reduction_amount = min(reduction_amount, int(state.shares))
                    if reduction_amount > 0:
                        state.cash += reduction_amount * current_price
                        state.shares = max(0.0, state.shares - reduction_amount)
                        last_reduction_date = date

            if reduction_threshold_pct is not None and not reduction_triggered:
                gain_pct = (current_price / initial_price - 1.0) * 100.0
                if gain_pct >= float(reduction_threshold_pct):
                    reduction_amount = int(state.shares * 0.25)
                    reduction_amount = min(reduction_amount, int(state.shares))
                    if reduction_amount > 0:
                        state.cash += reduction_amount * current_price
                        state.shares = max(0.0, state.shares - reduction_amount)
                        reduction_triggered = True

            # -----------------------------
            # Step 2/3: evaluate exit rules if option is open (v1 priority)
            # -----------------------------
            option_mark = 0.0
            intrinsic = 0.0
            extrinsic = 0.0

            if state.open_option is not None and state.open_option.covered_shares > 0:
                days_open = (date - state.open_option.open_date).days
                dte_remaining = int(target_dte_days) - int(days_open)
                T = max(dte_remaining, 0) / 365.0

                option_mark = self.black_scholes_call(
                    current_price, state.open_option.strike, T, self.risk_free_rate, volatility
                )

                intrinsic = max(current_price - state.open_option.strike, 0.0)
                extrinsic = max(option_mark - intrinsic, 0.0)

                exit_reason = self._evaluate_exit_reason(
                    intrinsic=intrinsic,
                    extrinsic=extrinsic,
                    premium_open_per_share=state.open_option.premium_open_per_share,
                    option_mark=option_mark,
                    dte_remaining=dte_remaining,
                    profit_capture_pct=profit_capture_pct,
                    stop_loss_multiple=stop_loss_multiple,
                    extrinsic_threshold_pct=extrinsic_threshold_pct,
                )

                if exit_reason:
                    # Expiration uses intrinsic as settlement/close value
                    close_per_share = intrinsic if exit_reason == "EXPIRE" else option_mark
                    close_cost_total = close_per_share * float(state.open_option.covered_shares)

                    # Cash accounting (v1)
                    state.cash -= close_cost_total

                    # Realized option PnL for THIS trade (signed)
                    realized_option_pnl = state.open_option.premium_open_total - close_cost_total

                    # Reporting totals
                    total_realized_option_pnl += realized_option_pnl
                    state.realized_option_pnl += realized_option_pnl

                    if realized_option_pnl > 0:  # MVP: ignore option-profit taxes
                        pass

                    if realized_option_pnl < 0:
                        loss_amt = abs(realized_option_pnl)
                        total_realized_option_loss += loss_amt

                        # Isolated Repair: Dynamic Mode Switching
                        # Harvest only if Price < Basis. Otherwise Premium Collection (Tax Neutral)
                        if current_price < state.cost_basis:
                            current_strategy_key = "harvest"
                            mode_label = "HARVEST_MODE"
                            reason = "harvest_mode"
                            shares_required = 0
                        else:
                            current_strategy_key = "tax_neutral"
                            mode_label = "PREMIUM_COLLECTION"
                            
                            gain_per_share = current_price - state.cost_basis
                            if gain_per_share <= 0:  # Exactly at basis
                                shares_required = 0
                                reason = "no_gain_available"
                            else:
                                shares_required = int(floor(loss_amt / gain_per_share))
                                
                                remaining_monthly_capacity = max_shares_per_month - shares_sold_this_month
                                
                                if remaining_monthly_capacity <= 0:
                                    shares_required = 0
                                    reason = "monthly_cap_reached"
                                else:
                                    shares_required = min(
                                        shares_required,
                                        remaining_monthly_capacity,
                                        int(state.shares)
                                    )
                                    
                                    trigger_px = state.cost_basis * (1.0 + share_reduction_trigger_pct)
                                    if current_price < trigger_px:
                                        reason = "trigger_not_met"
                                    else:
                                        reason = "trigger_met"

                        logger.debug(
                            f"LOSS={loss_amt:.2f} "
                            f"MODE={mode_label} "
                            f"REASON={reason}"
                        )

                        sim_state = SimState(shares=state.shares, cost_basis=state.cost_basis, cash=state.cash, price=current_price)
                        sim_params = SimParams(
                            sell_shares=shares_required, 
                            option_loss_available=loss_amt, 
                            tax_rate=self.long_term_tax_rate, 
                            trigger_percent=share_reduction_trigger_pct
                        )
                        
                        strat_res = runner.run(current_strategy_key, sim_state, sim_params)
                        
                        shares_sold = strat_res.get("shares_sold", 0)
                        cash_gen = strat_res.get("cash_generated", 0.0)
                        taxes_paid = strat_res.get("taxes", 0.0)
                        tlh_add = strat_res.get("tlh_delta", 0.0)
                        action_str = strat_res.get("action", "NO-SELL")
                        trigger_px = strat_res.get("trigger_price", state.cost_basis)
                        
                        state.shares -= shares_sold
                        shares_sold_this_month += int(shares_sold)
                        state.cash += (cash_gen - taxes_paid)
                        state.cumulative_taxes += taxes_paid
                        state.cumulative_tlh += tlh_add
                        state.realized_stock_gain += strat_res.get("realized_gain", 0.0)

                        total_shares_sold_on_call_loss += int(shares_sold)

                        # Log the event with correct mode label
                        if not exit_reason:
                            exit_reason = "CLOSE_STOP"
                            
                        base_log = (
                            f"{date.date()} | {exit_reason} | {action_str}\n"
                            f"mode={mode_label} | reason={reason}\n"
                            f"px=${current_price:,.2f} | basis=${state.cost_basis:,.2f}"
                        )
                        if current_strategy_key == "tax_neutral" and action_str != "NO-SELL":
                             base_log += f" | trigger={share_reduction_trigger_pct:.0%} | trigger_px=${trigger_px:,.2f}"
                        
                        financials_log = f"opt_loss=${loss_amt:,.0f} | taxes=${taxes_paid:,.0f} | tlh=${tlh_add:,.0f} | tlh_total=${state.cumulative_tlh:,.0f}"
                        
                        if int(shares_sold) > 0:
                            rem_cap = max(0, max_shares_per_month - shares_sold_this_month)
                            shares_log = f"shares_sold={int(shares_sold)} | monthly_cap_remaining={rem_cap}"
                            audit_log.append(f"{base_log}\n{shares_log}\n{financials_log}")
                        else:
                            audit_log.append(f"{base_log}\n{financials_log}")

                        # If you want to “turn off TLH tracking” when disabled:
                        if not enable_tax_loss_harvest:
                            # roll back what we added to TLH in the handler by setting to 0 delta:
                            # (We keep it simple: do nothing; MVP prefers to always track TLH dollars.)
                            pass

                    # Clear option; re-enter next day only
                    state.open_option = None
                    state.open_next_day = True
                    state.last_close_date = date

            # -----------------------------
            # Step 6: open a new option (next day only, v1)
            # -----------------------------
            can_open_today = (state.open_option is None) and (state.shares > 0)

            if can_open_today:
                # v1: do not re-enter same day as a close
                eligible = state.open_next_day and (state.last_close_date is None or date > state.last_close_date)

                if eligible:
                    covered_shares = int(state.shares * (coverage_pct / 100.0))
                    covered_shares = max(0, min(covered_shares, int(state.shares)))

                    T_open = float(target_dte_days) / 365.0
                    strike = self.strike_for_target_delta(
                        current_price, T_open, self.risk_free_rate, volatility, target_delta=float(target_delta)
                    )

                    premium_open_per_share = self.black_scholes_call(
                        current_price, strike, T_open, self.risk_free_rate, volatility
                    )

                    premium_open_total = premium_open_per_share * float(covered_shares)

                    # Cash inflow at open (v1)
                    state.cash += premium_open_total

                    state.open_option = OptionPos(
                        open_date=date,
                        dte_open=int(target_dte_days),
                        strike=float(strike),
                        covered_shares=int(covered_shares),
                        premium_open_per_share=float(premium_open_per_share),
                        premium_open_total=float(premium_open_total),
                    )

                    state.open_next_day = False

            # -----------------------------
            # Record time series (end of day)
            # -----------------------------
            df.loc[date, "Shares"] = float(state.shares)
            df.loc[date, "Covered_Shares"] = float(state.open_option.covered_shares if state.open_option else 0.0)
            df.loc[date, "Strike_Price"] = float(state.open_option.strike if state.open_option else 0.0)
            df.loc[date, "Option_Premium"] = float(state.open_option.premium_open_total if state.open_option else 0.0)

            stock_value = current_price * float(state.shares)
            df.loc[date, "Stock_Value"] = float(stock_value)

            # (We keep Stock_PnL unused/0 in this MVP overlay time series)
            df.loc[date, "Stock_PnL"] = 0.0

            # Keep v1 behavior: Option_PnL column reflects realized option pnl total (not cash)
            df.loc[date, "Option_PnL"] = float(total_realized_option_pnl)

            df.loc[date, "Cumulative_Taxes"] = float(state.cumulative_taxes)
            df.loc[date, "Cumulative_TLH"] = float(state.cumulative_tlh)
            df.loc[date, "Realized_Stock_Gain"] = float(state.realized_stock_gain)

            portfolio_value = stock_value + float(state.cash)
            df.loc[date, "Cash"] = float(state.cash)
            df.loc[date, "Portfolio_Value"] = float(portfolio_value)
            df.loc[date, "Total_PnL"] = float(portfolio_value - initial_value)

            # Debug option fields
            df.loc[date, "Option_Mark"] = float(option_mark)
            df.loc[date, "Intrinsic"] = float(intrinsic)
            df.loc[date, "Extrinsic"] = float(extrinsic)
            df.loc[date, "Exit_Reason"] = str(exit_reason)

            prev_price = current_price

        # Summary
        final_shares = float(df["Shares"].iloc[-1])
        final_stock_value = float(df["Stock_Value"].iloc[-1])
        final_cash = float(df["Cash"].iloc[-1])

        starting_shares = int(self.initial_shares)
        starting_price = float(initial_price)
        final_price = float(df["Price"].iloc[-1])

        total_shares_sold = starting_shares - final_shares
        remaining_shares = starting_shares - total_shares_sold
        
        net_option_cash_flow = float(total_realized_option_pnl)
        ending_cash = final_cash
        ending_stock_value = remaining_shares * final_price

        final_portfolio_value = ending_stock_value + ending_cash
        starting_portfolio_value = (starting_shares * starting_price) + starting_cash

        if starting_portfolio_value > 0:
            total_return = ((final_portfolio_value - starting_portfolio_value) / starting_portfolio_value) * 100.0
        else:
            total_return = 0.0

        print("\n==============================")
        print("SIMULATION SUMMARY")
        print("==============================")
        print()
        print(f"Starting Shares:        {starting_shares}")
        print(f"Shares Sold:            {int(total_shares_sold)}")
        print(f"Remaining Shares:       {int(remaining_shares)}")
        print()
        print(f"Starting Price:         ${starting_price:,.2f}")
        print(f"Final Price:            ${final_price:,.2f}")
        print()
        print(f"Starting Cash:          ${starting_cash:,.0f}")
        print(f"Net Option Cash Flow:   ${net_option_cash_flow:,.0f}")
        print()
        print(f"Ending Stock Value:     ${ending_stock_value:,.0f}")
        print(f"Ending Cash:            ${ending_cash:,.0f}")
        print()
        print(f"Final Portfolio Value:  ${final_portfolio_value:,.0f}")
        print()
        print(f"Total Return:           {total_return:.2f}%")
        print()
        print("==============================\n")

        shares_reduced = int(total_shares_sold_on_call_loss)

        summary = {
            "strategy": "Covered Call Overlay (v1: 20Δ/30D + early exits + cash=underlying + trigger tax-neutral reduction)",
            "initial_shares": int(self.initial_shares),
            "final_shares": float(final_shares),
        
            # v1 discipline outputs
            "shares_reduced": shares_reduced,
            "shares_sold_on_call_loss": int(total_shares_sold_on_call_loss),
            "realized_option_pnl": float(total_realized_option_pnl),
            "realized_option_loss": float(total_realized_option_loss),
            "realized_stock_gain": float(state.realized_stock_gain),
            "net_option_cash_flow": net_option_cash_flow,
        
            # valuation
            "starting_cash": float(starting_cash),
            "initial_value": float(starting_portfolio_value),
            "final_stock_value": float(ending_stock_value),
            "final_cash": float(ending_cash),
            "final_portfolio_value": float(final_portfolio_value),
            "total_return_pct": float(total_return),
        
            "cash_balance": float(ending_cash),
            "total_pnl": float(df["Total_PnL"].iloc[-1]),
        
            # config echo (locked v1)
            "target_dte_days": int(target_dte_days),
            "target_delta": float(target_delta),
            "profit_capture_pct": float(profit_capture_pct),
            "stop_loss_multiple": float(stop_loss_multiple),
            "extrinsic_threshold_pct": float(extrinsic_threshold_pct),
            "coverage_pct": float(coverage_pct),
            "cash_return_mode": str(cash_return_mode),
        
            # UI keys required by Streamlit
            "final_cash_proceeds": float(final_cash),        # UI uses this key
            "final_income_cash_balance": float(final_cash),  # optional nicer name
            "cumulative_taxes": float(state.cumulative_taxes),
        
            # informational
            "cumulative_tlh": float(state.cumulative_tlh),
        
            # Basis + trigger echo (MVP)
            "cost_basis_single_lot": float(state.cost_basis),
            "share_reduction_trigger_pct": float(share_reduction_trigger_pct),
            "audit_log": audit_log,
        
            # Debug (safe)
            "__debug_code_fingerprint__": "FINGERPRINT_2026_02_23_A",
            "__debug_trigger__": float(share_reduction_trigger_pct),
        }
        return {"time_series": df.reset_index(), "summary": summary}


# -----------------------------
# Comparison runner
# -----------------------------

def run_strategy_comparison(
    ticker: str,
    start_date: str,
    end_date: str,
    initial_shares: int = 1000,
    call_moneyness_pct: float = 5.0,
    dte_days: int = 45,
    roll_frequency_days: int = 30,
    coverage_pct: float = 50.0,
    enable_tax_loss_harvest: bool = True,
    position_reduction_pct_per_quarter: float = 0.0,
    reduction_threshold_pct: Optional[float] = None,

    # NEW:
    share_reduction_trigger_pct: float = 0.10,
    cost_basis: Optional[float] = None,

    # LEGACY (Streamlit still passes these; accepted for backward compatibility)
    sell_shares_on_call_loss: bool = False,
    sell_shares_on_call_loss_pct: float = 0.0,
    min_call_loss_to_trigger: float = 0.0,
) -> Dict[str, Any]:
    # (legacy args are intentionally ignored in the new trigger-based engine)
    _ = (sell_shares_on_call_loss, sell_shares_on_call_loss_pct, min_call_loss_to_trigger)

    engine = StrategyUnwindEngine(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
        initial_shares=initial_shares,
    )

    baseline = engine.run_baseline()

    overlay = engine.run_covered_call_overlay(
        call_moneyness_pct=call_moneyness_pct,
        dte_days=dte_days,
        roll_frequency_days=roll_frequency_days,
        coverage_pct=coverage_pct,
        enable_tax_loss_harvest=enable_tax_loss_harvest,
        position_reduction_pct_per_quarter=position_reduction_pct_per_quarter,
        reduction_threshold_pct=reduction_threshold_pct,
        share_reduction_trigger_pct=share_reduction_trigger_pct,
        cost_basis=cost_basis,
    )

    overlay_summary = overlay.get("summary", {})
    overlay_summary["__engine_version__"] = "V1_OVERLAY_ENGINE_REWRITE_TRIGGER_TAXNEUTRAL_SINGLELOT"
    


    return {
        "baseline": baseline,
        "overlay": overlay,
        "ticker": ticker,
        "start_date": start_date,
        "end_date": end_date,
    }
