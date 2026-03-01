from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Literal, Any


@dataclass(frozen=True)
class ExpectedReturnSpec:
    mode: Literal["implied_v1", "historical", "manual", "blended"] = "implied_v1"
    # v1 implied model defaults (editable later in UI)
    asset_class_growth: Dict[str, float] = field(default_factory=lambda: {
        "Equities": 0.050,
        "Fixed Income": 0.010,
        "Real Estate": 0.030,
        "Preferred Stocks": 0.020,
        "Commodities": 0.010,
        "Alternatives": 0.000,
        "Cash": 0.000,
    })
    sub_asset_growth: Dict[str, float] = field(default_factory=lambda: {
        # Equities
        "Large-Cap U.S.": 0.045,
        "Mid-Cap U.S.": 0.055,
        "Small-Cap U.S.": 0.060,
        "Developed Markets": 0.045,
        "Emerging Markets": 0.060,
        # Fixed Income
        "Short-Term Treasury": 0.005,
        "Intermediate Treasury": 0.008,
        "Long-Term Treasury": 0.010,
        "High-Yield Corporate": 0.015,
        "Long-Term Corporate": 0.012,
        "EM Local Currency": 0.020,
    })
    clamp_min: float = -0.05
    clamp_max: float = 0.20


@dataclass(frozen=True)
class RiskModelSpec:
    mode: Literal["historical_cov"] = "historical_cov"
    annualization_factor: int = 252
    min_history_days: int = 252 * 3


@dataclass(frozen=True)
class ConstraintsSpec:
    # bounds in decimals, e.g. 0.00, 0.15
    bounds: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    # Optional future group bounds (asset class caps/floors)
    group_bounds: List[Dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class FrontierGridSpec:
    grid_points_raw: int = 500
    # If None, computed from feasible min/max
    target_vol_min: Optional[float] = None
    target_vol_max: Optional[float] = None


@dataclass(frozen=True)
class SamplingSpec:
    mode: Literal["curve_length", "vol"] = "curve_length"
    method: Literal["nearest"] = "nearest"
    points: int = 100


@dataclass(frozen=True)
class UniverseSpec:
    assets: List[str] = field(default_factory=list)
    ticker_substitutions: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class FrontierSpec:
    schema_version: str = "frontier_spec_v1"
    engine_version: str = "0.2.0-dev"
    as_of: str = ""  # ISO date string "YYYY-MM-DD"
    model_id: str = "core"

    rf_annual: float = 0.0
    rf_tenor: str = "3M"

    universe: UniverseSpec = field(default_factory=UniverseSpec)
    expected_return: ExpectedReturnSpec = field(default_factory=ExpectedReturnSpec)
    risk_model: RiskModelSpec = field(default_factory=RiskModelSpec)
    constraints: ConstraintsSpec = field(default_factory=ConstraintsSpec)
    grid: FrontierGridSpec = field(default_factory=FrontierGridSpec)
    sampling: SamplingSpec = field(default_factory=SamplingSpec)

    # Metadata maps (optional)
    asset_class_map: Dict[str, str] = field(default_factory=dict)
    sub_asset_class_map: Dict[str, str] = field(default_factory=dict)
    name_map: Dict[str, str] = field(default_factory=dict)
    yield_map: Dict[str, float] = field(default_factory=dict)
    expense_ratio_map: Dict[str, float] = field(default_factory=dict)

    def normalized(self) -> "FrontierSpec":
        # Minimal normalization: sort assets and align bounds/maps by key deterministically
        assets = sorted(self.universe.assets)
        bounds = dict(sorted(self.constraints.bounds.items(), key=lambda kv: kv[0]))
        acm = dict(sorted(self.asset_class_map.items(), key=lambda kv: kv[0]))
        sacm = dict(sorted(self.sub_asset_class_map.items(), key=lambda kv: kv[0]))
        nm = dict(sorted(self.name_map.items(), key=lambda kv: kv[0]))
        ym = dict(sorted(self.yield_map.items(), key=lambda kv: kv[0]))
        erm = dict(sorted(self.expense_ratio_map.items(), key=lambda kv: kv[0]))
        subs = dict(sorted(self.universe.ticker_substitutions.items(), key=lambda kv: kv[0]))

        return FrontierSpec(
            schema_version=self.schema_version,
            engine_version=self.engine_version,
            as_of=self.as_of,
            model_id=self.model_id,
            universe=UniverseSpec(assets=assets, ticker_substitutions=subs),
            expected_return=self.expected_return,
            risk_model=self.risk_model,
            constraints=ConstraintsSpec(bounds=bounds, group_bounds=self.constraints.group_bounds),
            grid=self.grid,
            sampling=self.sampling,
            asset_class_map=acm,
            sub_asset_class_map=sacm,
            name_map=nm,
            yield_map=ym,
            expense_ratio_map=erm,
            rf_annual=self.rf_annual,
            rf_tenor=self.rf_tenor,
        )
