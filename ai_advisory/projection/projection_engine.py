from __future__ import annotations
import numpy as np
from typing import Optional
from ai_advisory.projection.defaults import merge_assumptions, fit_cp_assumptions
from ai_advisory.projection.monte_carlo import (
    generate_gbm_paths, extract_percentiles,
    apply_unwind_to_paths, apply_target_unwind_to_paths, combine_sleeve_paths,
)

def run_projection(cp_value, income_value, model_value, cash, cost_basis,
                   current_cp_price, horizon_years,
                   unwind_schedule=None,
                   target_concentration_pct=None,
                   spread_years=5,
                   income_preference=0.5, return_assumptions=None,
                   ticker=None, cp_price_series=None, seed=42):
    assumptions = merge_assumptions(return_assumptions)
    cp_fit = fit_cp_assumptions(ticker or "", cp_price_series)
    if not return_assumptions or (
        "cp_annual_return" not in return_assumptions and
        "cp_annual_vol" not in return_assumptions
    ):
        assumptions["cp_annual_return"] = cp_fit["cp_annual_return"]
        assumptions["cp_annual_vol"]    = cp_fit["cp_annual_vol"]

    n_months    = horizon_years * 12
    n_sims      = int(assumptions["simulations"])
    tax_rate    = float(assumptions["tax_rate"])
    income_frac = float(income_preference)
    model_frac  = 1.0 - income_frac
    rng = np.random.default_rng(seed)

    cp_raw     = generate_gbm_paths(cp_value,     assumptions["cp_annual_return"],
                                    assumptions["cp_annual_vol"],     n_months, n_sims, rng)
    income_raw = generate_gbm_paths(income_value, assumptions["income_annual_return"],
                                    assumptions["income_annual_vol"], n_months, n_sims, rng)
    model_raw  = generate_gbm_paths(model_value,  assumptions["model_annual_return"],
                                    assumptions["model_annual_vol"],  n_months, n_sims, rng)

    if target_concentration_pct is not None:
        # Dynamic per-path unwind: sell each year to close gap toward target
        cp_paths, income_paths, model_paths, proceeds_paths, tax_paths = \
            apply_target_unwind_to_paths(
                cp_raw, income_raw, model_raw, cash,
                target_concentration=float(target_concentration_pct),
                spread_years=int(spread_years),
                n_months=n_months,
                tax_rate=tax_rate,
                cost_basis_per_share=cost_basis,
                current_price=current_cp_price,
                income_annual_return=assumptions["income_annual_return"],
                income_annual_vol=assumptions["income_annual_vol"],
                model_annual_return=assumptions["model_annual_return"],
                model_annual_vol=assumptions["model_annual_vol"],
                income_frac=income_frac,
                model_frac=model_frac,
                rng=rng,
            )
    else:
        # Legacy fixed schedule unwind
        unwind_norm = {int(k): float(v) for k, v in (unwind_schedule or {}).items()
                       if float(v) > 0 and int(k) <= horizon_years}

        cp_paths, proceeds_paths, tax_paths = apply_unwind_to_paths(
            cp_raw, unwind_norm, n_months, tax_rate, cost_basis, current_cp_price)

        income_paths = income_raw.copy()
        model_paths  = model_raw.copy()

        for year, fraction in unwind_norm.items():
            month_idx = year * 12
            if month_idx > n_months:
                continue
            net           = proceeds_paths[:, month_idx]
            income_inject = net * income_frac
            model_inject  = net * model_frac
            remaining     = n_months - month_idx
            if remaining <= 0:
                income_paths[:, month_idx] += income_inject
                model_paths[:,  month_idx] += model_inject
                continue
            income_growth = generate_gbm_paths(
                1.0, assumptions["income_annual_return"],
                assumptions["income_annual_vol"], remaining, n_sims, rng)
            model_growth = generate_gbm_paths(
                1.0, assumptions["model_annual_return"],
                assumptions["model_annual_vol"], remaining, n_sims, rng)
            income_paths[:, month_idx:] += income_inject[:, np.newaxis] * income_growth
            model_paths[:,  month_idx:] += model_inject[:, np.newaxis]  * model_growth

    total_paths   = combine_sleeve_paths(cp_paths, income_paths, model_paths, cash)
    cum_tax_paths = np.cumsum(tax_paths, axis=1)

    cp_pct     = extract_percentiles(cp_paths)
    income_pct = extract_percentiles(income_paths)
    model_pct  = extract_percentiles(model_paths)
    total_pct  = extract_percentiles(total_paths)
    tax_pct    = extract_percentiles(cum_tax_paths)

    annual_snapshots = []
    for year in range(1, horizon_years + 1):
        idx = year * 12
        if idx > n_months:
            break
        cp_p50    = float(cp_pct.p50[idx])
        total_p50 = float(total_pct.p50[idx])
        annual_snapshots.append({
            "year":                    year,
            "total_p10":               round(float(total_pct.p10[idx]), 2),
            "total_p50":               round(total_p50, 2),
            "total_p90":               round(float(total_pct.p90[idx]), 2),
            "cp_p50":                  round(cp_p50, 2),
            "income_p50":              round(float(income_pct.p50[idx]), 2),
            "model_p50":               round(float(model_pct.p50[idx]), 2),
            "cp_remaining_pct":        round(cp_p50 / total_p50 * 100, 1) if total_p50 > 0 else 0.0,
            "cumulative_tax_paid_p50": round(float(tax_pct.p50[idx]), 2),
        })

    def to_list(arr):
        return [round(float(v), 2) for v in arr]

    return {
        "horizon_years":    horizon_years,
        "simulations_run":  n_sims,
        "monthly_steps":    n_months,
        "sleeves": {
            "cp":     {"p10": to_list(cp_pct.p10), "p50": to_list(cp_pct.p50), "p90": to_list(cp_pct.p90)},
            "income": {"p10": to_list(income_pct.p10), "p50": to_list(income_pct.p50), "p90": to_list(income_pct.p90)},
            "model":  {"p10": to_list(model_pct.p10), "p50": to_list(model_pct.p50), "p90": to_list(model_pct.p90)},
            "total":  {"p10": to_list(total_pct.p10), "p50": to_list(total_pct.p50), "p90": to_list(total_pct.p90)},
        },
        "annual_snapshots": annual_snapshots,
        "assumptions_used": {
            "cp_annual_return":      round(assumptions["cp_annual_return"], 4),
            "cp_annual_vol":         round(assumptions["cp_annual_vol"], 4),
            "income_annual_return":  round(assumptions["income_annual_return"], 4),
            "income_annual_vol":     round(assumptions["income_annual_vol"], 4),
            "model_annual_return":   round(assumptions["model_annual_return"], 4),
            "model_annual_vol":      round(assumptions["model_annual_vol"], 4),
            "tax_rate":              assumptions["tax_rate"],
            "reinvest_income":       assumptions["reinvest_income"],
            "simulations":           n_sims,
            "cp_ticker":             ticker or "unknown",
            "cp_assumptions_source": "fitted" if cp_price_series is not None
                                     and len(cp_price_series) >= 60 else "default",
        },
    }
