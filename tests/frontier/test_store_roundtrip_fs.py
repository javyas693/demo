from ai_advisory.frontier.spec import FrontierSpec, UniverseSpec
from ai_advisory.frontier.results import FrontierPoint, FrontierResult
from ai_advisory.frontier.store.fs_store import FileSystemFrontierStore
from ai_advisory.frontier.versioning import compute_frontier_version
from ai_advisory.frontier.weights import weights_tuple_to_dict


def test_fs_store_roundtrip(tmp_path):
    store = FileSystemFrontierStore(root=str(tmp_path))

    assets = ("SPY", "IEF")
    spec = FrontierSpec(as_of="2026-02-26", universe=UniverseSpec(assets=list(assets)))
    fv = compute_frontier_version(spec)

    pts = [
        FrontierPoint(risk_score=1, exp_return=0.03, vol=0.05, weights=(0.0, 1.0)),
        FrontierPoint(risk_score=2, exp_return=0.05, vol=0.10, weights=(0.5, 0.5)),
    ]
    res = FrontierResult(spec=spec, frontier_version=fv, points_raw=[], points_sampled=pts, assets=assets)

    store.put(res)
    out = store.get("2026-02-26", fv)

    assert out.frontier_version == fv
    assert len(out.points_sampled) == 2
    assert out.assets == assets

    w0 = weights_tuple_to_dict(out.points_sampled[0].weights, out.assets)
    assert w0["IEF"] == 1.0