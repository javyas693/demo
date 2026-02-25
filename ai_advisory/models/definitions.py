from __future__ import annotations

from ai_advisory.models.model_portfolio import ModelPortfolio

# Replace tickers/weights with your actual core lineup.
CONSERVATIVE = ModelPortfolio(
    name="Conservative",
    target_weights={
        "BND": 0.55,
        "VTI": 0.30,
        "VXUS": 0.15,
    },
)

BALANCED = ModelPortfolio(
    name="Balanced",
    target_weights={
        "VTI": 0.50,
        "VXUS": 0.25,
        "BND": 0.25,
    },
)

GROWTH = ModelPortfolio(
    name="Growth",
    target_weights={
        "VTI": 0.65,
        "VXUS": 0.30,
        "BND": 0.05,
    },
)