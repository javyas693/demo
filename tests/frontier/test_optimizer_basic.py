import numpy as np
from ai_advisory.frontier.optimizer import solve_max_return_under_vol_cap


def test_optimizer_respects_constraints():
    mu = np.array([0.05, 0.10])
    sigma = np.array([[0.04, 0.01],
                      [0.01, 0.09]])  # PSD

    bounds = [(0.0, 1.0), (0.0, 1.0)]
    vol_cap = 0.30

    w = solve_max_return_under_vol_cap(mu, sigma, vol_cap, bounds)

    assert abs(w.sum() - 1.0) < 1e-6
    assert (w >= -1e-8).all()
    assert (w <= 1.0 + 1e-8).all()

    vol = np.sqrt(w @ sigma @ w)
    assert vol <= vol_cap + 1e-6