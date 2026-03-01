from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Any

from .spec import FrontierSpec


def _round_floats(obj: Any, ndigits: int = 12) -> Any:
    if isinstance(obj, float):
        return round(obj, ndigits)
    if isinstance(obj, dict):
        return {k: _round_floats(v, ndigits) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round_floats(x, ndigits) for x in obj]
    if isinstance(obj, tuple):
        return tuple(_round_floats(x, ndigits) for x in obj)
    return obj


def compute_frontier_version(spec: FrontierSpec) -> str:
    n = spec.normalized()
    payload = asdict(n)
    payload = _round_floats(payload, ndigits=12)
    canon = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    h = hashlib.sha256(canon.encode("utf-8")).hexdigest()[:12]
    return f"fr_v1_{h}"
