from __future__ import annotations

from dataclasses import replace
from typing import List, Tuple

import numpy as np

from .spec import FrontierSpec
from .versioning import compute_frontier_version
from .results import FrontierResult, FrontierPoint
from .returns import compute_implied_mu
from .risk import compute_historical_cov
from .optimizer import solve_min_vol, solve_max_return_under_vol_cap
from .sampling import sample_curve_length_nearest
from .io_xlsx import load_allocation_workbook, load_prices_matrix
from .weights import weights_array_to_tuple
from .postprocess import add_sharpe, pareto_filter, collapse_duplicates

from ai_advisory.core.integrity import stable_hash, validate_frontier_payload


def _build_bounds_list(spec: FrontierSpec, assets: List[str]) -> List[Tuple[float, float]]:
    return [spec.constraints.bounds[t] for t in assets]


def _frontier_grid(min_vol: float, max_vol: float, k: int) -> np.ndarray:
    if k < 2:
        return np.array([min_vol], dtype=float)
    # include endpoints
    return np.linspace(min_vol, max_vol, num=k, dtype=float)


def build_frontier(
    spec: FrontierSpec,
    allocation_xlsx: str,
    prices_xlsx: str,
    allocation_sheet: str = "Sub-Assets",
    prices_sheet: str | None = None,
) -> FrontierResult:
    """
    Build deterministic efficient frontier from:
      - allocation workbook (Asset Class + Sub-Assets)
      - prices workbook

    Current v1:
      - expected returns: implied_v1 (yield - expense + growth defaults)
      - covariance: historical
      - raw frontier: max return under vol cap
      - sampling: curve-length + nearest

    Patch 5:
      - compute input_hash + frontier_hash (persisted by store layer)
      - validate frontier payload integrity (structure / invariants)
    """

    # --- Load inputs
    alloc_wb = load_allocation_workbook(allocation_xlsx)
    alloc_obj = alloc_wb["sub_assets"] if allocation_sheet == "Sub-Assets" else alloc_wb["asset_class"]

    prices_df = load_prices_matrix(prices_xlsx, sheet_name=prices_sheet)

    # intersect assets with available prices
    assets = [t for t in alloc_obj["assets"] if t in prices_df.columns]
    if len(assets) < 2:
        raise ValueError("Not enough overlapping tickers between allocation and prices.")

    # Build a fully-populated spec (metadata maps + bounds) for hashing and later storage
    bounds = {t: alloc_obj["bounds"][t] for t in assets}
    spec2 = FrontierSpec(
        schema_version=spec.schema_version,
        engine_version=spec.engine_version,
        as_of=spec.as_of,
        model_id=spec.model_id,
        universe=replace(spec.universe, assets=assets),
        expected_return=spec.expected_return,
        risk_model=spec.risk_model,
        constraints=replace(spec.constraints, bounds=bounds),
        grid=spec.grid,
        sampling=spec.sampling,
        asset_class_map=alloc_obj["asset_class_map"],
        sub_asset_class_map=alloc_obj["sub_asset_class_map"],
        name_map=alloc_obj["name_map"],
        yield_map=alloc_obj["yield_map"],
        expense_ratio_map=alloc_obj["expense_ratio_map"],
    ).normalized()

    # Patch 5: input fingerprint (determinism + integrity binding)
    # Persisted by store layer (meta.json) along with status transitions.
    input_hash = stable_hash(spec2)

    frontier_version = compute_frontier_version(spec2)

    # --- Compute mu and Sigma
    mu = compute_implied_mu(spec2, assets)
    sigma = compute_historical_cov(prices_df, assets, annualization_factor=spec2.risk_model.annualization_factor)

    # Ensure sigma symmetric numerical
    sigma = 0.5 * (sigma + sigma.T)

    bounds_list = _build_bounds_list(spec2, assets)

    # --- Feasible min-vol portfolio
    w_min = solve_min_vol(sigma, bounds_list)
    min_vol = float(np.sqrt(w_min @ sigma @ w_min))

    # --- Choose max_vol
    # If user set explicit max, use it; else a conservative max based on single-asset vols under bounds.
    if spec2.grid.target_vol_max is not None:
        max_vol = float(spec2.grid.target_vol_max)
    else:
        indiv = np.sqrt(np.maximum(np.diag(sigma), 0.0))
        max_vol = float(max(indiv.max(), min_vol * 2.0))
        if max_vol <= min_vol + 1e-8:
            max_vol = min_vol + 1e-3

    if spec2.grid.target_vol_min is not None:
        min_vol = float(spec2.grid.target_vol_min)

    # --- Build raw frontier
    raw_caps = _frontier_grid(min_vol, max_vol, spec2.grid.grid_points_raw)

    points_raw: List[FrontierPoint] = []
    for i, cap in enumerate(raw_caps):
        w = solve_max_return_under_vol_cap(mu, sigma, float(cap), bounds_list)

        # numerical hygiene
        w = np.clip(w, 0.0, 1.0)
        s = float(w.sum())
        if abs(s) > 1e-12:
            w = w / s

        vol = float(np.sqrt(w @ sigma @ w))
        ret = float(mu @ w)

        points_raw.append(
            FrontierPoint(
                risk_score=i + 1,
                exp_return=ret,
                vol=vol,
                weights=weights_array_to_tuple(w, assets),
            )
        )

    # sort by vol (monotonicization)
    points_raw = sorted(points_raw, key=lambda p: p.vol)

    points_raw = add_sharpe(points_raw, rf_annual=spec2.rf_annual)
    points_raw = pareto_filter(points_raw)
    points_raw = collapse_duplicates(points_raw)

    # --- Sample (curve-length nearest)
    points_sampled = sample_curve_length_nearest(points_raw, n=spec2.sampling.points)

    # relabel risk_score 1..N for sampled set
    points_sampled = [
        FrontierPoint(risk_score=k + 1, exp_return=p.exp_return, vol=p.vol, weights=p.weights)
        for k, p in enumerate(points_sampled)
    ]

    # Patch 5: output integrity + fingerprint
    validate_frontier_payload(points_sampled)

    frontier_hash = stable_hash(
        {
            "frontier_version": frontier_version,
            "assets": assets,
            "points_sampled": points_sampled,
        }
    )

    # NOTE: input_hash/frontier_hash are intentionally not returned yet to avoid changing FrontierResult.
    # Patch 5 persists these in frontier/store/fs_store.py (meta.json) alongside FrontierStatus gating.
    _ = input_hash, frontier_hash  # keep variables "used" without altering return type

    return FrontierResult(
        spec=spec2,
        frontier_version=frontier_version,
        points_raw=points_raw,
        points_sampled=points_sampled,
        assets=tuple(assets),
    )