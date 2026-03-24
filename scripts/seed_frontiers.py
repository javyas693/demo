import os
import json
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from pathlib import Path

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def generate_mock_frontier(store_root: str, as_of: str, model_id: str = "core_balanced"):
    root = Path(store_root)
    fv = f"v_mock_{as_of.replace('-', '')}"
    d = root / f"asof={as_of}" / f"frontier_version={fv}"
    d.mkdir(parents=True, exist_ok=True)
    
    assets = ["VTI", "VXUS", "BND"]
    
    # Generate 100 points
    points_rows = []
    weights_rows = []
    
    for i in range(1, 101):
        # Risk score 1 is conservative (high BND), 100 is aggressive (high VTI/VXUS)
        equity_weight = i / 100.0
        bond_weight = 1.0 - equity_weight
        
        vti_w = equity_weight * 0.7
        vxus_w = equity_weight * 0.3
        bnd_w = bond_weight
        
        ret = 0.02 + (equity_weight * 0.06) # 2% to 8% return
        vol = 0.05 + (equity_weight * 0.15) # 5% to 20% vol
        
        points_rows.append({
            "risk_score": i,
            "vol": vol,
            "exp_return": ret,
            "excess_return": ret - 0.02,
            "sharpe": (ret - 0.02) / vol if vol > 0 else 0
        })
        
        weights_rows.append({
            "risk_score": i,
            "VTI": vti_w,
            "VXUS": vxus_w,
            "BND": bnd_w
        })
        
    points_df = pd.DataFrame(points_rows)
    weights_df = pd.DataFrame(weights_rows)
    
    points_df.to_parquet(d / "points.parquet", index=False)
    weights_df.to_parquet(d / "weights.parquet", index=False)
    
    # spec.json
    spec = {
        "as_of": as_of,
        "model_id": model_id,
        "schema_version": "frontier_spec_v1",
        "engine_version": "mock"
    }
    (d / "spec.json").write_text(json.dumps(spec, indent=2))
    
    # run_meta.json
    run_meta = {
        "as_of": as_of,
        "model_id": model_id,
        "frontier_version": fv,
        "created_at_utc": _utc_now_iso()
    }
    (d / "run_meta.json").write_text(json.dumps(run_meta, indent=2))
    
    # meta.json
    meta = {
        "status": "APPROVED",
        "frontier_version": fv,
        "as_of": as_of,
        "model_id": model_id
    }
    (d / "meta.json").write_text(json.dumps(meta, indent=2))
    
    # latest.json
    latest_path = root / f"asof={as_of}" / "latest.json"
    latest_data = {"as_of": as_of, "models": {model_id: fv}}
    latest_path.write_text(json.dumps(latest_data, indent=2))
    
    # manifest.json
    # Just a dummy empty manifest to bypass verification if needed, or actual hashes
    import hashlib
    def sha256_file(p):
        h = hashlib.sha256()
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
        
    manifest = {p.name: sha256_file(p) for p in d.iterdir() if p.is_file() and p.name != "manifest.json"}
    (d / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"Generated mock frontier for {as_of} -> {fv}")

def main():
    dates = [
        "2023-01-31", "2023-02-28", "2023-03-31", "2023-04-30", "2023-05-31", "2023-06-30",
        "2023-07-31", "2023-08-31", "2023-09-30", "2023-10-31", "2023-11-30", "2023-12-31",
        "2024-01-31", "2024-02-29", "2024-03-31", "2024-04-30", "2024-05-31", "2024-06-30",
        "2024-07-31", "2024-08-31", "2024-09-30", "2024-10-31", "2024-11-30", "2024-12-31"
    ]
    for d in dates:
        generate_mock_frontier("data/frontiers", d, "core_balanced")
        generate_mock_frontier("data/frontiers", d, "core")

if __name__ == "__main__":
    main()
