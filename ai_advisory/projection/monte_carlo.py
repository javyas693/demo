from __future__ import annotations
import numpy as np
from typing import NamedTuple

class PercentiledPaths(NamedTuple):
    p10: np.ndarray
    p50: np.ndarray
    p90: np.ndarray

def generate_gbm_paths(start_value, annual_return, annual_vol, n_months, n_simulations, rng):
    if start_value <= 0:
        return np.zeros((n_simulations, n_months + 1))
    dt      = 1.0 / 12.0
    drift   = (annual_return - 0.5 * annual_vol ** 2) * dt
    diffuse = annual_vol * np.sqrt(dt)
    shocks  = rng.standard_normal((n_simulations, n_months))
    log_returns = drift + diffuse * shocks
    log_cumsum  = np.concatenate(
        [np.zeros((n_simulations, 1)), np.cumsum(log_returns, axis=1)], axis=1
    )
    return start_value * np.exp(log_cumsum)

def extract_percentiles(paths):
    return PercentiledPaths(
        p10=np.percentile(paths, 10, axis=0),
        p50=np.percentile(paths, 50, axis=0),
        p90=np.percentile(paths, 90, axis=0),
    )

def apply_unwind_to_paths(cp_paths, unwind_schedule, n_months, tax_rate, cost_basis_per_share, current_price):
    n_sims   = cp_paths.shape[0]
    cp_after = cp_paths.copy()
    proceeds = np.zeros_like(cp_paths)
    tax_paid = np.zeros_like(cp_paths)
    basis_ratio = (cost_basis_per_share / current_price
                   if current_price > 0 and cost_basis_per_share < current_price else 0.0)
    for year, fraction in unwind_schedule.items():
        if fraction <= 0:
            continue
        month_idx = int(year) * 12
        if month_idx > n_months:
            continue
        gross        = cp_after[:, month_idx] * fraction
        tax          = gross * (1.0 - basis_ratio) * tax_rate
        net_proceeds = gross - tax
        cp_after[:, month_idx:] *= (1.0 - fraction)
        proceeds[:, month_idx]  += net_proceeds
        tax_paid[:, month_idx]  += tax
    return cp_after, proceeds, tax_paid

def combine_sleeve_paths(cp_paths, income_paths, model_paths, cash):
    return cp_paths + income_paths + model_paths + cash
