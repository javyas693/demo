
from __future__ import annotations

from typing import List
import numpy as np

from .results import FrontierPoint


def _normalize(v: np.ndarray) -> np.ndarray:
    vmin = float(np.min(v))
    vmax = float(np.max(v))
    if abs(vmax - vmin) < 1e-18:
        return np.zeros_like(v)
    return (v - vmin) / (vmax - vmin)


def sample_curve_length_nearest(points_sorted_by_vol: List[FrontierPoint], n: int = 100) -> List[FrontierPoint]:
    if len(points_sorted_by_vol) == 0:
        return []
    if n <= 0:
        return []

    pts = points_sorted_by_vol

    vols = np.array([p.vol for p in pts], dtype=float)
    rets = np.array([p.exp_return for p in pts], dtype=float)

    x = _normalize(vols)
    y = _normalize(rets)

    # cumulative arc length
    dx = np.diff(x)
    dy = np.diff(y)
    seg = np.sqrt(dx * dx + dy * dy)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    total = float(s[-1])

    # If degenerate (all points identical), fall back to volatility spacing nearest
    if total < 1e-18:
        idx = np.linspace(0, len(pts) - 1, num=min(n, len(pts)))
        idx = np.round(idx).astype(int)
        idx = np.unique(idx)
        return [pts[i] for i in idx]

    targets = np.linspace(0.0, total, num=min(n, len(pts)))

    # nearest indices to each target
    chosen = []
    used = set()

    for t in targets:
        i = int(np.argmin(np.abs(s - t)))
        if i not in used:
            chosen.append(i)
            used.add(i)
            continue

        # deterministic de-dupe: expand outward to find nearest unused neighbor
        left = i - 1
        right = i + 1
        while left >= 0 or right < len(pts):
            if left >= 0 and left not in used:
                chosen.append(left)
                used.add(left)
                break
            if right < len(pts) and right not in used:
                chosen.append(right)
                used.add(right)
                break
            left -= 1
            right += 1

    chosen = sorted(chosen)

    # ensure endpoints included
    if 0 not in used:
        chosen = [0] + chosen
    if (len(pts) - 1) not in used:
        chosen = chosen + [len(pts) - 1]

    # trim to n deterministically (drop closest interior points if needed)
    chosen = sorted(set(chosen))
    if len(chosen) > n:
        # keep endpoints, drop extras by smallest incremental arc distance
        keep = set([chosen[0], chosen[-1]])
        middle = chosen[1:-1]

        # rank middle points by their distance to nearest neighbor in s-space
        gaps = []
        for idx in middle:
            # distance to nearest chosen neighbor in s space (initially endpoints only if we haven't built keep)
            gaps.append((min(abs(s[idx] - s[chosen[0]]), abs(s[idx] - s[chosen[-1]])), idx))
        # not perfect, but deterministic and stable
        gaps.sort(reverse=True)  # keep more "distinct" ones
        for _, idx in gaps:
            if len(keep) + len([m for m in middle if m not in keep]) <= n:
                break
            keep.add(idx)

        # If still too many, just take first n endpoints+sorted middle
        chosen2 = [chosen[0]] + sorted([m for m in middle]) + [chosen[-1]]
        chosen = chosen2[:n]
    return [pts[i] for i in chosen[:n]]