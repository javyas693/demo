from __future__ import annotations

from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict

# ----------------------------
# Session / Landing
# ----------------------------

class SessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    has_profile: bool
    profile: "ClientProfile"  # forward ref to your existing model


class PositionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str
    shares: float
    cost_basis: Optional[float] = None
    sleeve: str = "core"


class ClientProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cash_to_invest: float = 0.0
    positions: List[PositionIn] = Field(default_factory=list)
    risk_score: Optional[int] = None
    objective: Objective = "growth"
    income_target_annual: Optional[float] = None
    concentration_threshold_pct: float = 0.25


class ProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cash_to_invest: Optional[float] = None
    risk_score: Optional[int] = None
    objective: Optional[Objective] = None
    income_target_annual: Optional[float] = None
    concentration_threshold_pct: Optional[float] = None
    positions: Optional[List[PositionIn]] = None


Objective = Literal["growth", "growth_with_income", "income", "preservation"]

# ----------------------------
# Core profile objects
# ----------------------------

class PositionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str
    shares: float
    cost_basis: Optional[float] = None
    sleeve: str = "core"


class ClientProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cash_to_invest: float = 0.0
    positions: List[PositionIn] = Field(default_factory=list)
    risk_score: Optional[int] = None
    objective: Objective = "growth"
    income_target_annual: Optional[float] = None
    concentration_threshold_pct: float = 0.25


class ProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cash_to_invest: Optional[float] = None
    risk_score: Optional[int] = None
    objective: Optional[Objective] = None
    income_target_annual: Optional[float] = None
    concentration_threshold_pct: Optional[float] = None
    positions: Optional[List[PositionIn]] = None


class OrchestrateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_path: str
    reasons: List[str] = Field(default_factory=list)
    profile: ClientProfile
    result: Dict[str, Any] = Field(default_factory=dict)


# ----------------------------
# Session / Landing
# ----------------------------

class SessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    has_profile: bool
    profile: ClientProfile


# ----------------------------
# Presentation / UI Contracts
# ----------------------------

ConcentrationStatus = Literal["ok", "elevated", "breach"]
SignalSeverity = Literal["low", "medium", "high"]
ProgramKey = Literal["concentrated_position", "risk_reduction", "income_generation", "tax_optimization", "core_allocation"]


class CapitalSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    portfolio_value: float = 0.0
    cash_available: float = 0.0
    largest_holding_symbol: Optional[str] = None
    largest_holding_value: float = 0.0
    concentration_pct: float = 0.0

    concentration_status: ConcentrationStatus = "ok"
    items_require_review: int = 0

    headline: str
    subheadline: str


class SignalAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str
    route: str


class ProgramSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    program: ProgramKey
    severity: SignalSeverity
    title: str
    message: str
    actionable: bool = True
    primary_action: SignalAction


class SignalsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    signals: List[ProgramSignal]


class MetricCard(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str
    value: str
    tag: Optional[str] = None


class ProgramWorkspaceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    program: ProgramKey
    status: Literal["active", "monitoring", "action_required"]
    summary_title: str
    summary_subtitle: str

    summary_cards: List[MetricCard]
    signals: List[ProgramSignal]
    tabs: List[Literal["overview", "allocation", "historical", "future", "trades"]]