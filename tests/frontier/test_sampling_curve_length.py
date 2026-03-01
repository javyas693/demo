from ai_advisory.frontier.results import FrontierPoint
from ai_advisory.frontier.sampling import sample_curve_length_nearest


def test_curve_length_sampling_spreads_points():
    # synthetic frontier: vols 0..1, returns flat then steep
    pts = []
    for i in range(300):
        vol = i / 299
        ret = 0.02 if vol < 0.5 else 0.02 + (vol - 0.5) * 0.20
        pts.append(FrontierPoint(risk_score=i+1, exp_return=ret, vol=vol, weights={"A": 1.0}))

    sampled = sample_curve_length_nearest(pts, n=100)
    assert len(sampled) == 100
    assert sampled[0].vol == pts[0].vol
    assert sampled[-1].vol == pts[-1].vol
    # should cover both regions (not all clustered)
    vols = [p.vol for p in sampled]
    assert min(vols) <= 0.01
    assert max(vols) >= 0.99