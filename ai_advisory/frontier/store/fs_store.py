from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from ai_advisory.core.frontier_status import FrontierStatus
from ai_advisory.core.integrity import stable_hash

from .base import FrontierStore
from ..results import FrontierPoint, FrontierResult
from ..spec import FrontierSpec
from ..weights import weights_tuple_to_dict


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    _atomic_write_bytes(path, text.encode(encoding))


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def verify_manifest(dir_path: str | Path) -> None:
    d = Path(dir_path)
    manifest_path = d / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest.json not found in {d}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for fname, expected in manifest.items():
        p = d / fname
        if not p.exists():
            raise FileNotFoundError(f"missing artifact file listed in manifest: {fname}")
        actual = _sha256_file(p)
        if actual != expected:
            raise ValueError(f"sha256 mismatch for {fname}: expected={expected} actual={actual}")


class FileSystemFrontierStore(FrontierStore):
    """
    Patch 5 additions:
      - meta.json persisted per frontier_version:
          * status: FrontierStatus (starts DRAFT)
          * input_hash: stable hash of normalized spec
          * frontier_hash: stable hash of sampled points payload
      - status gating:
          * cannot overwrite APPROVED/EXECUTED
          * cannot set_latest unless status >= LOCKED (LOCKED/APPROVED/EXECUTED)
      - status transitions via set_status()
    """

    def __init__(self, root: str = "data/frontiers") -> None:
        self.root = Path(root)

    def _dir(self, as_of: str, frontier_version: str) -> Path:
        return self.root / f"asof={as_of}" / f"frontier_version={frontier_version}"

    def _meta_path(self, as_of: str, frontier_version: str) -> Path:
        return self._dir(as_of, frontier_version) / "meta.json"

    def _read_meta(self, as_of: str, frontier_version: str) -> dict:
        p = self._meta_path(as_of, frontier_version)
        if not p.exists():
            return {}
        return json.loads(p.read_text(encoding="utf-8"))

    def _write_meta(self, as_of: str, frontier_version: str, meta: dict) -> None:
        p = self._meta_path(as_of, frontier_version)
        _atomic_write_text(p, json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")

    def get_status(self, as_of: str, frontier_version: str) -> FrontierStatus:
        meta = self._read_meta(as_of, frontier_version)
        s = meta.get("status")
        if not s:
            return FrontierStatus.DRAFT
        return FrontierStatus(str(s))

    def set_status(self, as_of: str, frontier_version: str, new_status: FrontierStatus) -> None:
        """
        Patch 5: status transition gate.
        Allowed transitions:
          DRAFT -> LOCKED -> APPROVED -> EXECUTED
          Any -> ARCHIVED
        """
        d = self._dir(as_of, frontier_version)
        if not d.exists():
            raise FileNotFoundError(f"Frontier directory not found: {d}")

        meta = self._read_meta(as_of, frontier_version)
        current = FrontierStatus(str(meta.get("status", FrontierStatus.DRAFT.value)))

        allowed = {
            FrontierStatus.DRAFT: {FrontierStatus.LOCKED, FrontierStatus.ARCHIVED},
            FrontierStatus.LOCKED: {FrontierStatus.APPROVED, FrontierStatus.ARCHIVED},
            FrontierStatus.APPROVED: {FrontierStatus.EXECUTED, FrontierStatus.ARCHIVED},
            FrontierStatus.EXECUTED: {FrontierStatus.ARCHIVED},
            FrontierStatus.ARCHIVED: set(),
        }
        if new_status == current:
            return
        if new_status not in allowed.get(current, set()):
            raise ValueError(f"Invalid status transition: {current.value} -> {new_status.value}")

        meta["status"] = new_status.value
        meta.setdefault("status_history", [])
        meta["status_history"].append({"from": current.value, "to": new_status.value, "at_utc": _utc_now_iso()})
        self._write_meta(as_of, frontier_version, meta)

        # update manifest because meta.json changed
        self._write_manifest(as_of, frontier_version)

    def exists(self, as_of: str, frontier_version: str) -> bool:
        d = self._dir(as_of, frontier_version)
        return (d / "spec.json").exists() and (d / "points.parquet").exists() and (d / "weights.parquet").exists()

    def _write_manifest(self, as_of: str, frontier_version: str) -> None:
        d = self._dir(as_of, frontier_version)
        files = sorted([p for p in d.iterdir() if p.is_file() and not p.name.endswith(".tmp")])
        manifest = {p.name: _sha256_file(p) for p in files}
        _atomic_write_text(d / "manifest.json", json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    def put(self, result: FrontierResult) -> None:
        as_of = str(result.spec.as_of)
        fv = result.frontier_version
        d = self._dir(as_of, fv)
        d.mkdir(parents=True, exist_ok=True)

        # Patch 5: overwrite gating
        if self.exists(as_of, fv):
            current_status = self.get_status(as_of, fv)
            if current_status in (FrontierStatus.APPROVED, FrontierStatus.EXECUTED):
                raise ValueError(f"Refusing to overwrite frontier {fv} with status={current_status.value}")

        # Determine asset order
        assets = tuple(getattr(result, "assets", ()) or ())
        if not assets:
            assets = tuple(getattr(result.spec.universe, "assets", ()) or ())

        # --- spec (atomic)
        spec_payload = json.dumps(asdict(result.spec.normalized()), indent=2, sort_keys=True)
        _atomic_write_text(d / "spec.json", spec_payload, encoding="utf-8")

        # --- points (atomic parquet)
        pts = result.points_sampled
        points_df = pd.DataFrame(
            [
                {
                    "risk_score": p.risk_score,
                    "vol": p.vol,
                    "exp_return": p.exp_return,
                    "excess_return": getattr(p, "excess_return", None),
                    "sharpe": getattr(p, "sharpe", None),
                }
                for p in pts
            ]
        )

        tmp_points = d / "points.parquet.tmp"
        points_df.to_parquet(tmp_points, index=False)
        os.replace(tmp_points, d / "points.parquet")

        # --- weights (atomic parquet) as ticker columns
        weights_rows = []
        for p in pts:
            # Normalize weights to tuple[float,...] aligned to `assets`
            if isinstance(p.weights, dict):
                w_map = {k: float(v) for k, v in p.weights.items()}
                w_tuple = tuple(float(w_map.get(sym, 0.0)) for sym in assets)
            else:
                w_tuple = tuple(float(x) for x in p.weights)

            w_dict = weights_tuple_to_dict(w_tuple, assets)
            weights_rows.append({"risk_score": p.risk_score, **w_dict})

        weights_df = pd.DataFrame(weights_rows)

        # enforce numeric (fail fast if something is wrong)
        for c in weights_df.columns:
            if c != "risk_score":
                weights_df[c] = pd.to_numeric(weights_df[c], errors="raise")

        tmp_weights = d / "weights.parquet.tmp"
        weights_df.to_parquet(tmp_weights, index=False)
        os.replace(tmp_weights, d / "weights.parquet")

        # --- run_meta.json (atomic)
        run_meta = {
            "created_at_utc": _utc_now_iso(),
            "python_version": sys.version,
            "platform": platform.platform(),
            "frontier_version": fv,
            "schema_version": result.spec.schema_version,
            "engine_version": result.spec.engine_version,
            "as_of": as_of,
            "model_id": result.spec.model_id,
            "assets_count": len(assets),
            "points_raw_count": len(result.points_raw),
            "points_sampled_count": len(result.points_sampled),
        }
        _atomic_write_text(d / "run_meta.json", json.dumps(run_meta, indent=2, sort_keys=True), encoding="utf-8")

        # --- Patch 5: meta.json (atomic)
        # status starts as DRAFT unless already present (preserve if rerun wrote it)
        existing_meta = self._read_meta(as_of, fv)
        status = existing_meta.get("status", FrontierStatus.DRAFT.value)

        input_hash = stable_hash(result.spec.normalized())
        frontier_hash = stable_hash(
            {
                "frontier_version": fv,
                "assets": list(assets),
                "points_sampled": result.points_sampled,
            }
        )

        meta = {
            "frontier_version": fv,
            "as_of": as_of,
            "model_id": result.spec.model_id,
            "schema_version": result.spec.schema_version,
            "engine_version": result.spec.engine_version,
            "status": status,
            "input_hash": input_hash,
            "frontier_hash": frontier_hash,
            "created_at_utc": existing_meta.get("created_at_utc", _utc_now_iso()),
        }
        # keep history if present
        if "status_history" in existing_meta:
            meta["status_history"] = existing_meta["status_history"]

        self._write_meta(as_of, fv, meta)

        # --- manifest.json (atomic): hash every non-tmp file in the directory
        self._write_manifest(as_of, fv)

    def get(self, as_of: str, frontier_version: str) -> FrontierResult:
        d = self._dir(as_of, frontier_version)

        spec_obj = json.loads((d / "spec.json").read_text(encoding="utf-8"))
        spec = FrontierSpec(**spec_obj)  # relies on matching dataclass fields

        points_df = pd.read_parquet(d / "points.parquet")
        weights_df = pd.read_parquet(d / "weights.parquet").set_index("risk_score")

        # Most robust: asset order is the stored weights columns
        assets = tuple(str(c) for c in weights_df.columns)

        points: list[FrontierPoint] = []
        for _, row in points_df.iterrows():
            rs = int(row["risk_score"])
            row_dict = weights_df.loc[rs].to_dict()
            w_tuple = tuple(float(row_dict.get(sym, 0.0)) for sym in assets)

            points.append(
                FrontierPoint(
                    risk_score=rs,
                    vol=float(row["vol"]),
                    exp_return=float(row["exp_return"]),
                    weights=w_tuple,
                    excess_return=float(row["excess_return"])
                    if "excess_return" in row and pd.notna(row["excess_return"])
                    else None,
                    sharpe=float(row["sharpe"]) if "sharpe" in row and pd.notna(row["sharpe"]) else None,
                )
            )

        return FrontierResult(
            spec=spec,
            frontier_version=frontier_version,
            points_raw=[],
            points_sampled=points,
            assets=assets,
        )

    def _latest_path(self, as_of: str) -> Path:
        return self.root / f"asof={as_of}" / "latest.json"

    def get_latest(self, as_of: str, model_id: str) -> Optional[str]:
        p = self._latest_path(as_of)
        if not p.exists():
            return None
        data = json.loads(p.read_text(encoding="utf-8"))
        return data.get("models", {}).get(model_id)

    def set_latest(self, as_of: str, model_id: str, frontier_version: str) -> None:
        """
        Patch 5: only allow 'latest' to point to a frontier that is at least LOCKED.
        """
        status = self.get_status(as_of, frontier_version)
        if status not in (FrontierStatus.LOCKED, FrontierStatus.APPROVED, FrontierStatus.EXECUTED):
            raise ValueError(
                f"Cannot set latest to frontier_version={frontier_version} with status={status.value}. "
                f"Must be LOCKED/APPROVED/EXECUTED."
            )

        p = self._latest_path(as_of)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {"as_of": as_of, "models": {}}
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            data.setdefault("models", {})
        data["as_of"] = as_of
        data["models"][model_id] = frontier_version
        _atomic_write_text(p, json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")