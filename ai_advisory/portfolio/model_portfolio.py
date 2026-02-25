from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping


@dataclass(frozen=True)
class ModelPortfolio:
    """
    Canonical model portfolio output used by Capital Brain / Allocation Engine.
    Phase 1 metadata enrichment:
      - expected_return
      - volatility
      - frontier_version
    """
    name: str
    weights: Dict[str, float]  # ticker -> weight (must sum to 1)
    expected_return: float     # annualized (convention), numeric
    volatility: float          # annualized (convention), numeric
    frontier_version: str      # ties back to optimizer inputs/config lineage

    def validate(self) -> None:
        if not self.weights:
            raise ValueError("ModelPortfolio.weights cannot be empty")

        s = sum(float(w) for w in self.weights.values())
        if abs(s - 1.0) > 1e-6:
            raise ValueError(f"ModelPortfolio.weights must sum to 1.0 (got {s})")

        if self.expected_return < -1.0 or self.expected_return > 2.0:
            # keep wide bounds; we just want sanity in Phase 1
            raise ValueError("ModelPortfolio.expected_return looks out of bounds")

        if self.volatility < 0.0 or self.volatility > 3.0:
            raise ValueError("ModelPortfolio.volatility looks out of bounds")

        if not self.frontier_version:
            raise ValueError("ModelPortfolio.frontier_version is required")


@dataclass(frozen=True)
class AssetExposure:
    """
    Asset exposure is a stable abstraction for building custom portfolios without
    hardcoding tickers in the UI layer.

    Example:
      exposures = {"us_equity": 0.6, "intl_equity": 0.2, "core_bond": 0.2}
      mapping   = {"us_equity": "VTI", "intl_equity": "VXUS", "core_bond": "BND"}
      => weights {"VTI":0.6,"VXUS":0.2,"BND":0.2}
    """
    exposures: Dict[str, float]  # exposure_key -> weight (sum to 1)

    def validate(self) -> None:
        if not self.exposures:
            raise ValueError("AssetExposure.exposures cannot be empty")
        s = sum(float(w) for w in self.exposures.values())
        if abs(s - 1.0) > 1e-6:
            raise ValueError(f"AssetExposure.exposures must sum to 1.0 (got {s})")


def build_custom_model_portfolio(
    *,
    name: str,
    asset_exposure: AssetExposure,
    ticker_mapping: Mapping[str, str],   # exposure_key -> user ticker
    expected_return: float,
    volatility: float,
    frontier_version: str,
) -> ModelPortfolio:
    asset_exposure.validate()

    weights: Dict[str, float] = {}
    for exposure_key, w in asset_exposure.exposures.items():
        if exposure_key not in ticker_mapping:
            raise KeyError(f"Missing ticker mapping for exposure '{exposure_key}'")
        ticker = ticker_mapping[exposure_key]
        if not ticker:
            raise ValueError(f"Empty ticker for exposure '{exposure_key}'")
        weights[ticker] = weights.get(ticker, 0.0) + float(w)

    mp = ModelPortfolio(
        name=name,
        weights=weights,
        expected_return=float(expected_return),
        volatility=float(volatility),
        frontier_version=str(frontier_version),
    )
    mp.validate()
    return mp