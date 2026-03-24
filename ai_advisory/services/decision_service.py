"""
decision_service.py
ai_advisory/services/decision_service.py

Standalone Decision Engine for Concentrated Position Management.

Architectural contracts honored:
  - CP Decision Engine Spec v2:       Deterministic mode selection, TLH rules, sell triggers,
                                       system invariants, full decision traceability.
  - DecisionService Spec v1.0:        DecisionInput/Result/SignalVerdict contracts, trace schema §4,
                                       sell case definitions §5, invariants §8.
  - Strategy Execution Contract:       Returns DecisionResult (intent), never mutates portfolio state.
  - Architecture Contract v2:          Decoupled from CP engine; CP engine owns covered call overlay only.
  - Phase 1 Architecture:              No simulation logic; state is passed in, never derived here.
  - Risk Engine Contract v0.1:         Does not recalculate risk score; accepts pre-scored risk as input.

Decision Modes (CP Decision Engine Spec v2, §4):
  Mode 1 — Income + Harvest   : no selling, TLH generation only
  Mode 2 — Tax-efficient sell : sell only when TLH covers gains and all gates pass
  Mode 3 — Aggressive unwind  : sell up to max_shares_per_month, no TLH constraint (SELL_REQUIRED only)

Sell Cases (DecisionService Spec §5):
  Case 1  Tax-neutral sell    : min(max_shares, floor(tlh_working / gain_per_share))
  Case 2  Forced unwind       : max_shares_per_month, ignores TLH, requires SELL_REQUIRED
  Case 3  No sell             : enable_unwind=False, blocking_reason populated

OptionsLedger integration (session contract):
  DecisionInput.free_shares  — supplied by OptionsLedger.free_shares(total_shares)
                                Prevents selling encumbered shares.
  DecisionInput.tlh_delta_this_step — tlh_delta from OptionsLedger events this step,
                                      forwarded by orchestrator before calling evaluate().
                                      Working TLH = tlh_inventory + tlh_delta_this_step.

gate_overrides (Phase 6):
  DecisionInput.gate_overrides — dict mapping gate name → "suppress".
  "suppress" forces passed=True for that gate, bypassing the normal formula.
  Valid keys: any GATE name that appears in the decision trace
  (MOMENTUM_GATE, MACRO_GATE, VOLATILITY_GATE, PRICE_TRIGGER_GATE,
   CONCENTRATION_GATE, TLH_CAPACITY_GATE, UNREALIZED_GAIN_GATE).
  The override is recorded in the trace for full auditability.
  Client constraint (CLIENT_CONSTRAINT / NO_SELL) is NEVER overridable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, TypedDict


# ---------------------------------------------------------------------------
# Decision Trace schema (DecisionService Spec §4)
# ---------------------------------------------------------------------------

class TraceEntry(TypedDict, total=False):
    rule:            str
    value:           Any
    threshold:       Any
    passed:          bool
    note:            str
    enable_unwind:   bool
    shares_to_sell:  int
    blocking_reason: Optional[str]


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ClientConstraint(str, Enum):
    NO_SELL       = "NO_SELL"
    SELL_OPTIONAL = "SELL_OPTIONAL"
    SELL_REQUIRED = "SELL_REQUIRED"


class DecisionMode(str, Enum):
    INCOME_AND_HARVEST = "MODE_1_INCOME_AND_HARVEST"
    TAX_EFFICIENT_SELL = "MODE_2_TAX_EFFICIENT_SELL"
    AGGRESSIVE_UNWIND  = "MODE_3_AGGRESSIVE_UNWIND"


# ---------------------------------------------------------------------------
# Input contracts
# ---------------------------------------------------------------------------

@dataclass
class SignalInput:
    signal_name: str
    raw_value:   float
    threshold:   float
    weight:      float = 1.0
    direction:   str   = "below"
    override:    Optional[bool] = None
    note:        Optional[str]  = None


@dataclass
class UnwindParams:
    max_shares_per_month:         int
    concentration_threshold_pct:  float
    price_trigger:                Optional[float] = None
    urgency_override:             Optional[int]   = None


@dataclass
class DecisionInput:
    """
    Full input bundle consumed by DecisionService.evaluate().

    gate_overrides (Phase 6):
        Dict mapping gate name to "suppress".
        Suppressed gates are forced to passed=True and annotated in the trace.
        CLIENT_CONSTRAINT is never suppressible — it is checked before gate_overrides
        are consulted and raises ValueError if suppression is attempted.

        Example:
            gate_overrides={"MACRO_GATE": "suppress", "MOMENTUM_GATE": "suppress"}

    All other fields are unchanged from the original contract.
    """
    shares_held:          int
    cost_basis:           float
    current_price:        float
    tlh_inventory:        float
    position_pct:         float
    client_constraint:    ClientConstraint
    unwind_params:        UnwindParams
    free_shares:          int   = 0
    tlh_delta_this_step:  float = 0.0
    signals:              List[SignalInput] = field(default_factory=list)
    risk_score:           Optional[int]    = None
    extra:                Dict[str, Any]   = field(default_factory=dict)
    # Phase 6 — gate suppression for what-if runs
    gate_overrides:       Dict[str, str]   = field(default_factory=dict)

    @property
    def tlh_working(self) -> float:
        return self.tlh_inventory + self.tlh_delta_this_step

    @property
    def sellable_shares(self) -> int:
        return min(self.shares_held, self.free_shares)

    def is_suppressed(self, gate_name: str) -> bool:
        """
        Returns True if this gate should be force-passed in a what-if run.
        CLIENT_CONSTRAINT suppression raises immediately — it is not negotiable.
        """
        if gate_name == "CLIENT_CONSTRAINT" and gate_name in self.gate_overrides:
            raise ValueError(
                "[INVARIANT] CLIENT_CONSTRAINT cannot be suppressed via gate_overrides. "
                "This constraint is set by the advisor and is never overridable."
            )
        return self.gate_overrides.get(gate_name) == "suppress"


# ---------------------------------------------------------------------------
# Output contracts
# ---------------------------------------------------------------------------

@dataclass
class SignalVerdict:
    signal_name: str
    raw_value:   float
    threshold:   float
    passed:      bool
    weight:      float
    override:    Optional[bool]
    note:        Optional[str]


@dataclass
class DecisionResult:
    enable_unwind:           bool
    shares_to_sell:          int
    final_shares:            int
    mode:                    DecisionMode
    tlh_constrained_max:     Optional[int]
    urgency_constrained_max: int
    signal_verdicts:         List[SignalVerdict]
    decision_trace:          List[TraceEntry]
    blocking_reason:         Optional[str]
    what_if:                 Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# DecisionService
# ---------------------------------------------------------------------------

class DecisionService:
    """
    Deterministic decision engine for concentrated position management.

    Phase 6 addition: gate_overrides on DecisionInput.
    When a gate name is in gate_overrides with value "suppress", the gate is
    force-passed regardless of the actual signal/value. The override is recorded
    in the trace so every what-if run is fully auditable.

    CLIENT_CONSTRAINT is never suppressible. All system invariants still apply.
    """

    # ------------------------------------------------------------------
    # Trace helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _gate(rule: str, value: Any, threshold: Any, passed: bool, note: str) -> TraceEntry:
        return TraceEntry(rule=rule, value=value, threshold=threshold, passed=passed, note=note)

    @staticmethod
    def _final(enable_unwind: bool, shares_to_sell: int, blocking_reason: Optional[str]) -> TraceEntry:
        return TraceEntry(
            rule="FINAL_DECISION",
            enable_unwind=enable_unwind,
            shares_to_sell=shares_to_sell,
            blocking_reason=blocking_reason,
        )

    # ------------------------------------------------------------------
    # Gate suppression helper
    # ------------------------------------------------------------------

    def _maybe_suppress(
        self,
        inp: DecisionInput,
        gate_name: str,
        natural_result: bool,
        natural_note: str,
        trace: List[TraceEntry],
        value: Any = None,
        threshold: Any = None,
    ) -> bool:
        """
        Apply gate_override suppression if configured, otherwise use natural result.

        If suppressed:
          - passed is forced True
          - trace note is annotated with [WHAT-IF SUPPRESSED] so it's visible in the UI
        If not suppressed:
          - trace entry is written with natural result and note
          - natural_result is returned unchanged

        Returns the effective passed value.
        """
        if inp.is_suppressed(gate_name):
            trace.append(self._gate(
                rule=gate_name,
                value=value,
                threshold=threshold,
                passed=True,
                note=f"[WHAT-IF SUPPRESSED] Gate forced open. Original result would have been: {natural_note}",
            ))
            return True

        trace.append(self._gate(
            rule=gate_name,
            value=value,
            threshold=threshold,
            passed=natural_result,
            note=natural_note,
        ))
        return natural_result

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(self, inp: DecisionInput) -> DecisionResult:
        trace: List[TraceEntry] = []

        trace.append(self._gate(
            rule="INPUT_SNAPSHOT",
            value={
                "shares_held":         inp.shares_held,
                "free_shares":         inp.free_shares,
                "sellable_shares":     inp.sellable_shares,
                "cost_basis":          inp.cost_basis,
                "current_price":       inp.current_price,
                "tlh_inventory":       inp.tlh_inventory,
                "tlh_delta_this_step": inp.tlh_delta_this_step,
                "tlh_working":         inp.tlh_working,
                "position_pct":        inp.position_pct,
                "client_constraint":   inp.client_constraint.value,
                "gate_overrides":      inp.gate_overrides,
            },
            threshold=None,
            passed=True,
            note="Raw inputs recorded for deterministic replay.",
        ))

        self._assert_invariants(inp, trace)
        signal_verdicts = self._evaluate_signals(inp.signals, inp.gate_overrides, trace)
        mode, blocking_signal = self._select_mode(inp, signal_verdicts, trace)

        if mode == DecisionMode.INCOME_AND_HARVEST:
            return self._handle_mode1(inp, mode, signal_verdicts, trace, blocking_signal)
        elif mode == DecisionMode.TAX_EFFICIENT_SELL:
            return self._handle_mode2(inp, mode, signal_verdicts, trace)
        elif mode == DecisionMode.AGGRESSIVE_UNWIND:
            return self._handle_mode3(inp, mode, signal_verdicts, trace)

        raise ValueError(f"[FATAL] Unknown decision mode: {mode}")

    # ------------------------------------------------------------------
    # Step 1: Invariants
    # ------------------------------------------------------------------

    def _assert_invariants(self, inp: DecisionInput, trace: List[TraceEntry]) -> None:
        if inp.shares_held < 0:
            raise ValueError(f"[INVARIANT] shares_held={inp.shares_held} is negative.")
        if inp.free_shares < 0:
            raise ValueError(f"[INVARIANT] free_shares={inp.free_shares} is negative.")
        if inp.free_shares > inp.shares_held:
            raise ValueError(
                f"[INVARIANT] free_shares={inp.free_shares} > shares_held={inp.shares_held}."
            )
        if inp.tlh_inventory < 0:
            raise ValueError(f"[INVARIANT] tlh_inventory={inp.tlh_inventory:.4f} is negative.")
        if inp.tlh_delta_this_step < 0:
            raise ValueError(f"[INVARIANT] tlh_delta_this_step={inp.tlh_delta_this_step:.4f} is negative.")
        if inp.cost_basis < 0:
            raise ValueError(f"[INVARIANT] cost_basis={inp.cost_basis:.4f} is negative.")
        if inp.current_price < 0:
            raise ValueError(f"[INVARIANT] current_price={inp.current_price:.4f} is negative.")
        if not (0.0 <= inp.position_pct <= 1.0):
            raise ValueError(f"[INVARIANT] position_pct={inp.position_pct} must be in [0, 1].")

        trace.append(self._gate(
            rule="INVARIANT_CHECK",
            value="all_passed",
            threshold=None,
            passed=True,
            note=(
                f"shares_held={inp.shares_held} free_shares={inp.free_shares} "
                f"tlh_working={inp.tlh_working:.2f} cost_basis={inp.cost_basis:.4f} "
                f"current_price={inp.current_price:.4f} position_pct={inp.position_pct:.4f}"
            ),
        ))

    # ------------------------------------------------------------------
    # Step 2: Signal evaluation — now gate_overrides aware
    # ------------------------------------------------------------------

    def _evaluate_signals(
        self,
        signals: List[SignalInput],
        gate_overrides: Dict[str, str],
        trace: List[TraceEntry],
    ) -> List[SignalVerdict]:
        verdicts: List[SignalVerdict] = []

        if not signals:
            trace.append(self._gate(
                rule="SIGNAL_CHECK",
                value="none_provided",
                threshold=None,
                passed=True,
                note="No signals provided; all signal gates open.",
            ))
            return verdicts

        for sig in signals:
            gate_name = sig.signal_name.upper().replace(" ", "_") + "_GATE"

            # Natural evaluation
            if sig.override is not None:
                natural_passed = sig.override
                natural_note = (
                    f"OVERRIDE applied: passed={natural_passed} "
                    f"(raw={sig.raw_value:.4f}, threshold={sig.threshold:.4f})"
                )
            else:
                if sig.direction == "above":
                    natural_passed = sig.raw_value >= sig.threshold
                elif sig.direction == "below":
                    natural_passed = sig.raw_value <= sig.threshold
                else:
                    natural_passed = sig.raw_value <= sig.threshold
                direction_symbol = "<=" if sig.direction == "below" else ">="
                natural_note = (
                    sig.note or
                    f"raw={sig.raw_value:.4f} {direction_symbol} {sig.threshold:.4f} "
                    f"→ {'PASS' if natural_passed else 'BLOCK'}"
                )

            threshold_label = (
                f"<= {sig.threshold}"
                if sig.direction == "below"
                else f">= {sig.threshold}"
            )

            # Apply gate suppression if configured — annotates trace with [WHAT-IF SUPPRESSED]
            if gate_overrides.get(gate_name) == "suppress":
                effective_passed = True
                trace.append(self._gate(
                    rule=gate_name,
                    value=round(sig.raw_value, 4),
                    threshold=threshold_label,
                    passed=True,
                    note=f"[WHAT-IF SUPPRESSED] Gate forced open. Original result: {natural_note}",
                ))
            else:
                effective_passed = natural_passed
                trace.append(self._gate(
                    rule=gate_name,
                    value=round(sig.raw_value, 4),
                    threshold=threshold_label,
                    passed=effective_passed,
                    note=natural_note,
                ))

            verdicts.append(SignalVerdict(
                signal_name=sig.signal_name,
                raw_value=sig.raw_value,
                threshold=sig.threshold,
                passed=effective_passed,
                weight=sig.weight,
                override=sig.override,
                note=sig.note,
            ))

        passed_count = sum(1 for v in verdicts if v.passed)
        all_passed = passed_count == len(verdicts)
        trace.append(self._gate(
            rule="SIGNAL_SUMMARY",
            value=f"{passed_count}/{len(verdicts)} passed",
            threshold=None,
            passed=all_passed,
            note=f"{passed_count} of {len(verdicts)} signal gates passed.",
        ))
        return verdicts

    # ------------------------------------------------------------------
    # Step 3: Mode selection — structural gates now use _maybe_suppress
    # ------------------------------------------------------------------

    def _select_mode(
        self,
        inp: DecisionInput,
        signal_verdicts: List[SignalVerdict],
        trace: List[TraceEntry],
    ) -> tuple[DecisionMode, Optional[str]]:
        constraint = inp.client_constraint

        # CLIENT_CONSTRAINT — never suppressible (checked inside is_suppressed)
        trace.append(self._gate(
            rule="CLIENT_CONSTRAINT",
            value=constraint.value,
            threshold=None,
            passed=constraint != ClientConstraint.NO_SELL,
            note=(
                "Client allows selling."
                if constraint != ClientConstraint.NO_SELL
                else "NO_SELL: selling permanently blocked regardless of any signal."
            ),
        ))

        if constraint == ClientConstraint.NO_SELL:
            return DecisionMode.INCOME_AND_HARVEST, None

        if constraint == ClientConstraint.SELL_REQUIRED:
            trace.append(self._gate(
                rule="SELL_REQUIRED_GATE",
                value=constraint.value,
                threshold=None,
                passed=True,
                note="SELL_REQUIRED: forced unwind path selected; Mode 3 active.",
            ))
            return DecisionMode.AGGRESSIVE_UNWIND, None

        assert constraint == ClientConstraint.SELL_OPTIONAL

        price_trigger_met = self._eval_price_trigger(inp, trace)
        concentration_met = self._eval_concentration(inp, trace)
        tlh_met           = self._eval_tlh_capacity(inp, trace)
        gain_met          = self._eval_unrealized_gain(inp, trace)

        if not (price_trigger_met and concentration_met and tlh_met and gain_met):
            return DecisionMode.INCOME_AND_HARVEST, None

        # Signal verdicts — already evaluated and annotated in _evaluate_signals.
        # If suppressed there, they will already be passed=True in the verdicts list.
        blocking_signal: Optional[str] = None
        for verdict in signal_verdicts:
            if not verdict.passed:
                gate_name = verdict.signal_name.upper().replace(" ", "_") + "_GATE"
                blocking_signal = gate_name
                trace.append(self._gate(
                    rule="SIGNAL_BLOCK",
                    value=verdict.signal_name,
                    threshold=None,
                    passed=False,
                    note=f"{gate_name} failed — Mode 2 blocked, falling back to Mode 1.",
                ))
                break

        if blocking_signal:
            return DecisionMode.INCOME_AND_HARVEST, blocking_signal

        return DecisionMode.TAX_EFFICIENT_SELL, None

    def _eval_price_trigger(self, inp: DecisionInput, trace: List[TraceEntry]) -> bool:
        trigger = inp.unwind_params.price_trigger
        if trigger is None:
            return self._maybe_suppress(
                inp, "PRICE_TRIGGER_GATE",
                natural_result=True,
                natural_note="No price trigger configured; gate open.",
                trace=trace,
                value=inp.current_price,
                threshold="not configured",
            )
        met = inp.current_price >= trigger
        note = (
            f"Price ${inp.current_price:.4f} >= trigger ${trigger:.4f}."
            if met else
            f"Price ${inp.current_price:.4f} below trigger ${trigger:.4f} — gate blocked."
        )
        return self._maybe_suppress(
            inp, "PRICE_TRIGGER_GATE",
            natural_result=met,
            natural_note=note,
            trace=trace,
            value=round(inp.current_price, 4),
            threshold=trigger,
        )

    def _eval_concentration(self, inp: DecisionInput, trace: List[TraceEntry]) -> bool:
        passed = inp.position_pct >= inp.unwind_params.concentration_threshold_pct
        note = (
            f"{inp.position_pct:.1%} concentrated, above "
            f"{inp.unwind_params.concentration_threshold_pct:.0%} threshold."
            if passed else
            f"{inp.position_pct:.1%} concentrated, below "
            f"{inp.unwind_params.concentration_threshold_pct:.0%} threshold — gate blocked."
        )
        return self._maybe_suppress(
            inp, "CONCENTRATION_GATE",
            natural_result=passed,
            natural_note=note,
            trace=trace,
            value=round(inp.position_pct, 4),
            threshold=inp.unwind_params.concentration_threshold_pct,
        )

    def _eval_tlh_capacity(self, inp: DecisionInput, trace: List[TraceEntry]) -> bool:
        passed = inp.tlh_working > 0.0
        note = (
            f"TLH working balance ${inp.tlh_working:,.2f} available "
            f"(inventory={inp.tlh_inventory:.2f} + delta={inp.tlh_delta_this_step:.2f})."
            if passed else
            "TLH working balance is zero; tax-neutral sell not possible."
        )
        return self._maybe_suppress(
            inp, "TLH_CAPACITY_GATE",
            natural_result=passed,
            natural_note=note,
            trace=trace,
            value=round(inp.tlh_working, 2),
            threshold="> 0",
        )

    def _eval_unrealized_gain(self, inp: DecisionInput, trace: List[TraceEntry]) -> bool:
        gain = inp.current_price - inp.cost_basis
        passed = gain > 0
        note = (
            f"Unrealized gain ${gain:.4f}/share."
            if passed else
            "No unrealized gain; TLH offset not applicable."
        )
        return self._maybe_suppress(
            inp, "UNREALIZED_GAIN_GATE",
            natural_result=passed,
            natural_note=note,
            trace=trace,
            value=round(gain, 4),
            threshold="> 0",
        )

    # ------------------------------------------------------------------
    # Mode handlers — unchanged from original
    # ------------------------------------------------------------------

    def _handle_mode1(
        self,
        inp: DecisionInput,
        mode: DecisionMode,
        signal_verdicts: List[SignalVerdict],
        trace: List[TraceEntry],
        blocking_signal: Optional[str],
    ) -> DecisionResult:
        if blocking_signal:
            reason = (
                f"Mode 1 active: {blocking_signal} blocked the unwind. "
                "Covered call overlay continues for income generation."
            )
        else:
            reason = (
                "Mode 1 active: Income + Harvest. "
                "Sell trigger conditions not met or client does not permit selling."
            )
        trace.append(self._final(enable_unwind=False, shares_to_sell=0, blocking_reason=reason))
        return DecisionResult(
            enable_unwind=False,
            shares_to_sell=0,
            final_shares=0,
            mode=mode,
            tlh_constrained_max=None,
            urgency_constrained_max=inp.unwind_params.max_shares_per_month,
            signal_verdicts=signal_verdicts,
            decision_trace=trace,
            blocking_reason=reason,
        )

    def _handle_mode2(
        self,
        inp: DecisionInput,
        mode: DecisionMode,
        signal_verdicts: List[SignalVerdict],
        trace: List[TraceEntry],
    ) -> DecisionResult:
        gain_per_share = inp.current_price - inp.cost_basis
        trace.append(self._gate(
            rule="GAIN_PER_SHARE_CALC",
            value=round(gain_per_share, 4),
            threshold="> 0",
            passed=gain_per_share > 0,
            note=(
                f"current_price({inp.current_price:.4f}) - "
                f"cost_basis({inp.cost_basis:.4f}) = {gain_per_share:.4f}/share"
            ),
        ))

        if gain_per_share <= 0:
            reason = (
                "Mode 2: No unrealized gain per share; TLH offset not applicable. "
                "Selling deferred until position shows a gain."
            )
            trace.append(self._final(enable_unwind=False, shares_to_sell=0, blocking_reason=reason))
            return DecisionResult(
                enable_unwind=False,
                shares_to_sell=0,
                final_shares=0,
                mode=mode,
                tlh_constrained_max=0,
                urgency_constrained_max=inp.unwind_params.max_shares_per_month,
                signal_verdicts=signal_verdicts,
                decision_trace=trace,
                blocking_reason=reason,
            )

        tlh_constrained_max = math.floor(inp.tlh_working / gain_per_share)
        trace.append(self._gate(
            rule="TLH_SIZING",
            value=tlh_constrained_max,
            threshold="> 0",
            passed=tlh_constrained_max > 0,
            note=(
                f"floor(tlh_working({inp.tlh_working:.2f}) / "
                f"gain_per_share({gain_per_share:.4f})) = {tlh_constrained_max} shares"
            ),
        ))

        urgency_constrained_max = inp.unwind_params.max_shares_per_month
        trace.append(self._gate(
            rule="URGENCY_SIZING",
            value=urgency_constrained_max,
            threshold=None,
            passed=True,
            note=f"max_shares_per_month ceiling = {urgency_constrained_max} shares",
        ))

        trace.append(self._gate(
            rule="FREE_SHARES_GATE",
            value=inp.sellable_shares,
            threshold=inp.shares_held,
            passed=True,
            note=(
                f"sellable_shares={inp.sellable_shares} "
                f"(shares_held={inp.shares_held}, free_shares={inp.free_shares}). "
                "Encumbered shares excluded from sell sizing."
            ),
        ))

        if tlh_constrained_max <= 0:
            reason = (
                f"Mode 2: TLH working balance (${inp.tlh_working:.2f}) is insufficient "
                f"to cover gain on even one share (${gain_per_share:.2f}/share). "
                "Sale blocked until TLH inventory is replenished."
            )
            trace.append(self._final(enable_unwind=False, shares_to_sell=0, blocking_reason=reason))
            return DecisionResult(
                enable_unwind=False,
                shares_to_sell=0,
                final_shares=0,
                mode=mode,
                tlh_constrained_max=0,
                urgency_constrained_max=urgency_constrained_max,
                signal_verdicts=signal_verdicts,
                decision_trace=trace,
                blocking_reason=reason,
            )

        raw_shares     = min(urgency_constrained_max, tlh_constrained_max)
        shares_to_sell = min(raw_shares, inp.sellable_shares)

        if shares_to_sell < raw_shares:
            trace.append(self._gate(
                rule="SELLABLE_SHARES_CAP",
                value=shares_to_sell,
                threshold=inp.sellable_shares,
                passed=True,
                note=(
                    f"Clamped from {raw_shares} → {shares_to_sell} "
                    f"(sellable_shares={inp.sellable_shares}; "
                    f"shares_held={inp.shares_held}, free_shares={inp.free_shares})"
                ),
            ))

        enable_unwind   = shares_to_sell > 0
        blocking_reason = None if enable_unwind else "shares_to_sell resolved to 0 after all constraints."
        trace.append(self._final(
            enable_unwind=enable_unwind,
            shares_to_sell=shares_to_sell,
            blocking_reason=blocking_reason,
        ))
        return DecisionResult(
            enable_unwind=enable_unwind,
            shares_to_sell=shares_to_sell,
            final_shares=shares_to_sell,
            mode=mode,
            tlh_constrained_max=tlh_constrained_max,
            urgency_constrained_max=urgency_constrained_max,
            signal_verdicts=signal_verdicts,
            decision_trace=trace,
            blocking_reason=blocking_reason,
        )

    def _handle_mode3(
        self,
        inp: DecisionInput,
        mode: DecisionMode,
        signal_verdicts: List[SignalVerdict],
        trace: List[TraceEntry],
    ) -> DecisionResult:
        urgency_max = inp.unwind_params.max_shares_per_month

        if inp.unwind_params.urgency_override is not None:
            urgency_pct  = max(0, min(100, inp.unwind_params.urgency_override)) / 100.0
            adjusted_max = math.ceil(urgency_max * urgency_pct)
            trace.append(self._gate(
                rule="URGENCY_OVERRIDE",
                value=inp.unwind_params.urgency_override,
                threshold=None,
                passed=True,
                note=(
                    f"urgency_override={inp.unwind_params.urgency_override} → "
                    f"max_shares_per_month({urgency_max}) × {urgency_pct:.2f} = {adjusted_max}"
                ),
            ))
            urgency_max = adjusted_max

        trace.append(self._gate(
            rule="URGENCY_SIZING",
            value=urgency_max,
            threshold=None,
            passed=True,
            note=f"Mode 3 ceiling: {urgency_max} shares (no TLH constraint applied)",
        ))

        trace.append(self._gate(
            rule="FREE_SHARES_GATE",
            value=inp.sellable_shares,
            threshold=inp.shares_held,
            passed=True,
            note=(
                f"sellable_shares={inp.sellable_shares} "
                f"(shares_held={inp.shares_held}, free_shares={inp.free_shares}). "
                "Encumbered shares excluded even in Mode 3."
            ),
        ))

        shares_to_sell = min(urgency_max, inp.sellable_shares)
        if shares_to_sell < urgency_max:
            trace.append(self._gate(
                rule="SELLABLE_SHARES_CAP",
                value=shares_to_sell,
                threshold=inp.sellable_shares,
                passed=True,
                note=f"Clamped from {urgency_max} → {shares_to_sell} (sellable_shares={inp.sellable_shares})",
            ))

        enable_unwind   = shares_to_sell > 0
        blocking_reason = None if enable_unwind else "No sellable shares; nothing to sell."
        trace.append(self._final(
            enable_unwind=enable_unwind,
            shares_to_sell=shares_to_sell,
            blocking_reason=blocking_reason,
        ))
        return DecisionResult(
            enable_unwind=enable_unwind,
            shares_to_sell=shares_to_sell,
            final_shares=shares_to_sell,
            mode=mode,
            tlh_constrained_max=None,
            urgency_constrained_max=urgency_max,
            signal_verdicts=signal_verdicts,
            decision_trace=trace,
            blocking_reason=blocking_reason,
        )
