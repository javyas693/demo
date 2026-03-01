
from __future__ import annotations

from pathlib import Path

import pytest

from ai_advisory.core.frontier_status import FrontierStatus
from ai_advisory.frontier.results import FrontierPoint, FrontierResult
from ai_advisory.frontier.spec import FrontierSpec, UniverseSpec
from ai_advisory.frontier.store.fs_store import FileSystemFrontierStore
from ai_advisory.frontier.versioning import compute_frontier_version


def _build_small_result() -> FrontierResult:
    assets = ("SPY", "IEF")

    spec = FrontierSpec(
        as_of="2026-02-26",
        universe=UniverseSpec(assets=list(assets)),
    ).normalized()

    fv = compute_frontier_version(spec)

    pts = [
        FrontierPoint(risk_score=1, exp_return=0.03, vol=0.05, weights=(0.0, 1.0)),
        FrontierPoint(risk_score=2, exp_return=0.05, vol=0.10, weights=(0.5, 0.5)),
    ]

    return FrontierResult(
        spec=spec,
        frontier_version=fv,
        points_raw=[],
        points_sampled=pts,
        assets=assets,
    )


def test_store_cannot_overwrite_after_approved(tmp_path: Path) -> None:
    store = FileSystemFrontierStore(root=str(tmp_path))
    res = _build_small_result()
    store.put(res)

    as_of = str(res.spec.as_of)
    fv = res.frontier_version

    store.set_status(as_of, fv, FrontierStatus.LOCKED)
    store.set_status(as_of, fv, FrontierStatus.APPROVED)

    with pytest.raises(ValueError):
        store.put(res)


def test_set_latest_requires_locked(tmp_path: Path) -> None:
    store = FileSystemFrontierStore(root=str(tmp_path))
    res = _build_small_result()
    store.put(res)

    as_of = str(res.spec.as_of)
    fv = res.frontier_version
    model_id = res.spec.model_id

    with pytest.raises(ValueError):
        store.set_latest(as_of, model_id, fv)

    store.set_status(as_of, fv, FrontierStatus.LOCKED)
    store.set_latest(as_of, model_id, fv)
    assert store.get_latest(as_of, model_id) == fv