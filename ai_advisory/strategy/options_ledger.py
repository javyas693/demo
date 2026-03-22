"""
OptionsLedger
=============
ai_advisory/strategy/options_ledger.py

Event-driven options lifecycle tracker. Decoupled from simulation cadence.
Supports daily, weekly, monthly, quarterly, and LEAPS expirations.

Responsibilities (what this file owns):
  - Track every open OptionPosition by ID
  - Evaluate expirations against a supplied current_date
  - Produce OptionExpiryEvent records (status transitions + tlh_delta)
  - Expose free_shares() and encumbered_shares() to feed DecisionService

Boundary contract (what this file NEVER does):
  - Never makes sell decisions
  - Never mutates portfolio shares or cash directly
  - Never reads or writes TLH inventory — only reports tlh_delta per event
  - Never calls DecisionService or Orchestrator
  - Never uses simulation cadence (no df.iterrows loop driving expiry)

Integration contract:
  Caller (CP engine / orchestrator) writes OptionPosition records via open().
  Caller advances time via evaluate_expirations(current_date, current_price).
  DecisionService reads free_shares() before every decision step.
  Orchestrator reads pending_events() and forwards tlh_delta to DecisionService.

Architecture position (DecisionService_Spec §2):
  CP Engine → OptionsLedger.free_shares() → DecisionInput → DecisionService
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class OptionStatus(str, Enum):
    OPEN               = "OPEN"
    EXPIRED_WORTHLESS  = "EXPIRED_WORTHLESS"
    ASSIGNED           = "ASSIGNED"          # ITM at expiry → shares called away
    CLOSED_EARLY       = "CLOSED_EARLY"      # bought back before expiry
    ROLLED             = "ROLLED"            # closed and replaced in same step


class ExpiryOutcome(str, Enum):
    WORTHLESS  = "WORTHLESS"   # OTM at expiry — premium fully kept, no shares lost
    ASSIGNED   = "ASSIGNED"    # ITM at expiry — shares called away at strike
    CLOSED     = "CLOSED"      # bought back early (profit capture / stop / assignment prevent)


# ---------------------------------------------------------------------------
# Core data structures
# ---------------------------------------------------------------------------

@dataclass
class OptionPosition:
    """
    Single covered call position.

    All fields are immutable after creation — the ledger never edits a
    position in place; it only transitions its status via close/expire.
    """
    # Identity
    position_id:            str             # unique, assigned by OptionsLedger.open()

    # Option terms
    underlying:             str             # ticker symbol
    strike:                 float
    expiry_date:            date            # calendar date option expires
    written_date:           date            # date position was opened
    dte_at_open:            int             # DTE on written_date (informational)

    # Size
    shares_encumbered:      int             # shares this contract covers (e.g. 100 per lot)

    # Premium accounting
    premium_open_per_share: float           # Black-Scholes price at open
    premium_open_total:     float           # premium_open_per_share * shares_encumbered

    # Lifecycle
    status:                 OptionStatus = OptionStatus.OPEN

    # Populated on close/expiry
    close_date:             Optional[date]  = None
    close_per_share:        Optional[float] = None   # cost-to-close per share
    close_cost_total:       Optional[float] = None   # cost-to-close total
    close_reason:           Optional[str]   = None   # EXIT_REASON string from CP engine

    # Derived on close (set by ledger, read by orchestrator)
    realized_option_pnl:    Optional[float] = None   # premium_open_total - close_cost_total
    tlh_delta:              Optional[float] = None   # abs(realized_option_pnl) if loss, else 0.0

    # Live mark (set each step by mark_open_positions(); None until first mark)
    current_mark:           Optional[float] = None   # current Black-Scholes value per share
    unrealized_pnl:         Optional[float] = None   # premium_open_total - (current_mark * shares_encumbered)
                                                      # positive = winning (option losing value)
                                                      # negative = losing (option gaining value, short call)

    @property
    def is_open(self) -> bool:
        return self.status == OptionStatus.OPEN

    @property
    def dte_remaining(self) -> int:
        """
        Current DTE is always computed from expiry_date, not from open cadence.
        This is the fix for shares_sold=0: expiry is date-driven, not sim-row-driven.
        """
        today = date.today()  # caller should pass current_date; this is a fallback
        return (self.expiry_date - today).days

    def dte_as_of(self, as_of: date) -> int:
        return (self.expiry_date - as_of).days


@dataclass
class OptionExpiryEvent:
    """
    Produced by OptionsLedger.evaluate_expirations().
    One event per position that transitions status on the given date.

    This is the primary output consumed by the orchestrator and
    forwarded as tlh_delta into DecisionInput.
    """
    position_id:         str
    underlying:          str
    event_date:          date
    outcome:             ExpiryOutcome

    # Option financials
    premium_open_total:  float
    close_cost_total:    float
    realized_option_pnl: float    # signed: positive = income, negative = loss

    # TLH reporting (never negative; 0.0 if position was profitable)
    tlh_delta:           float

    # Shares impact (only non-zero for ASSIGNED)
    shares_called_away:  int      # 0 for WORTHLESS/CLOSED, > 0 for ASSIGNED

    # Full position snapshot (for audit log)
    position:            OptionPosition


# ---------------------------------------------------------------------------
# OptionsLedger
# ---------------------------------------------------------------------------

class OptionsLedger:
    """
    Stateful ledger of all option positions for a single underlying.

    The ledger is the single source of truth for:
      - Which shares are currently encumbered by open calls
      - Which option events have occurred (with tlh_delta per event)
      - free_shares(total_shares) for DecisionService input

    It does NOT:
      - Make sell decisions
      - Mutate portfolio cash or share counts
      - Track TLH inventory (only reports deltas; DecisionService owns inventory)
    """

    def __init__(self, underlying: str):
        self.underlying = underlying

        # Active positions keyed by position_id
        self._open: Dict[str, OptionPosition] = {}

        # Closed/expired positions (full history)
        self._closed: Dict[str, OptionPosition] = {}

        # Events produced this session (not yet consumed by orchestrator)
        self._pending_events: List[OptionExpiryEvent] = []

        # Full event history (all-time, for audit)
        self._event_history: List[OptionExpiryEvent] = []

    # ------------------------------------------------------------------
    # Write API — called by CP engine
    # ------------------------------------------------------------------

    def open(
        self,
        underlying: str,
        strike: float,
        written_date: date,
        expiry_date: date,
        shares_encumbered: int,
        premium_open_per_share: float,
        position_id: Optional[str] = None,
    ) -> OptionPosition:
        """
        Record a newly written covered call.
        Returns the OptionPosition with a ledger-assigned position_id.

        CP engine calls this after computing strike/premium via Black-Scholes.
        """
        if shares_encumbered <= 0:
            raise ValueError(f"shares_encumbered must be > 0, got {shares_encumbered}")
        if strike <= 0:
            raise ValueError(f"strike must be > 0, got {strike}")
        if premium_open_per_share < 0:
            raise ValueError(f"premium_open_per_share must be >= 0, got {premium_open_per_share}")
        if expiry_date <= written_date:
            raise ValueError(
                f"expiry_date {expiry_date} must be after written_date {written_date}"
            )

        dte_at_open = (expiry_date - written_date).days
        if position_id is None:
            position_id = f"OPT-{underlying}-{written_date.isoformat()}-{uuid.uuid4().hex[:8].upper()}"

        pos = OptionPosition(
            position_id=position_id,
            underlying=underlying,
            strike=strike,
            expiry_date=expiry_date,
            written_date=written_date,
            dte_at_open=dte_at_open,
            shares_encumbered=shares_encumbered,
            premium_open_per_share=premium_open_per_share,
            premium_open_total=premium_open_per_share * shares_encumbered,
        )

        self._open[position_id] = pos
        return pos

    def close_early(
        self,
        position_id: str,
        close_date: date,
        close_per_share: float,
        close_reason: str,
    ) -> OptionExpiryEvent:
        """
        Buy back an open position before expiry (profit capture, stop, assignment prevent).
        Called by CP engine when _evaluate_exit_reason() returns a non-EXPIRE reason.

        close_per_share: current Black-Scholes mark used as cost-to-close.
        close_reason: the EXIT_REASON string from _evaluate_exit_reason().
        """
        pos = self._get_open(position_id)

        close_cost_total   = close_per_share * pos.shares_encumbered
        realized_pnl       = pos.premium_open_total - close_cost_total
        tlh_delta          = abs(realized_pnl) if realized_pnl < 0 else 0.0

        pos.status            = OptionStatus.CLOSED_EARLY
        pos.close_date        = close_date
        pos.close_per_share   = close_per_share
        pos.close_cost_total  = close_cost_total
        pos.close_reason      = close_reason
        pos.realized_option_pnl = realized_pnl
        pos.tlh_delta         = tlh_delta

        event = OptionExpiryEvent(
            position_id=position_id,
            underlying=self.underlying,
            event_date=close_date,
            outcome=ExpiryOutcome.CLOSED,
            premium_open_total=pos.premium_open_total,
            close_cost_total=close_cost_total,
            realized_option_pnl=realized_pnl,
            tlh_delta=tlh_delta,
            shares_called_away=0,
            position=pos,
        )

        self._finalize(pos, event)
        return event

    # ------------------------------------------------------------------
    # Expiry evaluation — decoupled from sim cadence
    # ------------------------------------------------------------------

    def evaluate_expirations(
        self,
        current_date: date,
        current_price: float,
    ) -> List[OptionExpiryEvent]:
        """
        Core fix for shares_sold=0.

        Evaluates ALL open positions against current_date.
        Any position whose expiry_date <= current_date is settled now.

        This is date-driven, not sim-row-driven — it runs correctly whether
        the caller advances time daily, weekly, or monthly.

        Returns list of OptionExpiryEvent for all positions settled today.
        Caller (orchestrator) reads tlh_delta from each event and forwards
        it into DecisionInput before calling DecisionService.
        """
        settled: List[OptionExpiryEvent] = []

        for position_id, pos in list(self._open.items()):
            if pos.expiry_date > current_date:
                continue  # not yet expired

            dte = pos.dte_as_of(current_date)  # will be <= 0

            # Determine outcome: ITM (assigned) vs OTM (worthless)
            if current_price > pos.strike:
                outcome          = ExpiryOutcome.ASSIGNED
                new_status       = OptionStatus.ASSIGNED
                # Settlement at intrinsic (standard expiry)
                close_per_share  = max(current_price - pos.strike, 0.0)
                shares_called    = pos.shares_encumbered
            else:
                outcome          = ExpiryOutcome.WORTHLESS
                new_status       = OptionStatus.EXPIRED_WORTHLESS
                close_per_share  = 0.0   # expires worthless — no cost to close
                shares_called    = 0

            close_cost_total    = close_per_share * pos.shares_encumbered
            realized_pnl        = pos.premium_open_total - close_cost_total
            tlh_delta           = abs(realized_pnl) if realized_pnl < 0 else 0.0

            pos.status              = new_status
            pos.close_date          = current_date
            pos.close_per_share     = close_per_share
            pos.close_cost_total    = close_cost_total
            pos.close_reason        = f"EXPIRE_{outcome.value}"
            pos.realized_option_pnl = realized_pnl
            pos.tlh_delta           = tlh_delta

            event = OptionExpiryEvent(
                position_id=position_id,
                underlying=self.underlying,
                event_date=current_date,
                outcome=outcome,
                premium_open_total=pos.premium_open_total,
                close_cost_total=close_cost_total,
                realized_option_pnl=realized_pnl,
                tlh_delta=tlh_delta,
                shares_called_away=shares_called,
                position=pos,
            )

            self._finalize(pos, event)
            settled.append(event)

        return settled

    # ------------------------------------------------------------------
    # Read API — called by DecisionService (via DecisionInput)
    # ------------------------------------------------------------------

    def free_shares(self, total_shares: int) -> int:
        """
        Shares available for a sell decision.

        free_shares = total_shares - encumbered_shares()

        DecisionService reads this before every evaluation step to ensure
        it never instructs the orchestrator to sell shares that are
        currently locked under an open covered call.

        Invariant: always >= 0.
        """
        return max(0, total_shares - self.encumbered_shares())

    def encumbered_shares(self) -> int:
        """
        Total shares currently locked under open covered calls.
        Only counts OPEN positions.
        """
        return sum(pos.shares_encumbered for pos in self._open.values())

    def has_open_position(self) -> bool:
        return len(self._open) > 0

    def open_positions(self) -> List[OptionPosition]:
        return list(self._open.values())

    def closed_positions(self) -> List[OptionPosition]:
        return list(self._closed.values())

    # ------------------------------------------------------------------
    # Event consumption — called by orchestrator
    # ------------------------------------------------------------------

    def pending_events(self) -> List[OptionExpiryEvent]:
        """
        Returns all events not yet consumed by the orchestrator.
        Caller must call consume_pending_events() after processing.
        """
        return list(self._pending_events)

    def consume_pending_events(self) -> List[OptionExpiryEvent]:
        """
        Returns and clears the pending event queue.
        Orchestrator calls this after forwarding tlh_delta to DecisionService.
        """
        events = list(self._pending_events)
        self._pending_events.clear()
        return events

    # ------------------------------------------------------------------
    # Mark-to-market — called by orchestrator each step
    # ------------------------------------------------------------------

    def mark_open_positions(
        self,
        current_price: float,
        volatility: float,
        risk_free_rate: float,
        current_date: date,
        bs_call_fn,
    ) -> None:
        """
        Update current_mark and unrealized_pnl on every open position.

        Call order (orchestrator each step):
            1. evaluate_expirations(current_date, current_price)  — settle expired
            2. mark_open_positions(...)                           — mark survivors
            3. state_snapshot(...)                                — read for UI

        Args:
            current_price   Current underlying price (USD)
            volatility      Annualised implied/realised vol (e.g. 0.35)
            risk_free_rate  Risk-free rate (e.g. 0.04)
            current_date    Today's date — used to compute T (time to expiry in years)
            bs_call_fn      Black-Scholes call pricer from strategy_unwind.py:
                            bs_call_fn(S, K, T, r, sigma) -> float
                            Passed in so the ledger owns no pricing logic.

        Boundary: ledger calls bs_call_fn but never imports strategy_unwind directly.
        """
        for pos in self._open.values():
            dte = pos.dte_as_of(current_date)
            T   = max(dte, 0) / 365.0
            mark_per_share = bs_call_fn(
                current_price,
                pos.strike,
                T,
                risk_free_rate,
                volatility,
            )
            pos.current_mark   = float(mark_per_share)
            pos.unrealized_pnl = float(
                pos.premium_open_total - (mark_per_share * pos.shares_encumbered)
            )



    def state_snapshot(self, total_shares: int, current_date: date) -> dict:
        """
        Full ledger state for audit logging and reconciliation.
        Matches the traceability requirement in DecisionService_Spec §8.
        """
        return {
            "underlying":          self.underlying,
            "as_of_date":          current_date.isoformat(),
            "total_shares":        total_shares,
            "encumbered_shares":   self.encumbered_shares(),
            "free_shares":         self.free_shares(total_shares),
            "open_positions":      len(self._open),
            "closed_positions":    len(self._closed),
            "pending_events":      len(self._pending_events),
            "open_detail": [
                {
                    "position_id":        p.position_id,
                    "strike":             p.strike,
                    "expiry_date":        p.expiry_date.isoformat(),
                    "dte_remaining":      p.dte_as_of(current_date),
                    "shares_encumbered":  p.shares_encumbered,
                    "premium_open_total": p.premium_open_total,
                    "current_mark":       p.current_mark,        # None until mark_open_positions() called
                    "unrealized_pnl":     p.unrealized_pnl,      # None until mark_open_positions() called
                    "pct_encumbered":     round(
                        p.shares_encumbered / total_shares, 4
                    ) if total_shares > 0 else 0.0,
                }
                for p in self._open.values()
            ],
        }

    def cumulative_tlh_generated(self) -> float:
        """
        Sum of all tlh_delta across closed/expired positions.
        Read-only reporting — does not touch TLH inventory (owned by DecisionService).
        """
        return sum(
            (pos.tlh_delta or 0.0)
            for pos in self._closed.values()
        )

    def event_history(self) -> List[OptionExpiryEvent]:
        """Full event history for attribution timeline (DecisionService_Spec §7.4)."""
        return list(self._event_history)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_open(self, position_id: str) -> OptionPosition:
        pos = self._open.get(position_id)
        if pos is None:
            raise KeyError(
                f"Position {position_id} not found in open positions. "
                f"Already closed? Open IDs: {list(self._open.keys())}"
            )
        return pos

    def _finalize(self, pos: OptionPosition, event: OptionExpiryEvent) -> None:
        """Move position from open → closed, register event."""
        self._open.pop(pos.position_id, None)
        self._closed[pos.position_id] = pos
        self._pending_events.append(event)
        self._event_history.append(event)


# ---------------------------------------------------------------------------
# Invariant validation (called by tests + orchestrator health check)
# ---------------------------------------------------------------------------

def assert_ledger_invariants(
    ledger: OptionsLedger,
    total_shares: int,
    current_date: date,
) -> None:
    """
    Validate all system invariants from DecisionService_Spec §8 that
    the OptionsLedger is responsible for.

    Raises AssertionError with descriptive message on any violation.
    Call after every evaluate_expirations() and close_early() in tests.
    """
    # No open position should have expiry_date in the past
    for pos in ledger.open_positions():
        dte = pos.dte_as_of(current_date)
        assert dte > 0, (
            f"INVARIANT VIOLATION: position {pos.position_id} has "
            f"expiry_date {pos.expiry_date} which is in the past as of {current_date}. "
            f"evaluate_expirations() must have been skipped."
        )

    # encumbered_shares never exceeds total_shares
    enc = ledger.encumbered_shares()
    assert enc <= total_shares, (
        f"INVARIANT VIOLATION: encumbered_shares={enc} > total_shares={total_shares}. "
        f"Shares were sold without closing the covering option first."
    )

    # free_shares never negative
    free = ledger.free_shares(total_shares)
    assert free >= 0, (
        f"INVARIANT VIOLATION: free_shares={free} < 0."
    )

    # All closed positions must have tlh_delta >= 0
    for pos in ledger.closed_positions():
        assert (pos.tlh_delta or 0.0) >= 0, (
            f"INVARIANT VIOLATION: position {pos.position_id} has "
            f"tlh_delta={pos.tlh_delta} < 0. TLH delta is always non-negative."
        )

    # No position in both open and closed
    overlap = set(ledger._open.keys()) & set(ledger._closed.keys())
    assert not overlap, (
        f"INVARIANT VIOLATION: position IDs in both open and closed: {overlap}"
    )
