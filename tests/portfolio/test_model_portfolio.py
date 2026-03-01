import pytest

from ai_advisory.portfolio.model_portfolio import (
    AssetExposure,
    ModelPortfolio,
    build_custom_model_portfolio,
)
from ai_advisory.portfolio.model_portfolio_repo import default_model_portfolio_repo


def test_model_portfolio_requires_metadata_and_weight_sum():
    mp = ModelPortfolio(
        name="t",
        weights={"A": 0.6, "B": 0.4},
        expected_return=0.05,
        volatility=0.10,
        frontier_version="fv1",
    )
    mp.validate()

    bad = ModelPortfolio(
        name="bad",
        weights={"A": 0.6, "B": 0.5},
        expected_return=0.05,
        volatility=0.10,
        frontier_version="fv1",
    )
    with pytest.raises(ValueError, match="must sum to 1.0"):
        bad.validate()


def test_default_repo_returns_model_portfolio_with_metadata():
    repo = default_model_portfolio_repo(frontier_version="fv_test")
    mp = repo.get("core_balanced")
    assert mp.frontier_version == "fv_test"
    assert mp.expected_return > 0
    assert mp.volatility > 0
    mp.validate()


def test_build_custom_model_portfolio_from_asset_exposure_and_mapping():
    exposure = AssetExposure(
        exposures={"us_equity": 0.6, "intl_equity": 0.2, "core_bond": 0.2}
    )
    mapping = {"us_equity": "VTI", "intl_equity": "VXUS", "core_bond": "BND"}

    mp = build_custom_model_portfolio(
        name="custom_1",
        asset_exposure=exposure,
        ticker_mapping=mapping,
        expected_return=0.055,
        volatility=0.11,
        frontier_version="fv_custom_1",
    )

    assert mp.weights == {"VTI": 0.6, "VXUS": 0.2, "BND": 0.2}
    mp.validate()


def test_build_custom_model_portfolio_missing_mapping_raises():
    exposure = AssetExposure(exposures={"us_equity": 1.0})
    mapping = {}  # missing
    with pytest.raises(KeyError, match="Missing ticker mapping"):
        build_custom_model_portfolio(
            name="custom_bad",
            asset_exposure=exposure,
            ticker_mapping=mapping,
            expected_return=0.05,
            volatility=0.10,
            frontier_version="fv",
        )