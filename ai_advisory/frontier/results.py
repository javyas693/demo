from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .spec import FrontierSpec


@dataclass(frozen=True)
class FrontierPoint:
    risk_score: int
    exp_return: float
    vol: float
    weights: tuple[float, ...]
    excess_return: float | None = None
    sharpe: float | None = None


@dataclass(frozen=True)
class FrontierResult:
    spec: FrontierSpec
    frontier_version: str
    points_raw: List[FrontierPoint]
    points_sampled: List[FrontierPoint]
    assets: tuple[str, ...] = ()
