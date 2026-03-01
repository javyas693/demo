from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional

@dataclass(frozen=True)
class RiskScoreRequest:
    # group -> option_id (int) OR label (str)
    answers_by_group: Dict[str, Any]
    strict: bool = False

@dataclass(frozen=True)
class RiskScoreResponse:
    risk_score: int
    confidence: float
    drivers: Dict[str, Any]

@dataclass(frozen=True)
class FrontierProposalRequest:
    as_of: str
    model_id: str
    risk_score: int  # 1..100

@dataclass(frozen=True)
class FrontierProposalResponse:
    as_of: str
    model_id: str
    frontier_version: str
    frontier_status: str
    risk_score: int
    exp_return: float
    vol: float
    sharpe: Optional[float]
    target_weights: Dict[str, float]

@dataclass(frozen=True)
class Holding:
    symbol: str
    quantity: Decimal
    sleeve: str = "core"

@dataclass(frozen=True)
class HoldingsSnapshot:
    cash: Decimal
    holdings: List[Holding]

@dataclass(frozen=True)
class TradePreviewRequest:
    proposal: FrontierProposalRequest
    holdings: HoldingsSnapshot
    prices: Dict[str, Decimal]
    min_trade_notional: Decimal = Decimal("250.00")

@dataclass(frozen=True)
class BuyIntentDTO:
    symbol: str
    quantity: Decimal
    price: Decimal
    notional: Decimal

@dataclass(frozen=True)
class TradePreviewResponse:
    intents: List[BuyIntentDTO]
    blocked_reason: Optional[str] = None  # e.g. frontier not approved

@dataclass(frozen=True)
class TradeExecuteRequest(TradePreviewRequest):
    run_id: str = "exec:1"
    user_id: str = "u_123"

@dataclass(frozen=True)
class TradeExecuteResponse:
    intents: List[BuyIntentDTO]
    frontier_version: str
    status_after: str