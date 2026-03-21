from __future__ import annotations

import argparse
import os
from datetime import date

from ai_advisory.core.frontier_status import FrontierStatus
from ..spec import FrontierSpec, UniverseSpec, ConstraintsSpec
from ..engine import build_frontier_from_config
from ..store.fs_store import FileSystemFrontierStore
from ..versioning import compute_frontier_version


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Build the efficient frontier from live yfinance data (no xlsx required)."
    )
    ap.add_argument("--as-of", default=str(date.today()), help="YYYY-MM-DD (default: today)")
    ap.add_argument("--model-id", default="core")
    ap.add_argument("--store-root", default="data/frontiers")
    ap.add_argument(
        "--allocation-sheet",
        default="Sub-Assets",
        choices=["Sub-Assets", "Asset Class"],
        help="Which universe to use (Sub-Assets = full 16-ETF, Asset Class = 7-ETF top-level)",
    )
    ap.add_argument(
        "--prices-period",
        default="5y",
        help="yfinance history period (e.g. '5y', '3y', 'max'). Default: 5y",
    )
    ap.add_argument(
        "--cache-path",
        default=None,
        help="Optional path to a pickle file for caching yfinance prices across runs.",
    )
    ap.add_argument("--force", action="store_true", help="Rebuild even if frontier already exists.")
    args = ap.parse_args()

    store = FileSystemFrontierStore(root=args.store_root)

    spec = FrontierSpec(
        as_of=args.as_of,
        model_id=args.model_id,
        universe=UniverseSpec(assets=[]),
        constraints=ConstraintsSpec(bounds={}),
    )

    _ = compute_frontier_version(spec)  # placeholder pre-normalization

    if not args.force:
        latest = store.get_latest(args.as_of, args.model_id)
        if latest and store.exists(args.as_of, latest):
            print(f"Frontier already exists: {latest} — use --force to rebuild.")
            return 0

    print(f"Building frontier | as_of={args.as_of} | model_id={args.model_id} | sheet={args.allocation_sheet}")

    result = build_frontier_from_config(
        spec=spec,
        allocation_sheet=args.allocation_sheet,
        prices_period=args.prices_period,
        cache_path=args.cache_path,
    )

    print(f"  Assets ({len(result.assets)}): {list(result.assets)}")
    print(f"  Raw points: {len(result.points_raw)} | Sampled points: {len(result.points_sampled)}")

    # Handle existing frontier
    if store.exists(args.as_of, result.frontier_version) and not args.force:
        try:
            store.set_latest(args.as_of, args.model_id, result.frontier_version)
            print(f"Exists: {result.frontier_version} (latest updated)")
        except ValueError as e:
            print(f"Exists: {result.frontier_version} (latest not updated: {e})")
        return 0

    # Persist
    store.put(result)
    store.set_status(args.as_of, result.frontier_version, FrontierStatus.LOCKED)
    store.set_latest(args.as_of, args.model_id, result.frontier_version)

    print(f"Built + locked: {result.frontier_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
