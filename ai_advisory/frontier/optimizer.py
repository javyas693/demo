from __future__ import annotations

from typing import List, Tuple
import numpy as np
import cvxpy as cp


def solve_max_return_under_vol_cap(
    mu: np.ndarray,
    sigma: np.ndarray,
    vol_cap: float,
    bounds: List[Tuple[float, float]],
) -> np.ndarray:
    """
    Maximize mu^T w
    Subject to:
        w^T Sigma w <= vol_cap^2
        sum(w) = 1
        bounds[i][0] <= w_i <= bounds[i][1]
    """

    n = len(mu)
    w = cp.Variable(n)

    objective = cp.Maximize(mu @ w)

    constraints = []

    # Sum to 1
    constraints.append(cp.sum(w) == 1)

    # Vol constraint
    constraints.append(cp.quad_form(w, sigma) <= vol_cap ** 2)

    # Bounds
    for i in range(n):
        lb, ub = bounds[i]
        constraints.append(w[i] >= lb)
        constraints.append(w[i] <= ub)

    problem = cp.Problem(objective, constraints)

    problem.solve(
        solver=cp.ECOS,
        abstol=1e-9,
        reltol=1e-9,
        feastol=1e-9,
        verbose=False,
    )

    if w.value is None:
        raise RuntimeError("Optimization failed")

    return np.array(w.value).flatten()

def solve_min_vol(
    sigma: np.ndarray,
    bounds: List[Tuple[float, float]],
) -> np.ndarray:
    """
    Minimize w^T Sigma w subject to sum(w)=1 and bounds.
    Returns weights.
    """
    n = sigma.shape[0]
    w = cp.Variable(n)

    objective = cp.Minimize(cp.quad_form(w, sigma))
    constraints = [cp.sum(w) == 1]
    for i in range(n):
        lb, ub = bounds[i]
        constraints += [w[i] >= lb, w[i] <= ub]

    problem = cp.Problem(objective, constraints)
    problem.solve(
        solver=cp.ECOS,
        abstol=1e-9,
        reltol=1e-9,
        feastol=1e-9,
        verbose=False,
    )
    if w.value is None:
        raise RuntimeError("Min-vol optimization failed")
    return np.array(w.value).flatten()