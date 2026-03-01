import numpy as np

from ai_advisory.frontier.io_xlsx import load_allocation_constraints, load_prices_matrix
from ai_advisory.frontier.spec import FrontierSpec, UniverseSpec, ConstraintsSpec
from ai_advisory.frontier.returns import compute_implied_mu
from ai_advisory.frontier.risk import compute_historical_cov

from ai_advisory.frontier.io_xlsx import load_allocation_workbook


def test_build_mu_sigma_from_xlsx(tmp_path):
    # NOTE: Update these paths to your actual files if they live elsewhere.
    # For now the test is skipped unless you set env vars or place files in repo.
    import os
    alloc = os.getenv("AI_ADVISORY_ALLOC_XLSX")
    prices = os.getenv("AI_ADVISORY_PRICES_XLSX")
    if not alloc or not prices:
        return

    alloc_wb = load_allocation_workbook(alloc)
    prices_df = load_prices_matrix(prices)

    for key in ["asset_class", "sub_assets"]:
        alloc_obj = alloc_wb[key]
        assets = [t for t in alloc_obj["assets"] if t in prices_df.columns]
        assert len(assets) >= 2

        spec = FrontierSpec(
            as_of="2026-02-26",
            universe=UniverseSpec(assets=assets),
            constraints=ConstraintsSpec(bounds={k: alloc_obj["bounds"][k] for k in assets}),
            asset_class_map=alloc_obj["asset_class_map"],
            sub_asset_class_map=alloc_obj["sub_asset_class_map"],
            name_map=alloc_obj["name_map"],
            yield_map=alloc_obj["yield_map"],
            expense_ratio_map=alloc_obj["expense_ratio_map"],
        )

        mu = compute_implied_mu(spec, assets)
        sigma = compute_historical_cov(prices_df, assets, annualization_factor=spec.risk_model.annualization_factor)

        assert mu.shape == (len(assets),)
        assert sigma.shape == (len(assets), len(assets))
        assert np.isfinite(mu).all()
        assert np.isfinite(sigma).all()
        assert np.allclose(sigma, sigma.T, atol=1e-10)

