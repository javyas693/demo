"""
portfolio_orchestrator.py
ai_advisory/orchestration/portfolio_orchestrator.py

Pure capital router. Reads DecisionResult, emits trade intents.
No sizing logic. No sell decisions. No TLH inventory management.

Architecture contract (DecisionService_Spec §2 + Architecture Contract v2):
  Flow: ClientProfile + PortfolioState
          → Signal Engine          (raw signal values, no decisions)
          → Decision Service       (all sell/hold/unwind logic)
          → Orchestrator           (capital routing only — this file)
          → CP Engine              (covered call overlay + OptionsLedger writes)
          → Execution Layer        (trade intents → ledger)

Orchestrator step sequence (every cycle):
  1. Generate signals
  2. Build DecisionInput (free_shares from OptionsLedger, tlh_delta from CP engine)
  3. DecisionService.evaluate() → DecisionResult
  4. Emit sell trade intent if enable_unwind
  5. Route released capital → income / model sleeves
  6. Log decision_trace
"""

from __future__ import annotations

import copy
from datetime import datetime, date as _date
from typing import Any, Dict, List, Optional

from ai_advisory.portfolio.portfolio_state import PortfolioState
from ai_advisory.strategy.strategy_unwind import StrategyUnwindEngine
from ai_advisory.strategy.options_ledger import OptionsLedger
from ai_advisory.strategy.anchor_income import AnchorIncomeEngine
from ai_advisory.services.portfolio_analytics import run_mp_backtest
from ai_advisory.services.decision_service import (
    DecisionService,
    DecisionInput,
    ClientConstraint,
    SignalInput,
    UnwindParams,
)
from ai_advisory.orchestration.trace_logger import trace_log

# ---------------------------------------------------------------------------
# Frontier weight lookup (unchanged)
# ---------------------------------------------------------------------------

_FRONTIER_STORE_ROOT = "data/frontiers"


def _get_frontier_weights(
    risk_score: int,
    as_of: Optional[str] = None,
    model_id: str = "core",
) -> Dict[str, float]:
    from ai_advisory.frontier.store.fs_store import FileSystemFrontierStore
    from ai_advisory.frontier.trade_flow_compat import weights_for_risk_score

    as_of = as_of or str(_date.today())
    store = FileSystemFrontierStore(root=_FRONTIER_STORE_ROOT)

    latest = store.get_latest(as_of, model_id)
    if not latest or not store.exists(as_of, latest):
        trace_log(f"[FRONTIER] No frontier for as_of={as_of} — building now...")
        _build_and_store_frontier(store, as_of, model_id)
        latest = store.get_latest(as_of, model_id)

    if not latest:
        trace_log("[FRONTIER] Build failed — using balanced proxy")
        return {"SPY": 0.60, "IEF": 0.30, "BIL": 0.10}

    try:
        return weights_for_risk_score(store, as_of, model_id, risk_score)
    except Exception as e:
        trace_log(f"[FRONTIER] Lookup error: {e} — using balanced proxy")
        return {"SPY": 0.60, "IEF": 0.30, "BIL": 0.10}


def _build_and_store_frontier(store, as_of: str, model_id: str) -> None:
    import os
    from ai_advisory.frontier.engine import build_frontier_from_config
    from ai_advisory.frontier.spec import FrontierSpec, UniverseSpec, ConstraintsSpec
    from ai_advisory.core.frontier_status import FrontierStatus

    spec = FrontierSpec(
        as_of=as_of,
        model_id=model_id,
        universe=UniverseSpec(assets=[]),
        constraints=ConstraintsSpec(bounds={}),
    )
    cache_path = os.path.join(_FRONTIER_STORE_ROOT, "yf_price_cache.pkl")

    try:
        result = build_frontier_from_config(
            spec=spec,
            allocation_sheet="Sub-Assets",
            prices_period="5y",
            cache_path=cache_path,
        )
        store.put(result)
        store.set_status(as_of, result.frontier_version, FrontierStatus.LOCKED)
        store.set_latest(as_of, model_id, result.frontier_version)
        trace_log(f"[FRONTIER] Built + locked: {result.frontier_version} ({len(result.points_sampled)} points)")
    except Exception as e:
        trace_log(f"[FRONTIER] Build error: {e}")


# ---------------------------------------------------------------------------
# PortfolioOrchestrator
# ---------------------------------------------------------------------------

class PortfolioOrchestrator:
    """
    Pure capital router. Sits one level above the specialized engines.
    Does not recreate their math; governs capital flow between them.

    Responsibilities:
      - De-risk scoring and unwind parameter mapping
      - Signal → DecisionInput assembly
      - Reading DecisionResult and emitting trade intents
      - Routing released capital to income / model sleeves
      - Decision logging

    Non-responsibilities:
      - Sell sizing (DecisionService)
      - TLH inventory tracking (DecisionService)
      - Option lifecycle (CP engine + OptionsLedger)
      - Portfolio state mutation (Execution Layer)
    """

    def __init__(self, state: PortfolioState, income_preference: float = 50.0):
        self.state = state
        self.income_preference = income_preference
        self.decision_log: List[Dict[str, Any]] = []

    def _log_decision(self, event: str, details: Dict[str, Any]) -> None:
        trace_log(f"--- [MODULE 4] LEDGER/EVENT TRACE: {event} ---")
        if event == "ORCHESTRATION_CYCLE_COMPLETE":
            trace_log("Trades explicitly handled via execution_layer.execute_trades")
        self.decision_log.append({
            "timestamp": datetime.now().isoformat(),
            "event": event,
            "details": details,
        })

    def determine_de_risk_score(self) -> float:
        """
        De-risk scoring layer.
        Higher risk score = lower desire to unwind quickly.
        Lower risk score = higher desire to unwind an outsized concentrated position.
        """
        base_urgency   = self.state.concentration_pct * 100.0
        risk_adjustment = (100.0 - self.state.risk_score) / 100.0
        de_risk_score  = base_urgency * risk_adjustment

        self._log_decision("EVALUATE_RISK_POSTURE", {
            "concentration_pct":       round(self.state.concentration_pct, 4),
            "risk_score_input":        self.state.risk_score,
            "calculated_de_risk_score": round(de_risk_score, 2),
        })
        return de_risk_score

    def determine_capital_release_params(
        self, de_risk_score: float, unwind_urgency: float = 0.5
    ) -> Dict[str, Any]:
        """
        Maps de-risk score and unwind urgency into UnwindParams values.
        unwind_urgency (0–1) from signal engine.
        """
        base_trigger = max(0.05, 0.40 - (de_risk_score / 200.0))
        trigger_pct  = max(0.05, base_trigger * (1.0 - unwind_urgency * 0.7))

        if de_risk_score < 40 and unwind_urgency < 0.3:
            max_shares = 200
        elif unwind_urgency > 0.7 or de_risk_score > 70:
            max_shares = 750
        else:
            max_shares = 400

        params = {
            "share_reduction_trigger_pct": trigger_pct,
            "max_shares_per_month":        max_shares,
        }
        self._log_decision("MAP_UNWIND_PARAMS", {
            "de_risk_score":  round(de_risk_score, 2),
            "unwind_urgency": round(unwind_urgency, 3),
            "trigger_pct":    round(trigger_pct, 4),
            "max_shares":     max_shares,
            "mapped_params":  params,
        })
        return params

    def determine_allocations(self, released_cash: float) -> Dict[str, float]:
        """Deterministic split based on income preference."""
        income_weight  = self.income_preference / 100.0
        alloc_income   = released_cash * income_weight
        alloc_model    = released_cash * (1.0 - income_weight)

        self._log_decision("SPLIT_RELEASED_CAPITAL", {
            "released_cash":        released_cash,
            "income_preference_pct": self.income_preference,
            "allocation_to_income": alloc_income,
            "allocation_to_model":  alloc_model,
        })
        return {"income": alloc_income, "model": alloc_model}

    def _build_signals(self, signals: Dict[str, Any]) -> List[SignalInput]:
        """
        Convert raw signal dict from signal_engine into typed SignalInput list
        for DecisionService.

        Signal engine output keys (frozen contract in signal_engine.py):
          momentum_score  : float  [-1.0, 1.0]
          macro_regime    : str    "risk_on" | "neutral" | "risk_off"
          volatility_level: str    "low" | "medium" | "high"
          unwind_urgency  : float  [0.0, 1.0]

        Mapping to numeric SignalInput:
          momentum_score  → raw float, threshold=0.5, direction="below"
                            (pass if momentum <= 0.5 — not strongly bullish)
          macro_regime    → encoded: risk_on=1.0, neutral=0.5, risk_off=0.0
                            threshold=0.6, direction="below"
                            (pass if not risk_on; risk_on blocks unwind)
          volatility_level → encoded: low=0.2, medium=0.5, high=1.0
                            threshold=0.8, direction="below"
                            (pass unless high vol)
        """
        signal_inputs: List[SignalInput] = []

        # ── Momentum ──────────────────────────────────────────────────
        momentum = signals.get("momentum_score")
        if momentum is not None:
            momentum = float(momentum)
            signal_inputs.append(SignalInput(
                signal_name="momentum",
                raw_value=momentum,
                threshold=0.5,
                direction="below",
                note=(
                    f"Momentum {momentum:.3f} — "
                    + ("allowing unwind." if momentum <= 0.5 else "strongly bullish, protecting upside.")
                ),
            ))

        # ── Macro regime ──────────────────────────────────────────────
        # signal_engine returns a string; encode to float for DecisionService
        macro_regime = signals.get("macro_regime")
        if macro_regime is not None:
            macro_score = {"risk_on": 1.0, "neutral": 0.5, "risk_off": 0.0}.get(
                str(macro_regime), 0.5
            )
            signal_inputs.append(SignalInput(
                signal_name="macro",
                raw_value=macro_score,
                threshold=0.6,   # block only when risk_on (1.0 > 0.6)
                direction="below",
                note=(
                    f"Macro regime '{macro_regime}' (encoded={macro_score:.1f}) — "
                    + ("risk-on, blocking unwind." if macro_score > 0.6 else "allowing unwind.")
                ),
            ))

        # ── Volatility ────────────────────────────────────────────────
        # signal_engine returns a string; encode to float for DecisionService
        vol_level = signals.get("volatility_level")
        if vol_level is not None:
            vol_score = {"low": 0.2, "medium": 0.5, "high": 1.0}.get(
                str(vol_level), 0.5
            )
            signal_inputs.append(SignalInput(
                signal_name="volatility",
                raw_value=vol_score,
                threshold=0.8,   # block only when high (1.0 > 0.8)
                direction="below",
                note=(
                    f"Volatility '{vol_level}' (encoded={vol_score:.1f}) — "
                    + ("extreme vol, blocking unwind." if vol_score > 0.8 else "acceptable.")
                ),
            ))

        return signal_inputs

    def _resolve_client_constraint(self) -> ClientConstraint:
        """
        Map PortfolioState client constraint string to ClientConstraint enum.
        Defaults to SELL_OPTIONAL if not set or unrecognised.
        """
        raw = getattr(self.state, "client_constraint", "SELL_OPTIONAL")
        try:
            return ClientConstraint(raw)
        except ValueError:
            trace_log(f"[ORCHESTRATOR] Unknown client_constraint='{raw}', defaulting to SELL_OPTIONAL")
            return ClientConstraint.SELL_OPTIONAL


# ---------------------------------------------------------------------------
# Main orchestrator entrypoint
# ---------------------------------------------------------------------------

def run_portfolio_cycle(
    state: PortfolioState,
    ticker: str,
    start_date: str,
    end_date: str,
    initial_shares: float,
    unwind_cost_basis: float = 100.0,
    income_preference: float = 50.0,
    prices: Dict[str, float] = None,
    available_cash: float = None,
    month: int = 0,
) -> Dict[str, Any]:
    """
    Main orchestrator entrypoint. Sequential logic flow:

      1. Initialize orchestrator + OptionsLedger
      2. Generate signals
      3. Run CP engine (covered call overlay → option events → tlh_delta_reported)
      4. Mark open positions for UI
      5. Build DecisionInput from CP engine output + OptionsLedger state
      6. DecisionService.evaluate() → DecisionResult
      7. Emit sell trade intent if enable_unwind
      8. Route released capital → income / model sleeves
      9. Emit buy intents
     10. Log and return

    State mutation: NONE. All portfolio changes are emitted as trade intents
    for the Execution Layer. (Architecture Contract v2.)
    """
    prices = prices or {}
    trades: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # 1. Initialize
    # ------------------------------------------------------------------
    orch           = PortfolioOrchestrator(state, income_preference)
    options_ledger = OptionsLedger(underlying=ticker)

    # Restore open option state from PortfolioState if present
    # (allows OptionsLedger to survive across monthly steps)
    existing_open_option = getattr(state, "open_option", None)
    if existing_open_option is not None:
        try:
            import pandas as pd
            options_ledger.open(
                underlying=ticker,
                strike=float(existing_open_option.strike),
                written_date=existing_open_option.open_date.date()
                    if hasattr(existing_open_option.open_date, 'date')
                    else existing_open_option.open_date,
                expiry_date=existing_open_option.expiry_date.date()
                    if hasattr(existing_open_option.expiry_date, 'date')
                    else existing_open_option.expiry_date,
                shares_encumbered=int(existing_open_option.covered_shares),
                premium_open_per_share=float(existing_open_option.premium_open_per_share),
                position_id=getattr(existing_open_option, "position_id", None),
            )
        except Exception as e:
            trace_log(f"[ORCHESTRATOR] Could not restore open option to ledger: {e}")

    # ------------------------------------------------------------------
    # 2. Generate signals
    # ------------------------------------------------------------------
    from ai_advisory.signals.signal_engine import generate_signals
    price_history = prices.get("__cp_history__", None)
    signals       = generate_signals(state, prices, price_history=price_history)

    unwind_urgency = signals.get("unwind_urgency", 0.0)
    de_risk_score  = orch.determine_de_risk_score()
    unwind_params  = orch.determine_capital_release_params(de_risk_score, unwind_urgency)

    # ------------------------------------------------------------------
    # 3. CP engine — covered call overlay only
    # ------------------------------------------------------------------
    trace_log("--- [MODULE 3] STRATEGY CALL TRACE ---")
    trace_log("-> CALLED: CP Strategy Engine (StrategyUnwindEngine.run_covered_call_overlay)")
    orch._log_decision("INVOKE_CONCENTRATED_ENGINE", {
        "action": "Start", "initial_shares": initial_shares
    })

    cp_engine = StrategyUnwindEngine(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
        initial_shares=initial_shares,
    )

    res_cp     = cp_engine.run_covered_call_overlay(
        options_ledger=options_ledger,
        coverage_pct=50.0,
        target_dte_days=30,
        target_delta=0.20,
        profit_capture_pct=0.50,
        cost_basis=unwind_cost_basis,
        starting_cash=state.cash,
        initial_state=state,
    )
    cp_summary = res_cp["summary"]

    # ------------------------------------------------------------------
    # 4. Mark open positions for UI (after expiry evaluation)
    # ------------------------------------------------------------------
    current_price = cp_summary.get("ending_price", 0.0)
    if current_price > 0 and options_ledger.has_open_position():
        options_ledger.mark_open_positions(
            current_price=current_price,
            volatility=cp_engine.estimate_volatility(),
            risk_free_rate=cp_engine.risk_free_rate,
            current_date=_date.today(),
            bs_call_fn=cp_engine.black_scholes_call,
        )

    # Snapshot for UI — encumbered shares, marks, DTE
    ledger_snapshot = options_ledger.state_snapshot(
        total_shares=int(state.shares),
        current_date=_date.today(),
    )

    # ------------------------------------------------------------------
    # 5. Build DecisionInput
    #
    #    free_shares          = OptionsLedger.free_shares() — excludes encumbered
    #    tlh_delta_this_step  = tlh generated by option events this step
    #    signals              = typed SignalInput list from signal engine
    #    client_constraint    = from PortfolioState (NO_SELL / SELL_OPTIONAL / SELL_REQUIRED)
    # ------------------------------------------------------------------
    tlh_delta_this_step = cp_summary.get("tlh_delta_reported", 0.0)
    tlh_inventory       = getattr(state, "tlh_inventory", 0.0)
    free_shares         = options_ledger.free_shares(int(state.shares))

    signal_inputs       = orch._build_signals(signals)
    client_constraint   = orch._resolve_client_constraint()

    price_trigger = (
        unwind_cost_basis * (1.0 + unwind_params["share_reduction_trigger_pct"])
        if unwind_cost_basis > 0
        else None
    )

    decision_input = DecisionInput(
        shares_held         = int(state.shares),
        free_shares         = free_shares,
        cost_basis          = float(unwind_cost_basis),
        current_price       = float(current_price),
        tlh_inventory       = float(tlh_inventory),
        tlh_delta_this_step = float(tlh_delta_this_step),
        position_pct        = float(state.concentration_pct),
        client_constraint   = client_constraint,
        unwind_params       = UnwindParams(
            max_shares_per_month        = int(unwind_params["max_shares_per_month"]),
            concentration_threshold_pct = 0.15,
            price_trigger               = price_trigger,
        ),
        signals             = signal_inputs,
        risk_score          = int(round(state.risk_score)),
    )

    trace_log("[DECISION INPUT]")
    trace_log(f"shares_held={decision_input.shares_held} free_shares={free_shares} "
              f"encumbered={ledger_snapshot['encumbered_shares']}")
    trace_log(f"tlh_inventory={tlh_inventory:.0f} tlh_delta_this_step={tlh_delta_this_step:.0f} "
              f"tlh_working={decision_input.tlh_working:.0f}")
    trace_log(f"client_constraint={client_constraint.value}")

    # ------------------------------------------------------------------
    # 6. DecisionService.evaluate()
    # ------------------------------------------------------------------
    decision_svc    = DecisionService()
    decision_result = decision_svc.evaluate(decision_input)

    # Consume pending ledger events (clears queue after tlh_delta was read)
    options_ledger.consume_pending_events()

    trace_log("[DECISION RESULT]")
    trace_log(f"mode={decision_result.mode.value}")
    trace_log(f"enable_unwind={decision_result.enable_unwind}")
    trace_log(f"shares_to_sell={decision_result.shares_to_sell}")
    if decision_result.blocking_reason:
        trace_log(f"blocking_reason={decision_result.blocking_reason}")

    orch._log_decision("DECISION_SERVICE_RESULT", {
        "mode":             decision_result.mode.value,
        "enable_unwind":    decision_result.enable_unwind,
        "shares_to_sell":   decision_result.shares_to_sell,
        "blocking_reason":  decision_result.blocking_reason,
        "decision_trace":   decision_result.decision_trace,
    })

    # ------------------------------------------------------------------
    # 7. Emit sell trade intent
    # ------------------------------------------------------------------
    shares_sold      = 0
    proceeds_from_sales = 0.0

    if decision_result.enable_unwind and decision_result.final_shares > 0:
        shares_sold = decision_result.final_shares
        proceeds_from_sales = shares_sold * current_price

        trades.append({
            "symbol":         ticker,
            "side":           "SELL",
            "quantity":       shares_sold,
            "price_override": current_price,
        })
        trace_log(f"[SELL INTENT] {shares_sold} shares @ ${current_price:.2f} = ${proceeds_from_sales:,.0f}")

    orch._log_decision("UNWIND_COMPLETE", {
        "shares_sold":                  shares_sold,
        "cash_released_from_liquidation": proceeds_from_sales,
    })

    # Option cash flow (premium collected - buyback cost from CP engine)
    option_income_this_step = cp_summary.get("cash_delta", 0.0)

    # ------------------------------------------------------------------
    # 8. Route released capital → income / model sleeves
    # ------------------------------------------------------------------
    available_capital = state.cash + proceeds_from_sales + option_income_this_step
    allocs            = orch.determine_allocations(available_capital)

    # Capital constraint: cap allocations to what's actually available
    requested_total = allocs["income"] + allocs["model"]
    scale_factor    = 1.0
    if requested_total > available_capital and requested_total > 0:
        scale_factor         = available_capital / requested_total
        allocs["income"]    *= scale_factor
        allocs["model"]     *= scale_factor

    trace_log("[CAPITAL CONSTRAINT]")
    trace_log(f"Month: {month}")
    trace_log(f"Requested: {requested_total:.2f}")
    trace_log(f"Available: {available_capital:.2f}")
    trace_log(f"Scale Factor: {scale_factor:.4f}")

    # ------------------------------------------------------------------
    # 9. Emit buy intents — income sleeve
    # ------------------------------------------------------------------
    income_weights: Dict[str, float] = {}
    if allocs["income"] > 0.01:
        trace_log("-> CALLED: Income Strategy Engine (AnchorIncomeEngine)")
        orch._log_decision("INVOKE_INCOME_ENGINE", {"capital_injected": allocs["income"]})

        inc_engine     = AnchorIncomeEngine(
            start_date=start_date,
            end_date=end_date,
            initial_capital=allocs["income"],
            reinvest_pct=100.0,
        )
        income_weights = inc_engine.parking_lot_target_weights

        for t, w in income_weights.items():
            if w > 0.0 and prices.get(t, 0) > 0:
                trades.append({
                    "symbol":   t,
                    "side":     "BUY",
                    "quantity": (allocs["income"] * w) / prices[t],
                })

    # ------------------------------------------------------------------
    # 9b. Emit buy intents — model portfolio sleeve
    # ------------------------------------------------------------------
    model_weights: Dict[str, float] = {}
    if allocs["model"] > 0.01:
        trace_log("-> CALLED: Model Strategy Engine (frontier portfolio)")
        orch._log_decision("INVOKE_MODEL_PORTFOLIO_ENGINE", {"capital_injected": allocs["model"]})

        model_weights = _get_frontier_weights(
            risk_score=int(round(state.risk_score)),
            as_of=start_date[:10],
            model_id="core",
        )
        trace_log(f"-> Frontier weights: {model_weights}")

        for t, w in model_weights.items():
            if w > 0.0 and prices.get(t, 0) > 0:
                trades.append({
                    "symbol":   t,
                    "side":     "BUY",
                    "quantity": (allocs["model"] * w) / prices[t],
                })

    # ------------------------------------------------------------------
    # 10. Assemble output
    # ------------------------------------------------------------------
    orch._log_decision("ORCHESTRATION_CYCLE_COMPLETE", {
        "capital_released": proceeds_from_sales,
    })

    purchases   = allocs["income"] + allocs["model"]
    cash_delta  = proceeds_from_sales + option_income_this_step - purchases

    orch_summary = {
        "status":                 "success",
        "cash_delta":             cash_delta,
        "capital_released":       proceeds_from_sales,
        "allocation_to_income":   allocs["income"],
        "allocation_to_model":    allocs["model"],
        "income_weights":         income_weights,
        "model_weights":          model_weights,
        "true_final_ecosystem_value": cp_summary.get("final_portfolio_value", 0.0),  # compat

        # DecisionService outputs — readable by UI trace panel
        "decision_mode":          decision_result.mode.value,
        "shares_to_sell":         decision_result.final_shares,
        "enable_unwind":          decision_result.enable_unwind,
        "blocking_reason":        decision_result.blocking_reason,
        "decision_trace":         decision_result.decision_trace,
        "signal_verdicts":        [
            {
                "signal":    v.signal_name,
                "value":     v.raw_value,
                "threshold": v.threshold,
                "passed":    v.passed,
                "note":      v.note,
            }
            for v in decision_result.signal_verdicts
        ],

        # TLH reporting (read-only; inventory managed by DecisionService)
        "tlh_delta_this_step":    tlh_delta_this_step,
        "tlh_inventory_prior":    tlh_inventory,
        "tlh_working":            decision_input.tlh_working,

        # OptionsLedger UI data
        "ledger_snapshot":        ledger_snapshot,
        "option_income":          option_income_this_step,
        "option_pnl":             cp_summary.get("net_option_result", 0.0),
    }

    return {
        "trades":       trades,
        "orch_summary": orch_summary,
        "decision_log": orch.decision_log,
        "nested_reports": {
            "concentrated_position": res_cp,
            "income":                None,
            "model_portfolio":       None,
        },
        "metadata": {
            "concentrated_position": res_cp,
            "income":                None,
            "model_portfolio":       None,
        },
    }
