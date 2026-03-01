from ai_advisory.frontier.spec import FrontierSpec, UniverseSpec
from ai_advisory.frontier.versioning import compute_frontier_version


def test_frontier_version_stable_under_asset_order():
    s1 = FrontierSpec(as_of="2026-02-26", universe=UniverseSpec(assets=["SPY","IEF","BIL"]))
    s2 = FrontierSpec(as_of="2026-02-26", universe=UniverseSpec(assets=["BIL","SPY","IEF"]))
    assert compute_frontier_version(s1) == compute_frontier_version(s2)
