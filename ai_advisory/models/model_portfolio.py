from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping


@dataclass(frozen=True)
class ModelPortfolio:
    """
    Frozen schema name: ModelPortfolio (do not rename).
    v1 minimal: target_weights must sum to 1 (within tolerance).
    """
    name: str
    target_weights: Mapping[str, float]

    def normalized_weights(self) -> Dict[str, float]:
        w = dict(self.target_weights)
        total = sum(w.values())
        if total <= 0:
            raise ValueError("ModelPortfolio.target_weights total must be > 0")
        for k, v in w.items():
            if v < 0:
                raise ValueError(f"ModelPortfolio.target_weights cannot be negative: {k}={v}")
        return {k: v / total for k, v in w.items()}

    def validate(self, tol: float = 1e-6) -> None:
        w = self.normalized_weights()
        s = sum(w.values())
        if abs(s - 1.0) > tol:
            raise ValueError(f"ModelPortfolio.target_weights must sum to 1.0 (sum={s})")