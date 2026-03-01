from __future__ import annotations

import numpy as np
import pandas as pd


def compute_historical_cov(prices: pd.DataFrame, assets: list[str], annualization_factor: int = 252) -> np.ndarray:
    px = prices[assets].copy()
    # forward fill small gaps then drop remaining NaNs
    px = px.ffill().dropna()
    rets = px.pct_change().dropna()
    cov_daily = rets.cov().values
    cov_annual = cov_daily * float(annualization_factor)
    # force symmetry
    cov_annual = 0.5 * (cov_annual + cov_annual.T)
    return cov_annual
