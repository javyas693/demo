from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from .model_portfolio import ModelPortfolio

# ─────────────────────────────────────────────────────────────────────────────
# Universe definition
# ─────────────────────────────────────────────────────────────────────────────

MODEL_UNIVERSE  = ["VTI", "VXUS", "BND", "TLT"]
INCOME_UNIVERSE = ["JEPQ", "TLTW", "SVOL"]

RETURN_PRIORS: Dict[str, float] = {
    "VTI":  0.085,
    "VXUS": 0.075,
    "BND":  0.040,
    "TLT":  0.035,
    "JEPQ": 0.110,
    "TLTW": 0.120,
    "SVOL": 0.090,
}

DEFAULT_BOUNDS: Dict[str, Tuple[float, float]] = {
    "VTI":  (0.00, 0.70),
    "VXUS": (0.00, 0.40),
    "BND":  (0.00, 0.50),
    "TLT":  (0.00, 0.40),
    "JEPQ": (0.00, 0.40),
    "TLTW": (0.00, 0.30),
    "SVOL": (0.00, 0.20),
}

# ─────────────────────────────────────────────────────────────────────────────
# Risk-score → vol cap
# ─────────────────────────────────────────────────────────────────────────────

def _vol_cap_from_risk_score(risk_score: float) -> float:
    """risk=10→6% vol, risk=50→12%, risk=90→20%."""
    return 0.06 + (risk_score / 100.0) * 0.16


# ─────────────────────────────────────────────────────────────────────────────
# Universe + bounds blended by income_preference
# ─────────────────────────────────────────────────────────────────────────────

def _build_universe_and_bounds(income_preference: float):
    income_w = income_preference / 100.0
    model_w  = 1.0 - income_w
    tickers  = MODEL_UNIVERSE + INCOME_UNIVERSE
    bounds   = []
    for t in tickers:
        lo, hi = DEFAULT_BOUNDS[t]
        if t in INCOME_UNIVERSE:
            hi = min(hi * income_w * 2.0, 0.70)
        else:
            hi = min(hi * (0.3 + model_w * 0.7), 0.70)
        bounds.append((lo, hi))
    mu = np.array([RETURN_PRIORS[t] for t in tickers])
    return tickers, bounds, mu


# ─────────────────────────────────────────────────────────────────────────────
# Covariance matrix from yfinance history
# ─────────────────────────────────────────────────────────────────────────────

def _build_covariance_matrix(tickers: list) -> np.ndarray:
    try:
        import yfinance as yf
        import pandas as pd

        df = yf.download(tickers, period="5y", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            prices = df["Adj Close"] if "Adj Close" in df.columns.levels[0] else df["Close"]
        else:
            prices = df

        monthly = prices.resample("BME").last().pct_change().dropna()
        if len(monthly) < 24:
            raise ValueError("Insufficient history")

        monthly = monthly.reindex(columns=tickers).ffill().bfill().dropna(axis=1)
        available = list(monthly.columns)
        cov_avail = monthly.cov().values * 12.0

        if len(available) == len(tickers):
            return cov_avail

        # Pad missing tickers with default diagonal variance
        full_cov = np.diag([0.04] * len(tickers))
        idx = {t: i for i, t in enumerate(tickers)}
        av_idx = [idx[t] for t in available if t in idx]
        for ii, i in enumerate(av_idx):
            for jj, j in enumerate(av_idx):
                full_cov[i, j] = cov_avail[ii, jj]
        return full_cov

    except Exception:
        # Fallback diagonal covariance
        default_vols = {
            "VTI": 0.15, "VXUS": 0.17, "BND": 0.06, "TLT": 0.14,
            "JEPQ": 0.18, "TLTW": 0.16, "SVOL": 0.12,
        }
        vols = np.array([default_vols.get(t, 0.15) for t in tickers])
        return np.diag(vols ** 2)


# ─────────────────────────────────────────────────────────────────────────────
# Core optimizer call
# ─────────────────────────────────────────────────────────────────────────────

def build_optimized_model_portfolio(
    risk_score: float,
    income_preference: float,
    frontier_version: str = "frontier_v1_live",
) -> ModelPortfolio:
    """
    Real mean-variance optimized ModelPortfolio.
    Driven by risk_score (vol cap) and income_preference (asset universe tilt).
    """
    from ai_advisory.frontier.optimizer import solve_max_return_under_vol_cap

    tickers, bounds, mu = _build_universe_and_bounds(income_preference)
    cov     = _build_covariance_matrix(tickers)
    vol_cap = _vol_cap_from_risk_score(risk_score)

    try:
        raw_weights = solve_max_return_under_vol_cap(
            mu=mu, sigma=cov, vol_cap=vol_cap, bounds=bounds,
        )
    except Exception:
        raw_weights = _fallback_weights(tickers, risk_score, income_preference)

    # Clean up tiny weights and renormalize
    weights_arr = np.where(np.abs(raw_weights) < 1e-4, 0.0, raw_weights)
    total = weights_arr.sum()
    if total <= 0:
        weights_arr = _fallback_weights(tickers, risk_score, income_preference)
        total = weights_arr.sum()
    weights_arr /= total

    weights = {t: float(w) for t, w in zip(tickers, weights_arr) if w > 1e-4}

    w_arr = np.array([weights.get(t, 0.0) for t in tickers])
    expected_return = float(mu @ w_arr)
    realized_vol    = float(np.sqrt(w_arr @ cov @ w_arr))

    if risk_score < 35:
        name = "optimized_conservative"
    elif risk_score < 65:
        name = "optimized_balanced"
    else:
        name = "optimized_aggressive"
    if income_preference >= 60:
        name += "_income"

    mp = ModelPortfolio(
        name=name,
        weights=weights,
        expected_return=expected_return,
        volatility=realized_vol,
        frontier_version=frontier_version,
    )
    mp.validate()
    return mp


def _fallback_weights(tickers: list, risk_score: float, income_preference: float) -> np.ndarray:
    equity_w = risk_score / 100.0
    bond_w   = 1.0 - equity_w
    income_w = income_preference / 100.0
    base = {
        "VTI":  equity_w * (1.0 - income_w) * 0.60,
        "VXUS": equity_w * (1.0 - income_w) * 0.25,
        "BND":  bond_w   * (1.0 - income_w) * 0.70,
        "TLT":  bond_w   * (1.0 - income_w) * 0.30,
        "JEPQ": income_w * 0.45,
        "TLTW": income_w * 0.35,
        "SVOL": income_w * 0.20,
    }
    total = sum(base.values())
    return np.array([base.get(t, 0.0) / max(total, 1e-9) for t in tickers])


# ─────────────────────────────────────────────────────────────────────────────
# Repo (preserves existing .get() interface; adds .get_for_client())
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ModelPortfolioRepo:
    portfolios: Dict[str, ModelPortfolio]

    def get(self, name: str) -> ModelPortfolio:
        if name not in self.portfolios:
            raise KeyError(f"Unknown model portfolio: {name}")
        return self.portfolios[name]

    def maybe_get(self, name: str) -> Optional[ModelPortfolio]:
        return self.portfolios.get(name)

    def get_for_client(self, risk_score: float, income_preference: float) -> ModelPortfolio:
        """
        Primary orchestrator entry point.
        Returns a live-optimized portfolio for exact client parameters.
        Results are cached under a compound key.
        """
        key = f"opt_r{int(risk_score)}_i{int(income_preference)}"
        if key not in self.portfolios:
            self.portfolios[key] = build_optimized_model_portfolio(
                risk_score=risk_score,
                income_preference=income_preference,
            )
        return self.portfolios[key]


def default_model_portfolio_repo(frontier_version: str = "frontier_v1_live") -> ModelPortfolioRepo:
    """
    Bootstrap with pre-built risk-tier portfolios. Additional portfolios
    are built on demand via get_for_client().
    """
    tiers = [(20, 30), (20, 70), (50, 50), (80, 30), (80, 70)]
    portfolios: Dict[str, ModelPortfolio] = {}

    for rs, ip in tiers:
        try:
            mp  = build_optimized_model_portfolio(rs, ip, frontier_version)
            key = f"opt_r{rs}_i{ip}"
            portfolios[key] = mp
            if rs == 50 and ip == 50:
                portfolios["core_balanced"] = mp
            if rs == 20 and ip == 30:
                portfolios["conservative"] = mp
        except Exception:
            pass

    # Compat aliases — last-resort stubs if optimizer entirely unavailable
    for alias, weights_def, er, vol in [
        ("core_balanced", {"VTI": 0.50, "VXUS": 0.25, "BND": 0.25}, 0.06, 0.12),
        ("conservative",  {"VTI": 0.30, "VXUS": 0.15, "BND": 0.55}, 0.045, 0.08),
    ]:
        if alias not in portfolios:
            mp = ModelPortfolio(
                name=alias, weights=weights_def,
                expected_return=er, volatility=vol,
                frontier_version=frontier_version,
            )
            mp.validate()
            portfolios[alias] = mp

    return ModelPortfolioRepo(portfolios=portfolios)
