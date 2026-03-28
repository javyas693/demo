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


def apply_target_unwind_to_paths(
    cp_paths, income_paths, model_paths, cash,
    target_concentration, spread_years, n_months,
    tax_rate, cost_basis_per_share, current_price,
    income_annual_return, income_annual_vol,
    model_annual_return, model_annual_vol,
    income_frac, model_frac, rng,
):
    """
    Dynamic per-path unwind: each year, sell enough CP to close
    (excess_concentration / years_remaining) of the gap toward target.

    After spread_years, if concentration is still above target (stock ran up),
    sell all excess each year until target is met.
    If concentration is already at or below target, no sell.

    Returns updated (cp_out, income_out, model_out, proceeds_paths, tax_paths).
    """
    n_sims   = cp_paths.shape[0]
    cp_out   = cp_paths.copy()
    inc_out  = income_paths.copy()
    mod_out  = model_paths.copy()
    proceeds = np.zeros_like(cp_paths)
    tax_paid = np.zeros_like(cp_paths)

    basis_ratio = (
        cost_basis_per_share / current_price
        if current_price > 0 and cost_basis_per_share < current_price
        else 0.0
    )

    max_year = n_months // 12

    for year in range(1, max_year + 1):
        month_idx = year * 12
        if month_idx > n_months:
            break

        # Concentration per path at this year-end
        total        = cp_out[:, month_idx] + inc_out[:, month_idx] + mod_out[:, month_idx] + cash
        concentration = np.where(total > 0, cp_out[:, month_idx] / total, 0.0)
        excess        = np.maximum(0.0, concentration - target_concentration)

        # No paths need selling — skip
        if np.all(excess == 0):
            continue

        # Fraction of CP value to sell this year
        if year <= spread_years:
            years_left    = spread_years - year + 1
            sell_fraction = excess / years_left
        else:
            # Past spread window: sell all excess immediately
            sell_fraction = excess

        gross = cp_out[:, month_idx] * sell_fraction
        tax   = gross * (1.0 - basis_ratio) * tax_rate
        net   = gross - tax

        # Reduce CP from this month forward
        scale              = np.where(cp_out[:, month_idx] > 0,
                                      1.0 - sell_fraction, 1.0)
        cp_out[:, month_idx:] *= scale[:, np.newaxis]

        proceeds[:, month_idx] += net
        tax_paid[:, month_idx] += tax

        # Inject net proceeds into income/model sleeves and compound forward
        income_inject = net * income_frac
        model_inject  = net * model_frac
        remaining     = n_months - month_idx

        if remaining > 0:
            income_growth = generate_gbm_paths(
                1.0, income_annual_return, income_annual_vol, remaining, n_sims, rng
            )
            model_growth = generate_gbm_paths(
                1.0, model_annual_return, model_annual_vol, remaining, n_sims, rng
            )
            inc_out[:, month_idx:] += income_inject[:, np.newaxis] * income_growth
            mod_out[:, month_idx:] += model_inject[:, np.newaxis]  * model_growth
        else:
            inc_out[:, month_idx] += income_inject
            mod_out[:, month_idx] += model_inject

    return cp_out, inc_out, mod_out, proceeds, tax_paid
