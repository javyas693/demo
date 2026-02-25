from __future__ import annotations

from dataclasses import dataclass
from typing import List

from ai_advisory.models.definitions import CONSERVATIVE, BALANCED, GROWTH
from ai_advisory.models.model_portfolio import ModelPortfolio


@dataclass(frozen=True)
class RiskBandRule:
    min_score: int
    max_score: int
    model_portfolio: ModelPortfolio


DEFAULT_RULES: List[RiskBandRule] = [
    RiskBandRule(1, 3, CONSERVATIVE),
    RiskBandRule(4, 7, BALANCED),
    RiskBandRule(8, 10, GROWTH),
]


def get_model_portfolio(risk_score: int, rules: List[RiskBandRule] = DEFAULT_RULES) -> ModelPortfolio:
    if not isinstance(risk_score, int):
        raise TypeError("risk_score must be int")
    if risk_score < 1 or risk_score > 10:
        raise ValueError("risk_score must be between 1 and 10")

    for r in rules:
        if r.min_score <= risk_score <= r.max_score:
            mp = r.model_portfolio
            mp.validate()
            return mp

    raise RuntimeError(f"No RiskBandRule matched risk_score={risk_score}")