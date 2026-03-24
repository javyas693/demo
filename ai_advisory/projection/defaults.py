from __future__ import annotations

DEFAULT_ASSUMPTIONS: dict = {
    "cp_annual_return": 0.09,
    "cp_annual_vol":    0.22,
    "income_annual_return": 0.07,
    "income_annual_vol":    0.13,
    "model_annual_return": 0.08,
    "model_annual_vol":    0.14,
    "reinvest_income": True,
    "simulations": 1000,
    "tax_rate": 0.20,
}

MIN_RELIABLE_MONTHS = 60
FIT_WINDOW_MONTHS   = 120   # last 10 years only — avoids ancient history bias
CP_RETURN_CAP = 0.20
CP_RETURN_MIN = 0.04
CP_VOL_CAP    = 0.40
CP_VOL_MIN    = 0.10

def fit_cp_assumptions(ticker: str, price_series=None) -> dict:
    import numpy as np
    if price_series is None or len(price_series) < MIN_RELIABLE_MONTHS:
        return {"cp_annual_return": DEFAULT_ASSUMPTIONS["cp_annual_return"],
                "cp_annual_vol":    DEFAULT_ASSUMPTIONS["cp_annual_vol"]}
    try:
        series = price_series.iloc[-FIT_WINDOW_MONTHS:]
        monthly_returns = series.pct_change().dropna()
        ann_return = float((1 + monthly_returns.mean()) ** 12 - 1)
        ann_vol    = float(monthly_returns.std() * np.sqrt(12))
        ann_return = max(CP_RETURN_MIN, min(ann_return, CP_RETURN_CAP))
        ann_vol    = max(CP_VOL_MIN,    min(ann_vol,    CP_VOL_CAP))
        return {"cp_annual_return": round(ann_return, 4),
                "cp_annual_vol":    round(ann_vol, 4)}
    except Exception:
        return {"cp_annual_return": DEFAULT_ASSUMPTIONS["cp_annual_return"],
                "cp_annual_vol":    DEFAULT_ASSUMPTIONS["cp_annual_vol"]}

def merge_assumptions(user_overrides: dict | None) -> dict:
    result = dict(DEFAULT_ASSUMPTIONS)
    if user_overrides:
        for key in DEFAULT_ASSUMPTIONS:
            if key in user_overrides and user_overrides[key] is not None:
                result[key] = user_overrides[key]
    return result
