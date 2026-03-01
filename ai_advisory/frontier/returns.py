from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np

from .spec import FrontierSpec


def compute_implied_mu(spec: FrontierSpec, assets: List[str]) -> np.ndarray:
    er = spec.expected_return
    mu = []
    for t in assets:
        y = float(spec.yield_map.get(t, 0.0))
        e = float(spec.expense_ratio_map.get(t, 0.0))
        ac = spec.asset_class_map.get(t, "")
        sac = spec.sub_asset_class_map.get(t, "")

        g = 0.0
        if sac and sac in er.sub_asset_growth:
            g = float(er.sub_asset_growth[sac])
        elif ac and ac in er.asset_class_growth:
            g = float(er.asset_class_growth[ac])

        m = y - e + g

        # clamp
        m = max(er.clamp_min, min(er.clamp_max, m))
        mu.append(m)

    return np.array(mu, dtype=float)
