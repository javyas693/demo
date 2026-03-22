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
    """
    One ordered entry in decision_trace.

    Gate entries:
        rule            str   — rule name, e.g. "MOMENTUM_GATE"
        value           Any   — actual value evaluated
        threshold       Any   — threshold compared against
        passed          bool  — True if the gate allowed the action
        note            str   — human-readable explanation

    FINAL_DECISION entry (always last):
        rule            str   — always "FINAL_DECISION"
        enable_unwind   bool
        shares_to_sell  int
        blocking_reason Optional[str]
    """
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
    """CP Decision Engine Spec v2 §3 — highest-priority constraint."""
    NO_SELL       = "NO_SELL"        # Never sell shares under any circumstances
    SELL_OPTIONAL = "SELL_OPTIONAL"  # Engine decides whether to sell
    SELL_REQUIRED = "SELL_REQUIRED"  # Must attempt selling


class DecisionMode(str, Enum):
    """CP Decision Engine Spec v2 §4."""
    INCOME_AND_HARVEST = "MODE_1_INCOME_AND_HARVEST"
    TAX_EFFICIENT_SELL = "MODE_2_TAX_EFFICIENT_SELL"
    AGGRESSIVE_UNWIND  = "MODE_3_AGGRESSIVE_UNWIND"


# ---------------------------------------------------------------------------
# Input contracts
# ---------------------------------------------------------------------------

@dataclass
class SignalInput:
    """
    A single named signal with its raw value and evaluation metadata.
    Consumed by the engine to produce a SignalVerdict.
    Signals are independently injectable and overridable (spec §7.3).
    """
    signal_name: str
    raw_value:   float
    threshold:   float
    weight:      float = 1.0
    direction:   str   = "below"    # "below" → pass if raw_value <= threshold (e.g. momentum < 0.5)
                                    # "above" → pass if raw_value >= threshold
    override:    Optional[bool] = None   # Explicit override; None = use formula
    note:        Optional[str]  = None


@dataclass
class UnwindParams:
    """
    Parameters governing sell quantity limits.
    Provided by the orchestrator; never derived inside DecisionService.
    """
    max_shares_per_month:         int    # Hard ceiling on shares sold per period
    concentration_threshold_pct:  float  # Gate: sell if position_pct >= this (e.g. 0.15)
    price_trigger:                Optional[float] = None  # Gate: sell only if current_price >= this
    urgency_override:             Optional[int]   = None  # 0–100; scales max_shares in Mode 3


@dataclass
class DecisionInput:
    """
    Full input bundle consumed by DecisionService.evaluate().

    OptionsLedger integration fields:
        free_shares          OptionsLedger.free_shares(total_shares) — shares not encumbered
                             by open covered calls. DecisionService uses this as the ceiling
                             for shares_to_sell, never shares_held directly.
        tlh_delta_this_step  Sum of tlh_delta from OptionsLedger events settled this step.
                             Orchestrator reads pending_events(), sums tlh_delta, passes here.
                             Working TLH = tlh_inventory + tlh_delta_this_step.

    Other fields:
        shares_held          Total shares in the concentrated position (for invariant checks)
        cost_basis           Per-share cost basis (USD)
        current_price        Current mark-to-market price (USD)
        tlh_inventory        Accumulated TLH inventory from prior steps (USD)
        position_pct         Concentration as fraction of total portfolio (0.0–1.0)
        client_constraint    Client's sell permission level
        unwind_params        Sell quantity and trigger parameters
        signals              Optional list of named signal inputs (e.g. momentum, macro)
        risk_score           Pre-computed 1–100 score from Risk Engine — never recalculated here
        extra                Arbitrary pass-through metadata for tracing / replay
    """
    shares_held:          int
    cost_basis:           float
    current_price:        float
    tlh_inventory:        float
    position_pct:         float
    client_constraint:    ClientConstraint
    unwind_params:        UnwindParams
    free_shares:          int   = 0    # from OptionsLedger.free_shares() — defaults 0 for safety
    tlh_delta_this_step:  float = 0.0  # from OptionsLedger events this step
    signals:              List[SignalInput] = field(default_factory=list)
    risk_score:           Optional[int]    = None
    extra:                Dict[str, Any]   = field(default_factory=dict)

    @property
    def tlh_working(self) -> float:
        """
        Working TLH available for this decision step.
        tlh_inventory carries prior balance; tlh_delta_this_step adds what was just
        generated by option events before this evaluation.
        Never negative — enforced by invariant check.
        """
        return self.tlh_inventory + self.tlh_delta_this_step

    @property
    def sellable_shares(self) -> int:
        """
        Shares that can physically be sold this step.
        = min(shares_held, free_shares)
        free_shares excludes shares encumbered by open covered calls.
        """
        return min(self.shares_held, self.free_shares)


# ---------------------------------------------------------------------------
# Output contracts
# ---------------------------------------------------------------------------

@dataclass
class SignalVerdict:
    """
    Output record for a single evaluated signal.
    Rendered as a dial/gauge/bar in the signal dashboard (spec §7.1).
    """
    signal_name: str
    raw_value:   float
    threshold:   float
    passed:      bool
    weight:      float
    override:    Optional[bool]
    note:        Optional[str]


@dataclass
class DecisionResult:
    """
    Output of DecisionService.evaluate().

    Contract (Strategy Execution Contract):
        - This is a TRADE INTENT, not an executed trade.
        - Portfolio state is NEVER mutated here.
        - Orchestrator reads final_shares and emits trade intents to the trade engine.

    Fields:
        enable_unwind            True if any selling should be attempted
        shares_to_sell           Recommended shares (== final_shares, spec §3.2 name)
        final_shares             Spec §3.2 field — always equals shares_to_sell
        mode                     Decision mode selected
        tlh_constrained_max      Max shares TLH can offset (Mode 2 only; None in Mode 1/3)
        urgency_constrained_max  max_shares_per_month ceiling applied
        signal_verdicts          Per-signal evaluation results
        decision_trace           Ordered list of TraceEntry dicts (spec §4 schema)
                                 Last entry is always FINAL_DECISION.
        blocking_reason          Set when enable_unwind=False
        what_if                  Reserved for §7.3 counterfactual replay; always None for now
    """
    enable_unwind:           bool
    shares_to_sell:          int
    final_shares:            int          # spec §3.2 alias — always == shares_to_sell
    mode:                    DecisionMode
    tlh_constrained_max:     Optional[int]
    urgency_constrained_max: int
    signal_verdicts:         List[SignalVerdict]
    decision_trace:          List[TraceEntry]
    blocking_reason:         Optional[str]
    what_if:                 Optional[Dict[str, Any]] = None   # spec §3.2 future field


# ---------------------------------------------------------------------------
# DecisionService
# ---------------------------------------------------------------------------

class DecisionService:
    """
    Deterministic decision engine for concentrated position management.

    Responsibilities:
        1. Validate inputs and enforce system invariants
        2. Evaluate all signals independently → signal_verdicts
        3. Select the correct decision mode (Mode 1 / 2 / 3)
        4. Compute shares_to_sell, enforcing free_shares ceiling from OptionsLedger
        5. Produce a fully auditable DecisionResult with decision_trace

    Non-responsibilities (by contract):
        - CP engine covered-call overlay logic
        - Portfolio state mutation
        - TLH generation (CP engine / OptionsLedger reports tlh_delta; we consume it)
        - Risk score calculation (Risk Engine's domain)
        - Trade execution (trade engine + ledger)
        - OptionsLedger position tracking (OptionsLedger's domain)
    """

    # ------------------------------------------------------------------
    # Trace helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _gate(rule: str, value: Any, threshold: Any, passed: bool, note: str) -> TraceEntry:
        """Build a gate-style TraceEntry (spec §4 schema)."""
        return TraceEntry(rule=rule, value=value, threshold=threshold, passed=passed, note=note)

    @staticmethod
    def _final(enable_unwind: bool, shares_to_sell: int, blocking_reason: Optional[str]) -> TraceEntry:
        """Build the closing FINAL_DECISION TraceEntry (always last in trace)."""
        return TraceEntry(
            rule="FINAL_DECISION",
            enable_unwind=enable_unwind,
            shares_to_sell=shares_to_sell,
            blocking_reason=blocking_reason,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(self, inp: DecisionInput) -> DecisionResult:
        """
        Main entry point.  Deterministic: identical inputs → identical output.

        Processing order (CP Decision Engine Spec v2 §8 flow):
            1.  Record input snapshot for deterministic replay
            2.  Validate inputs and enforce invariants
            3.  Evaluate signals → signal_verdicts
            4.  Select decision mode
            5.  Apply mode-specific sell logic
            6.  Return DecisionResult (inp is never mutated)
        """
        trace: List[TraceEntry] = []

        # Input snapshot — full replay fidelity (spec §9 determinism requirement)
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
            },
            threshold=None,
            passed=True,
            note="Raw inputs recorded for deterministic replay.",
        ))

        # Step 1: invariants
        self._assert_invariants(inp, trace)

        # Step 2: signals
        signal_verdicts = self._evaluate_signals(inp.signals, trace)

        # Step 3: mode selection
        mode, blocking_signal = self._select_mode(inp, signal_verdicts, trace)

        # Step 4: mode handler
        if mode == DecisionMode.INCOME_AND_HARVEST:
            return self._handle_mode1(inp, mode, signal_verdicts, trace, blocking_signal)
        elif mode == DecisionMode.TAX_EFFICIENT_SELL:
            return self._handle_mode2(inp, mode, signal_verdicts, trace)
        elif mode == DecisionMode.AGGRESSIVE_UNWIND:
            return self._handle_mode3(inp, mode, signal_verdicts, trace)

        raise ValueError(f"[FATAL] Unknown decision mode: {mode}")

    # ------------------------------------------------------------------
    # Step 1: Invariant enforcement (CP Spec §10, DecisionService Spec §8)
    # ------------------------------------------------------------------

    def _assert_invariants(self, inp: DecisionInput, trace: List[TraceEntry]) -> None:
        """
        Invariants from CP Decision Engine Spec v2 §10:
            - No negative shares
            - No negative TLH
        Additional invariants from DecisionService Spec §8:
            - free_shares <= shares_held (can't be more free than total)
            - tlh_working never negative
        Raises ValueError immediately; engine must not proceed on bad state.
        """
        if inp.shares_held < 0:
            raise ValueError(f"[INVARIANT] shares_held={inp.shares_held} is negative.")
        if inp.free_shares < 0:
            raise ValueError(f"[INVARIANT] free_shares={inp.free_shares} is negative.")
        if inp.free_shares > inp.shares_held:
            raise ValueError(
                f"[INVARIANT] free_shares={inp.free_shares} > shares_held={inp.shares_held}. "
                "OptionsLedger.free_shares() must never exceed total shares."
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
    # Step 2: Signal evaluation (spec §7.1)
    # ------------------------------------------------------------------

    def _evaluate_signals(
        self,
        signals: List[SignalInput],
        trace: List[TraceEntry],
    ) -> List[SignalVerdict]:
        """
        Evaluate each signal independently.

        - Overrides take absolute precedence over formula result.
        - Each signal produces exactly one TraceEntry (e.g. MOMENTUM_GATE).
        - Verdicts are consumed by _select_mode() to block Mode 2 if any fail.
        - All verdicts stored in DecisionResult for UI signal dashboard (§7.1).
        """
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
            if sig.override is not None:
                passed = sig.override
                note = (
                    f"OVERRIDE applied: passed={passed} "
                    f"(raw={sig.raw_value:.4f}, threshold={sig.threshold:.4f})"
                )
            else:
                if sig.direction == "above":
                    passed = sig.raw_value >= sig.threshold
                elif sig.direction == "below":
                    passed = sig.raw_value <= sig.threshold
                else:
                    passed = sig.raw_value <= sig.threshold  # default: treat as "below"
                direction_symbol = "<=" if sig.direction == "below" else ">="
                note = (
                    sig.note or
                    f"raw={sig.raw_value:.4f} {direction_symbol} {sig.threshold:.4f} "
                    f"→ {'PASS' if passed else 'BLOCK'}"
                )

            # TraceEntry per signal — matches spec §4 example (MOMENTUM_GATE, etc.)
            gate_name = sig.signal_name.upper().replace(" ", "_") + "_GATE"
            threshold_label = (
                f"<= {sig.threshold}"
                if sig.direction == "below"
                else f">= {sig.threshold}"
            )
            trace.append(self._gate(
                rule=gate_name,
                value=round(sig.raw_value, 4),
                threshold=threshold_label,
                passed=passed,
                note=note,
            ))

            verdicts.append(SignalVerdict(
                signal_name=sig.signal_name,
                raw_value=sig.raw_value,
                threshold=sig.threshold,
                passed=passed,
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
    # Step 3: Mode selection
    # ------------------------------------------------------------------

    def _select_mode(
        self,
        inp: DecisionInput,
        signal_verdicts: List[SignalVerdict],
        trace: List[TraceEntry],
    ) -> tuple[DecisionMode, Optional[str]]:
        """
        Mode selection (CP Decision Engine Spec v2 §4 + §3 client constraint priority).

        Priority order:
            1. NO_SELL      → Mode 1, immediately (client constraint is supreme, §3)
            2. SELL_REQUIRED → Mode 3, immediately (forced unwind)
            3. SELL_OPTIONAL → evaluate all gates in order:
                a. Price trigger gate
                b. Concentration gate
                c. TLH capacity gate
                d. Unrealized gain gate
                e. Signal gates (any failing signal → Mode 1, not Mode 2)
               All must pass → Mode 2. Any failure → Mode 1.

        Returns:
            (mode, blocking_signal_name_or_None)
            blocking_signal is set when a signal is the reason for Mode 1 selection,
            so the trace FINAL_DECISION entry can name the blocking signal.
        """
        constraint = inp.client_constraint

        # CLIENT_CONSTRAINT gate — always first (spec §4 example)
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

        # SELL_OPTIONAL: evaluate all trigger gates
        assert constraint == ClientConstraint.SELL_OPTIONAL

        price_trigger_met = self._eval_price_trigger(inp, trace)
        concentration_met = self._eval_concentration(inp, trace)
        tlh_met           = self._eval_tlh_capacity(inp, trace)
        gain_met          = self._eval_unrealized_gain(inp, trace)

        # All structural gates must pass before checking signals
        if not (price_trigger_met and concentration_met and tlh_met and gain_met):
            return DecisionMode.INCOME_AND_HARVEST, None

        # Signal gates — each failing signal blocks Mode 2 (spec §4 trace example)
        # Signals were already evaluated and logged in _evaluate_signals().
        # Here we check their verdicts for blocking, matching the spec §4 trace:
        #   MOMENTUM_GATE passes=False → FINAL_DECISION blocking_reason="MOMENTUM_GATE"
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
                break   # first failing signal is the blocking reason (deterministic)

        if blocking_signal:
            return DecisionMode.INCOME_AND_HARVEST, blocking_signal

        return DecisionMode.TAX_EFFICIENT_SELL, None

    def _eval_price_trigger(self, inp: DecisionInput, trace: List[TraceEntry]) -> bool:
        """Spec §7 rule 1: price >= trigger. No trigger configured → gate open."""
        trigger = inp.unwind_params.price_trigger
        if trigger is None:
            trace.append(self._gate(
                rule="PRICE_TRIGGER_GATE",
                value=inp.current_price,
                threshold="not configured",
                passed=True,
                note="No price trigger configured; gate open.",
            ))
            return True
        met = inp.current_price >= trigger
        trace.append(self._gate(
            rule="PRICE_TRIGGER_GATE",
            value=round(inp.current_price, 4),
            threshold=trigger,
            passed=met,
            note=(
                f"Price ${inp.current_price:.4f} >= trigger ${trigger:.4f}."
                if met else
                f"Price ${inp.current_price:.4f} below trigger ${trigger:.4f} — gate blocked."
            ),
        ))
        return met

    def _eval_concentration(self, inp: DecisionInput, trace: List[TraceEntry]) -> bool:
        """Concentration gate: position_pct >= threshold."""
        passed = inp.position_pct >= inp.unwind_params.concentration_threshold_pct
        trace.append(self._gate(
            rule="CONCENTRATION_GATE",
            value=round(inp.position_pct, 4),
            threshold=inp.unwind_params.concentration_threshold_pct,
            passed=passed,
            note=(
                f"{inp.position_pct:.1%} concentrated, above "
                f"{inp.unwind_params.concentration_threshold_pct:.0%} threshold."
                if passed else
                f"{inp.position_pct:.1%} concentrated, below "
                f"{inp.unwind_params.concentration_threshold_pct:.0%} threshold — gate blocked."
            ),
        ))
        return passed

    def _eval_tlh_capacity(self, inp: DecisionInput, trace: List[TraceEntry]) -> bool:
        """TLH capacity gate: working TLH > 0 (spec §7 rule 2)."""
        passed = inp.tlh_working > 0.0
        trace.append(self._gate(
            rule="TLH_CAPACITY_GATE",
            value=round(inp.tlh_working, 2),
            threshold="> 0",
            passed=passed,
            note=(
                f"TLH working balance ${inp.tlh_working:,.2f} available "
                f"(inventory={inp.tlh_inventory:.2f} + delta={inp.tlh_delta_this_step:.2f})."
                if passed else
                "TLH working balance is zero; tax-neutral sell not possible."
            ),
        ))
        return passed

    def _eval_unrealized_gain(self, inp: DecisionInput, trace: List[TraceEntry]) -> bool:
        """Unrealized gain gate: current_price > cost_basis."""
        gain = inp.current_price - inp.cost_basis
        passed = gain > 0
        trace.append(self._gate(
            rule="UNREALIZED_GAIN_GATE",
            value=round(gain, 4),
            threshold="> 0",
            passed=passed,
            note=(
                f"Unrealized gain ${gain:.4f}/share."
                if passed else
                "No unrealized gain; TLH offset not applicable."
            ),
        ))
        return passed

    # ------------------------------------------------------------------
    # Mode handlers
    # ------------------------------------------------------------------

    def _handle_mode1(
        self,
        inp: DecisionInput,
        mode: DecisionMode,
        signal_verdicts: List[SignalVerdict],
        trace: List[TraceEntry],
        blocking_signal: Optional[str],
    ) -> DecisionResult:
        """
        Mode 1: Income + Harvest.
        Spec §5 Harvest Strategy: Never sells shares. Generates TLH from option losses.
        Spec §10 invariant: Harvest never sells.
        → Case 3: No sell.
        """
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
        """
        Mode 2: Tax-Efficient Sell.
        Case 1: Tax-neutral sell.
            shares_to_sell = min(max_shares_per_month,
                                 floor(tlh_working / gain_per_share),
                                 sellable_shares)

        sellable_shares = min(shares_held, free_shares) — enforces OptionsLedger boundary.
        TLH rules (CP Spec §6): must never double-count; used only to offset gains.
        """
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

        # Guard: gain <= 0 — TLH offset irrelevant
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

        # Case 1 formula: TLH-constrained max (spec §5 Case 1)
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

        # Log the OptionsLedger free_shares ceiling
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

        # Block if TLH inventory can't cover even one share
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

        # Binding limit: min of all three ceilings
        raw_shares    = min(urgency_constrained_max, tlh_constrained_max)
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

        enable_unwind  = shares_to_sell > 0
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
        """
        Mode 3: Aggressive Unwind.
        Case 2: Forced sell. SELL_REQUIRED only.
            shares_to_sell = min(max_shares_per_month, sellable_shares)
            No TLH constraint. Full capital gains tax owed.

        sellable_shares still applied — cannot sell encumbered shares even in Mode 3.
        Spec §3: SELL_REQUIRED → must attempt selling.
        """
        urgency_max = inp.unwind_params.max_shares_per_month

        # Apply urgency_override scaling if provided
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

        # OptionsLedger free_shares ceiling — applies even in forced mode
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

        # Cannot sell more than sellable (no negative shares invariant, spec §10)
        shares_to_sell = min(urgency_max, inp.sellable_shares)
        if shares_to_sell < urgency_max:
            trace.append(self._gate(
                rule="SELLABLE_SHARES_CAP",
                value=shares_to_sell,
                threshold=inp.sellable_shares,
                passed=True,
                note=(
                    f"Clamped from {urgency_max} → {shares_to_sell} "
                    f"(sellable_shares={inp.sellable_shares})"
                ),
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
            tlh_constrained_max=None,   # not applicable in Mode 3
            urgency_constrained_max=urgency_max,
            signal_verdicts=signal_verdicts,
            decision_trace=trace,
            blocking_reason=blocking_reason,
        )
