from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .http_models import ProgramSignal, SignalAction, ProgramKey
from .http_models import SignalSeverity  # type alias Literal
from .http_models import ClientProfile


def _position_value(p) -> float:
    """
    Best-effort value proxy until we have prices:
    - cost_basis * shares if cost_basis exists
    - else shares (fallback)
    """
    try:
        if getattr(p, "cost_basis", None) is not None:
            return float(p.cost_basis) * float(p.shares)
    except Exception:
        pass
    return float(getattr(p, "shares", 0.0))


def compute_signals(profile: ClientProfile) -> List[ProgramSignal]:
    signals: List[ProgramSignal] = []

    # ----------------------------
    # Risk Reduction: concentration breach
    # ----------------------------
    thresh = getattr(profile, "concentration_threshold_pct", None)
    positions = getattr(profile, "positions", None) or []

    if thresh is not None and positions:
        vals = [(_position_value(p), p) for p in positions]
        total = sum(v for v, _ in vals) or 0.0

        if total > 0:
            max_v, max_p = max(vals, key=lambda t: t[0])
            pct = max_v / total

            if pct >= float(thresh):
                # breach if >= threshold; make "elevated" later if near threshold
                sev: SignalSeverity = "high" if pct >= float(thresh) * 1.10 else "medium"

                sym = getattr(max_p, "symbol", "Position")
                signals.append(
                    ProgramSignal(
                        id=f"sig_conc_{str(sym).lower()}",
                        program="risk_reduction",
                        severity=sev,
                        title="Concentration Alert",
                        message=f"{sym} is above your {int(float(thresh)*100)}% concentration target.",
                        actionable=True,
                        primary_action=SignalAction(label="Review", route="/programs/risk_reduction"),
                    )
                )

    # ----------------------------
    # Tax Optimization: placeholder (until TLH engine emits real signals)
    # ----------------------------
    # Only show if user has positions (so it's not noisy for empty profiles)
    if positions:
        signals.append(
            ProgramSignal(
                id="sig_tax_oppty",
                program="tax_optimization",
                severity="low",
                title="Tax Opportunity",
                message="Potential tax-efficiency opportunities may be available based on your holdings.",
                actionable=True,
                primary_action=SignalAction(label="Review", route="/programs/tax_optimization"),
            )
        )

    # ----------------------------
    # Income Generation: placeholder (until income engine emits real signals)
    # ----------------------------
    if positions:
        signals.append(
            ProgramSignal(
                id="sig_income_event",
                program="income_generation",
                severity="low",
                title="Income Update",
                message="Income strategy is active. Review your income outlook and upcoming events.",
                actionable=True,
                primary_action=SignalAction(label="Review", route="/programs/income_generation"),
            )
        )

    return signals