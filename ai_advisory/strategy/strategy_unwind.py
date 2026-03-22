"""
Concentrated Position Unwind Strategy Module
ai_advisory/strategy/strategy_unwind.py

Responsibilities (this file):
  - Buy-and-hold baseline
  - Covered call overlay: option open, mark, early exit, expiry
  - Option cash accounting: premium inflow at open, cost-to-close outflow at close
  - TLH delta reporting: tlh_delta += loss_amt on option loss (report only — never consumed here)
  - Option lifecycle audit log entries
  - Feed OptionsLedger on every open/close/expire event

Boundary contract (this file NEVER does):
  - Never makes sell decisions (DecisionService owns all sell logic)
  - Never sizes shares_to_sell (DecisionService owns sizing)
  - Never reads, writes, or consumes TLH inventory (DecisionService owns inventory)
  - Never calls StrategyRunner
  - Never determines decision mode (Mode 1 / 2 / 3)

Integration contract:
  CP engine opens options via OptionsLedger.open()
  CP engine closes options via OptionsLedger.close_early() or evaluate_expirations()
  CP engine calls OptionsLedger.mark_open_positions() each step for UI
  Orchestrator reads OptionsLedger.pending_events() → tlh_delta → DecisionInput
  DecisionService reads OptionsLedger.free_shares() → DecisionInput.free_shares

Architecture position (DecisionService_Spec §2):
  Orchestrator → CP Engine (covered call overlay) → OptionsLedger
                                                   → tlh_delta reported upward
  Orchestrator → DecisionService (all sell logic)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
import yfinance as yf
from scipy.stats import norm
import logging

logger = logging.getLogger(__name__)

from ai_advisory.strategy.options_ledger import OptionsLedger, OptionPosition


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class OptionPos:
    """
    Local option position mirror used within the sim loop.
    The authoritative record lives in OptionsLedger.
    position_id links back to the ledger entry.
    """
    position_id:            str
    open_date:              pd.Timestamp
    expiry_date:            pd.Timestamp   # calendar expiry date (date-driven)
    dte_open:               int
    strike:                 float
    covered_shares:         int
    premium_open_per_share: float
    premium_open_total:     float


@dataclass
class OverlayState:
    """
    Carries state between monthly orchestrator steps.
    TLH inventory fields removed — owned by DecisionService.
    """
    shares:             float
    cost_basis:         float
    cash:               float
    open_option:        Optional[OptionPos]

    cumulative_taxes:   float
    realized_option_pnl: float

    last_close_date:        Optional[pd.Timestamp]
    open_next_day:          bool
    next_call_allowed_date: Optional[pd.Timestamp] = None


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class StrategyUnwindEngine:
    """
    Covered call overlay engine for concentrated position management.

    Owns:
      - Price data loading
      - Black-Scholes pricing and strike selection
      - Option lifecycle (open → exit evaluation → close/expire)
      - Cash accounting for option premium
      - tlh_delta reporting (never consumption)
      - OptionsLedger write calls

    Does NOT own:
      - Sell decisions (DecisionService)
      - TLH inventory (DecisionService)
      - Trade execution (Execution Layer)
    """

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

    # ------------------------------------------------------------------
    # Data load
    # ------------------------------------------------------------------

    def _load_price_data(self) -> pd.DataFrame:
        import time
        max_retries = 3
        df = None
        for attempt in range(max_retries):
            try:
                df = yf.download(
                    self.ticker,
                    start=self.start_date,
                    end=self.end_date,
                    progress=False,
                )
                if df is not None and not df.empty:
                    break
            except Exception as e:
                logger.warning(f"yf.download failed on attempt {attempt+1}: {e}")
            if attempt < max_retries - 1:
                time.sleep(1.5)

        if df is None or df.empty:
            raise ValueError(f"No data available for {self.ticker}")

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

    # ------------------------------------------------------------------
    # Option math
    # ------------------------------------------------------------------

    def black_scholes_call(self, S: float, K: float, T: float, r: float, sigma: float) -> float:
        """European call approximation (Black-Scholes)."""
        if T <= 0:
            return max(S - K, 0.0)
        sigma = max(float(sigma), 1e-6)
        S = max(float(S), 1e-9)
        K = max(float(K), 1e-9)
        d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        return max(float(S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)), 0.0)

    def estimate_volatility(self, lookback_days: int = 60) -> float:
        """Deterministic annualised vol from log returns."""
        prices = self.price_data["Price"].values
        if len(prices) < 3:
            return 0.30
        window = prices[-min(lookback_days, len(prices)):]
        rets = np.diff(np.log(window))
        if len(rets) < 2:
            return 0.30
        return max(float(np.std(rets)) * math.sqrt(252), 0.10)

    def strike_for_target_delta(
        self, S: float, T: float, r: float, sigma: float, target_delta: float = 0.20
    ) -> float:
        """
        Deterministic strike solver from target call delta.
        delta = N(d1) → d1 = N⁻¹(delta)
        K = S * exp(-(d1*sigma*sqrt(T) - (r+0.5*sigma²)*T))
        """
        T     = max(float(T), 1e-9)
        sigma = max(float(sigma), 1e-6)
        td    = min(max(float(target_delta), 1e-6), 1 - 1e-6)
        d1    = float(norm.ppf(td))
        return max(float(S) * math.exp(-(d1 * sigma * math.sqrt(T) - (r + 0.5 * sigma * sigma) * T)), 0.01)

    # ------------------------------------------------------------------
    # Baseline
    # ------------------------------------------------------------------

    def run_baseline(self) -> Dict[str, Any]:
        df = self.price_data.copy()
        df["Shares"]          = float(self.initial_shares)
        df["Stock_Value"]     = df["Price"] * df["Shares"]
        initial_value         = float(df["Stock_Value"].iloc[0])
        df["Stock_PnL"]       = df["Stock_Value"] - initial_value
        df["Option_PnL"]      = 0.0
        df["Total_PnL"]       = df["Stock_PnL"]
        df["Cumulative_Taxes"] = 0.0
        df["Covered_Shares"]  = 0.0
        df["Strike_Price"]    = 0.0
        final_value           = float(df["Stock_Value"].iloc[-1])

        return {
            "time_series": df.reset_index(),
            "summary": {
                "strategy":        "Buy-and-Hold Baseline",
                "initial_shares":  self.initial_shares,
                "final_shares":    self.initial_shares,
                "initial_value":   initial_value,
                "final_value":     final_value,
                "total_return_pct": (final_value / initial_value - 1.0) * 100.0,
                "stock_pnl":       float(df["Stock_PnL"].iloc[-1]),
                "option_pnl":      0.0,
                "total_pnl":       float(df["Total_PnL"].iloc[-1]),
                "cumulative_taxes": 0.0,
            },
        }

    # ------------------------------------------------------------------
    # Exit evaluation (CP engine's responsibility — unchanged)
    # ------------------------------------------------------------------

    @staticmethod
    def _evaluate_exit_reason(
        intrinsic:               float,
        extrinsic:               float,
        premium_open_per_share:  float,
        option_mark:             float,
        dte_remaining:           int,
        profit_capture_pct:      float,
        stop_loss_multiple:      float,
        extrinsic_threshold_pct: float,
    ) -> str:
        """
        Strict v1 priority:
          1) CLOSE_ASSIGNMENT_PREVENT
          2) CLOSE_PROFIT
          3) CLOSE_STOP
          4) EXPIRE
        """
        premium_open_per_share    = max(float(premium_open_per_share), 1e-9)
        profit_if_close_per_share = premium_open_per_share - float(option_mark)

        if intrinsic > 0 and extrinsic <= float(extrinsic_threshold_pct) * premium_open_per_share:
            return "CLOSE_ASSIGNMENT_PREVENT"

        if profit_capture_pct < 1.0:
            if profit_capture_pct <= 0.0:
                if profit_if_close_per_share > 0.0:
                    return "CLOSE_PROFIT"
            else:
                if profit_if_close_per_share >= float(profit_capture_pct) * premium_open_per_share:
                    return "CLOSE_PROFIT"

        if profit_if_close_per_share <= -float(stop_loss_multiple) * premium_open_per_share:
            return "CLOSE_STOP"

        if int(dte_remaining) <= 0:
            return "EXPIRE"

        return ""

    # ------------------------------------------------------------------
    # Covered call overlay
    # ------------------------------------------------------------------

    def run_covered_call_overlay(
        self,
        options_ledger:                  OptionsLedger,
        enable_covered_call:             bool  = True,
        coverage_pct:                    float = 50.0,
        target_dte_days:                 int   = 30,
        target_delta:                    float = 0.20,
        profit_capture_pct:              float = 0.50,
        stop_loss_multiple:              float = 1.00,
        extrinsic_threshold_pct:         float = 0.05,
        wash_sale_cooldown_days:         int   = 0,
        position_reduction_pct_per_quarter: float = 0.0,
        reduction_threshold_pct:         Optional[float] = None,
        cost_basis:                      Optional[float] = None,
        starting_cash:                   float = 0.0,
        initial_state:                   Any   = None,
        cash_return_mode:                str   = "underlying",
    ) -> Dict[str, Any]:
        """
        Run the covered call overlay for one simulation window.

        Returns a result dict containing:
          - time_series: DataFrame with option lifecycle columns
          - summary: option-specific metrics (no sell/TLH keys)
          - tlh_delta: total TLH generated from option losses this run (report only)

        DecisionService integration:
          Caller (orchestrator) reads options_ledger.pending_events() after this
          returns, sums tlh_delta, and passes it into DecisionInput.tlh_delta_this_step.
          Caller reads options_ledger.free_shares() for DecisionInput.free_shares.
        """
        df = self.price_data.copy()

        # Single-row mode: override price with live price when orchestrator passes state
        if initial_state is not None and getattr(initial_state, 'current_price', 0.0) > 0.0:
            df = df.iloc[[-1]].copy()
            df["Price"] = float(initial_state.current_price)

        # Initialize time-series columns
        for col in [
            "Shares", "Covered_Shares", "Stock_Value", "Stock_PnL",
            "Option_PnL", "Total_PnL", "Cumulative_Taxes",
            "Strike_Price", "Option_Premium", "Cash", "Portfolio_Value",
            "Option_Mark", "Intrinsic", "Extrinsic", "Realized_Stock_Gain",
        ]:
            df[col] = 0.0
        df["Exit_Reason"] = ""

        initial_price    = float(df["Price"].iloc[0])
        initial_value    = initial_price * float(self.initial_shares)
        basis            = float(cost_basis) if cost_basis is not None else initial_price

        # State carried across rows
        current_shares   = float(initial_state.shares)    if initial_state is not None else float(self.initial_shares)
        current_cash     = float(initial_state.cash)      if initial_state is not None else starting_cash
        initial_basis_val = float(initial_state.cost_basis) if initial_state is not None else basis

        shares_delta     = 0.0
        cash_delta       = 0.0

        open_option: Optional[OptionPos] = (
            getattr(initial_state, 'open_option', None) if initial_state is not None else None
        )
        next_call_allowed_date: Optional[pd.Timestamp] = (
            getattr(initial_state, 'next_call_allowed_date', None) if initial_state is not None else None
        )

        volatility       = self.estimate_volatility()

        # Option income / loss reporting (CP engine scope only)
        total_realized_option_pnl   = 0.0
        total_realized_option_loss  = 0.0
        option_premium_collected    = 0.0
        option_buyback_cost         = 0.0
        option_income               = 0.0
        option_losses               = 0.0
        tlh_delta_reported          = 0.0   # reported upward; never consumed here
        yearly_tax_ledger: Dict     = {}

        # Scheduled reduction tracking (orthogonal to sell logic — kept)
        last_reduction_date = df.index[0]
        reduction_triggered = False

        # Audit log: option lifecycle events only
        audit_log = [
            f"{df.index[0].date()} | INITIALIZE | CONCENTRATED START\n"
            f"Basis: ${initial_basis_val:,.2f} | Cash: ${starting_cash:,.2f} | Shares: {int(self.initial_shares)}"
        ]

        for date, row in df.iterrows():
            current_price = float(row["Price"])
            exit_reason   = ""

            if (current_shares + shares_delta) <= 0:
                break

            # ----------------------------------------------------------
            # Scheduled reductions (kept — orthogonal to sell decisions)
            # NOTE: not taxed in MVP
            # ----------------------------------------------------------
            if position_reduction_pct_per_quarter > 0:
                days_since = (date - last_reduction_date).days
                if days_since >= 90:
                    reduction_amount = min(
                        int((current_shares + shares_delta) * (position_reduction_pct_per_quarter / 100.0)),
                        int(current_shares + shares_delta),
                    )
                    if reduction_amount > 0:
                        cash_delta     += reduction_amount * current_price
                        current_shares  = max(0.0, (current_shares + shares_delta) - reduction_amount)
                        last_reduction_date = date

            if reduction_threshold_pct is not None and not reduction_triggered:
                gain_pct = (current_price / initial_price - 1.0) * 100.0
                if gain_pct >= float(reduction_threshold_pct):
                    reduction_amount = min(
                        int((current_shares + shares_delta) * 0.25),
                        int(current_shares + shares_delta),
                    )
                    if reduction_amount > 0:
                        cash_delta     += reduction_amount * current_price
                        current_shares  = max(0.0, (current_shares + shares_delta) - reduction_amount)
                        reduction_triggered = True

            # ----------------------------------------------------------
            # Step 1: Mark open position (UI + exit evaluation)
            # ----------------------------------------------------------
            option_mark = 0.0
            intrinsic   = 0.0
            extrinsic   = 0.0

            if open_option is not None and open_option.covered_shares > 0:
                # Date-driven DTE — uses expiry_date, not sim cadence
                dte_remaining = open_option.expiry_date.date() - date.date()
                dte_days_remaining = dte_remaining.days
                T = max(dte_days_remaining, 0) / 365.0

                option_mark = self.black_scholes_call(
                    current_price, open_option.strike, T, self.risk_free_rate, volatility
                )
                intrinsic = max(current_price - open_option.strike, 0.0)
                extrinsic = max(option_mark - intrinsic, 0.0)

                # Mark the ledger position for UI
                options_ledger.mark_open_positions(
                    current_price=current_price,
                    volatility=volatility,
                    risk_free_rate=self.risk_free_rate,
                    current_date=date.date(),
                    bs_call_fn=self.black_scholes_call,
                )

                # ----------------------------------------------------------
                # Step 2: Exit evaluation (v1 priority — CP engine owns this)
                # ----------------------------------------------------------
                exit_reason = self._evaluate_exit_reason(
                    intrinsic=intrinsic,
                    extrinsic=extrinsic,
                    premium_open_per_share=open_option.premium_open_per_share,
                    option_mark=option_mark,
                    dte_remaining=dte_days_remaining,
                    profit_capture_pct=profit_capture_pct,
                    stop_loss_multiple=stop_loss_multiple,
                    extrinsic_threshold_pct=extrinsic_threshold_pct,
                )

                if exit_reason:
                    # Settlement value
                    close_per_share  = intrinsic if exit_reason == "EXPIRE" else option_mark
                    close_cost_total = close_per_share * float(open_option.covered_shares)

                    # Cash accounting (v1 discipline)
                    cash_delta -= close_cost_total

                    # Realized option PnL
                    realized_option_pnl   = open_option.premium_open_total - close_cost_total
                    option_premium_collected += open_option.premium_open_total
                    option_buyback_cost      += close_cost_total
                    total_realized_option_pnl += realized_option_pnl

                    # Yearly tax ledger
                    year = date.year
                    if year not in yearly_tax_ledger:
                        yearly_tax_ledger[year] = {
                            "option_income": 0.0,
                            "option_losses": 0.0,
                            "net_capital_result": 0.0,
                            "tlh_generated": 0.0,
                        }

                    if realized_option_pnl >= 0:
                        option_income += realized_option_pnl
                        yearly_tax_ledger[year]["option_income"]      += realized_option_pnl
                        yearly_tax_ledger[year]["net_capital_result"]  = (
                            yearly_tax_ledger[year]["option_income"]
                            - yearly_tax_ledger[year]["option_losses"]
                        )
                        yearly_tax_ledger[year]["tlh_generated"] = yearly_tax_ledger[year]["option_losses"]
                        audit_log.append(
                            f"{date.date()} | {exit_reason} | NO-LOSS\n"
                            f"opt_profit=${realized_option_pnl:,.0f}"
                        )
                    else:
                        loss_amt = abs(realized_option_pnl)
                        option_losses            += loss_amt
                        total_realized_option_loss += loss_amt

                        yearly_tax_ledger[year]["option_losses"]      += loss_amt
                        yearly_tax_ledger[year]["net_capital_result"]  = (
                            yearly_tax_ledger[year]["option_income"]
                            - yearly_tax_ledger[year]["option_losses"]
                        )
                        yearly_tax_ledger[year]["tlh_generated"] = yearly_tax_ledger[year]["option_losses"]

                        # TLH reporting — report only, never consumed here
                        tlh_delta_reported += loss_amt

                        # Wash-sale cooldown
                        if wash_sale_cooldown_days > 0:
                            next_call_allowed_date = pd.Timestamp(date) + pd.Timedelta(days=wash_sale_cooldown_days)

                        audit_log.append(
                            f"{date.date()} | {exit_reason} | OPTION-LOSS\n"
                            f"loss=${loss_amt:,.0f} | tlh_delta_reported=${tlh_delta_reported:,.0f}\n"
                            f"NOTE: sell decision deferred to DecisionService"
                        )

                    # Notify OptionsLedger of close
                    if exit_reason == "EXPIRE":
                        options_ledger.evaluate_expirations(
                            current_date=date.date(),
                            current_price=current_price,
                        )
                    else:
                        options_ledger.close_early(
                            position_id=open_option.position_id,
                            close_date=date.date(),
                            close_per_share=close_per_share,
                            close_reason=exit_reason,
                        )

                    open_option = None

            # ----------------------------------------------------------
            # Step 3: Settle any options that expired by date
            # (handles cases where expiry_date passed without an explicit
            #  exit_reason firing — e.g. daily cadence skips exact date)
            # ----------------------------------------------------------
            expiry_events = options_ledger.evaluate_expirations(
                current_date=date.date(),
                current_price=current_price,
            )
            for ev in expiry_events:
                # Keep local open_option in sync
                if open_option is not None and open_option.position_id == ev.position_id:
                    open_option = None
                # Report TLH from date-driven expiry (may differ from early close above)
                tlh_delta_reported += ev.tlh_delta
                if ev.tlh_delta > 0:
                    audit_log.append(
                        f"{date.date()} | EXPIRE_SETTLED | position={ev.position_id}\n"
                        f"tlh_delta=${ev.tlh_delta:,.0f} | outcome={ev.outcome.value}\n"
                        f"NOTE: sell decision deferred to DecisionService"
                    )

            # ----------------------------------------------------------
            # Step 4: Open a new covered call
            # ----------------------------------------------------------
            can_open = (
                enable_covered_call
                and open_option is None
                and (current_shares + shares_delta) > 0
                and not options_ledger.has_open_position()
            )

            if can_open:
                if next_call_allowed_date is not None and date < next_call_allowed_date:
                    can_open = False

            if can_open:
                covered_shares = int((current_shares + shares_delta) * (coverage_pct / 100.0))
                covered_shares = max(0, min(covered_shares, int(current_shares + shares_delta)))

                T_open        = float(target_dte_days) / 365.0
                raw_strike    = self.strike_for_target_delta(
                    current_price, T_open, self.risk_free_rate, volatility, target_delta=float(target_delta)
                )
                strike_max_delta = self.strike_for_target_delta(
                    current_price, T_open, self.risk_free_rate, volatility, target_delta=0.35
                )
                # Phase 1 constraints: delta <= 0.35, strike >= 1.05 * price
                strike = max(raw_strike, current_price * 1.05, strike_max_delta)

                premium_open_per_share = self.black_scholes_call(
                    current_price, strike, T_open, self.risk_free_rate, volatility
                )
                premium_open_total = premium_open_per_share * float(covered_shares)

                if premium_open_total <= 0:
                    pass  # skip — no premium available
                else:
                    # Cash inflow at open (v1 discipline)
                    cash_delta += premium_open_total

                    # Compute calendar expiry date from target DTE
                    expiry_date = pd.Timestamp(date) + pd.Timedelta(days=target_dte_days)

                    # Write to OptionsLedger (authoritative record)
                    ledger_pos: OptionPosition = options_ledger.open(
                        underlying=self.ticker,
                        strike=float(strike),
                        written_date=date.date(),
                        expiry_date=expiry_date.date(),
                        shares_encumbered=int(covered_shares),
                        premium_open_per_share=float(premium_open_per_share),
                    )

                    # Local mirror for sim loop
                    open_option = OptionPos(
                        position_id=ledger_pos.position_id,
                        open_date=pd.Timestamp(date),
                        expiry_date=expiry_date,
                        dte_open=int(target_dte_days),
                        strike=float(strike),
                        covered_shares=int(covered_shares),
                        premium_open_per_share=float(premium_open_per_share),
                        premium_open_total=float(premium_open_total),
                    )

                    audit_log.append(
                        f"{date.date()} | SELL_CALL | {covered_shares} shares\n"
                        f"strike=${strike:,.2f} | premium=${premium_open_total:,.0f} "
                        f"| expiry={expiry_date.date()} | delta<={0.35}"
                    )

            # ----------------------------------------------------------
            # Record time-series (end of step)
            # ----------------------------------------------------------
            shares_now    = float(current_shares + shares_delta)
            stock_value   = current_price * shares_now
            portfolio_val = stock_value + float(current_cash + cash_delta)

            df.loc[date, "Shares"]          = shares_now
            df.loc[date, "Covered_Shares"]  = float(open_option.covered_shares if open_option else 0.0)
            df.loc[date, "Strike_Price"]    = float(open_option.strike          if open_option else 0.0)
            df.loc[date, "Option_Premium"]  = float(open_option.premium_open_total if open_option else 0.0)
            df.loc[date, "Stock_Value"]     = float(stock_value)
            df.loc[date, "Stock_PnL"]       = 0.0  # kept for UI compat
            df.loc[date, "Option_PnL"]      = float(total_realized_option_pnl)
            df.loc[date, "Cumulative_Taxes"] = 0.0  # taxes computed by orchestrator
            df.loc[date, "Cash"]            = float(current_cash + cash_delta)
            df.loc[date, "Portfolio_Value"] = float(portfolio_val)
            df.loc[date, "Total_PnL"]       = float(portfolio_val - initial_value)
            df.loc[date, "Option_Mark"]     = float(option_mark)
            df.loc[date, "Intrinsic"]       = float(intrinsic)
            df.loc[date, "Extrinsic"]       = float(extrinsic)
            df.loc[date, "Exit_Reason"]     = str(exit_reason)

        # ------------------------------------------------------------------
        # Summary (option-scoped keys only — sell/TLH keys removed)
        # ------------------------------------------------------------------
        final_shares    = float(current_shares + shares_delta)
        final_cash      = float(current_cash + cash_delta)
        final_price     = float(df["Price"].iloc[-1])
        starting_price  = float(initial_price)

        summary = {
            "strategy": "Covered Call Overlay (v2: date-driven expiry, DecisionService sell logic)",

            # Position
            "initial_shares":  int(self.initial_shares),
            "final_shares":    float(final_shares),
            "shares_delta":    float(shares_delta),

            # Option income / loss (CP engine scope)
            "realized_option_pnl":     float(total_realized_option_pnl),
            "realized_option_loss":    float(total_realized_option_loss),
            "option_premium_collected": float(option_premium_collected),
            "option_buyback_cost":     float(option_buyback_cost),
            "option_income":           float(option_income),
            "option_losses":           float(option_losses),
            "net_option_result":       float(option_income - option_losses),

            # TLH reported (not consumed) — orchestrator reads this and
            # passes it as tlh_delta_this_step into DecisionInput
            "tlh_delta_reported": float(tlh_delta_reported),

            # Yearly tax ledger (option events only)
            "yearly_tax_ledger": yearly_tax_ledger,

            # Valuation
            "starting_cash":       float(starting_cash),
            "initial_value":       float(initial_value),
            "final_cash":          float(final_cash),
            "ending_price":        float(final_price),
            "starting_price":      float(starting_price),
            "cash_delta":          float(cash_delta),

            # Option config echo
            "target_dte_days":          int(target_dte_days),
            "target_delta":             float(target_delta),
            "profit_capture_pct":       float(profit_capture_pct),
            "stop_loss_multiple":       float(stop_loss_multiple),
            "extrinsic_threshold_pct":  float(extrinsic_threshold_pct),
            "coverage_pct":             float(coverage_pct),
            "cash_return_mode":         str(cash_return_mode),

            # UI keys
            "final_cash_proceeds":     float(final_cash),
            "final_income_cash_balance": float(final_cash),

            # Open option state (for next orchestrator step)
            "is_option_open":        open_option is not None,
            "open_option_premium":   float(open_option.premium_open_total) if open_option else 0.0,
            "open_option":           open_option,
            "next_call_allowed_date": next_call_allowed_date,

            # Audit
            "audit_log": audit_log,
        }

        return {"time_series": df.reset_index(), "summary": summary}


# ---------------------------------------------------------------------------
# Comparison runner (backward-compatible entry point)
# ---------------------------------------------------------------------------

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
    max_shares_per_month: int = 200,
    share_reduction_trigger_pct: float = 0.10,
    strategy_mode: str = "harvest",
    cost_basis: Optional[float] = None,
    wash_sale_cooldown_days: int = 0,
    # Legacy args accepted for backward compat but not used
    sell_shares_on_call_loss: bool = False,
    sell_shares_on_call_loss_pct: float = 0.0,
    min_call_loss_to_trigger: float = 0.0,
) -> Dict[str, Any]:
    _ = (sell_shares_on_call_loss, sell_shares_on_call_loss_pct, min_call_loss_to_trigger)

    engine         = StrategyUnwindEngine(ticker=ticker, start_date=start_date, end_date=end_date, initial_shares=initial_shares)
    options_ledger = OptionsLedger(underlying=ticker)
    baseline       = engine.run_baseline()

    overlay = engine.run_covered_call_overlay(
        options_ledger=options_ledger,
        coverage_pct=coverage_pct,
        target_dte_days=dte_days,
        position_reduction_pct_per_quarter=position_reduction_pct_per_quarter,
        reduction_threshold_pct=reduction_threshold_pct,
        cost_basis=cost_basis,
        wash_sale_cooldown_days=wash_sale_cooldown_days,
    )

    overlay_summary = overlay.get("summary", {})
    overlay_summary["__engine_version__"] = "V2_DECISION_SERVICE_DECOUPLED"

    return {
        "baseline":   baseline,
        "overlay":    overlay,
        "ticker":     ticker,
        "start_date": start_date,
        "end_date":   end_date,
    }
