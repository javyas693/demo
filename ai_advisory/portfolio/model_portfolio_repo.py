from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from .model_portfolio import ModelPortfolio


@dataclass
class ModelPortfolioRepo:
    """
    Phase 1: in-memory registry of canonical model portfolios.
    Later phases can swap this for persisted frontier outputs.
    """
    portfolios: Dict[str, ModelPortfolio]

    def get(self, name: str) -> ModelPortfolio:
        if name not in self.portfolios:
            raise KeyError(f"Unknown model portfolio: {name}")
        return self.portfolios[name]

    def maybe_get(self, name: str) -> Optional[ModelPortfolio]:
        return self.portfolios.get(name)


def default_model_portfolio_repo(frontier_version: str = "frontier_v0") -> ModelPortfolioRepo:
    """
    Provide a couple of canonical portfolios so allocation can reference metadata.
    Numbers are placeholders for Phase 1.5/2 to overwrite with optimizer outputs.
    """
    core_balanced = ModelPortfolio(
        name="core_balanced",
        weights={"VTI": 0.50, "VXUS": 0.25, "BND": 0.25},
        expected_return=0.06,
        volatility=0.12,
        frontier_version=frontier_version,
    )
    core_balanced.validate()

    conservative = ModelPortfolio(
        name="conservative",
        weights={"VTI": 0.30, "VXUS": 0.15, "BND": 0.55},
        expected_return=0.045,
        volatility=0.08,
        frontier_version=frontier_version,
    )
    conservative.validate()

    return ModelPortfolioRepo(
        portfolios={
            core_balanced.name: core_balanced,
            conservative.name: conservative,
        }
    )