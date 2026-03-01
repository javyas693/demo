from __future__ import annotations

import argparse
from datetime import date

from ai_advisory.core.frontier_status import FrontierStatus
from ..spec import FrontierSpec, UniverseSpec, ConstraintsSpec
from ..engine import build_frontier
from ..store.fs_store import FileSystemFrontierStore
from ..versioning import compute_frontier_version


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", default=str(date.today()), help="YYYY-MM-DD")
    ap.add_argument("--model-id", default="core")
    ap.add_argument("--store-root", default="data/frontiers")
    ap.add_argument("--allocation-xlsx", required=True)
    ap.add_argument("--prices-xlsx", required=True)
    ap.add_argument("--allocation-sheet", default="Sub-Assets", choices=["Sub-Assets", "Asset Class"])
    ap.add_argument("--prices-sheet", default=None)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    store = FileSystemFrontierStore(root=args.store_root)

    # Spec is mostly metadata here; engine will normalize/overwrite assets/bounds from workbook.
    spec = FrontierSpec(
        as_of=args.as_of,
        model_id=args.model_id,
        universe=UniverseSpec(assets=[]),
        constraints=ConstraintsSpec(bounds={}),
    )

    _ = compute_frontier_version(spec)  # placeholder; not authoritative pre-normalization

    if not args.force:
        # quick path: attempt to load latest mapping first
        latest = store.get_latest(args.as_of, args.model_id)
        if latest and store.exists(args.as_of, latest):
            print(f"Exists latest: {latest}")
            return 0

    result = build_frontier(
        spec=spec,
        allocation_xlsx=args.allocation_xlsx,
        prices_xlsx=args.prices_xlsx,
        allocation_sheet=args.allocation_sheet,
        prices_sheet=args.prices_sheet,
    )

    # If it already exists and we're not forcing, try to set latest (will only work if LOCKED+)
    if store.exists(args.as_of, result.frontier_version) and (not args.force):
        try:
            store.set_latest(args.as_of, args.model_id, result.frontier_version)
            print(f"Exists: {result.frontier_version} (set latest)")
        except ValueError as e:
            # Likely status is DRAFT; don't fail the job, just report.
            print(f"Exists: {result.frontier_version} (latest not updated: {e})")
        return 0

    # Persist artifacts
    store.put(result)

    # Patch 6A: lock after successful build
    store.set_status(args.as_of, result.frontier_version, FrontierStatus.LOCKED)

    # Now allowed by Patch 5 gating
    store.set_latest(args.as_of, args.model_id, result.frontier_version)

    print(f"Built + locked: {result.frontier_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())