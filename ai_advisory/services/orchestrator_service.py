from __future__ import annotations

from typing import Any, Dict

from .concentrated_service import propose_concentrated
from .http_models import ClientProfile


def propose(profile: ClientProfile) -> Dict[str, Any]:
    """
    MVP orchestrator:
      - If single holding -> concentrated path
      - Return selected_path + reasons + profile + result
    """
    reasons: list[str] = []

    # MVP rule: single holding means concentrated
    if profile.positions and len(profile.positions) == 1:
        reasons.append("Detected concentrated position (MVP rule: single holding).")
        result = propose_concentrated(profile)
        return {
            "selected_path": "concentrated",
            "reasons": reasons,
            "profile": profile.model_dump(),
            "result": result,
        }

    reasons.append("No concentrated position detected (MVP rule).")
    return {
        "selected_path": "frontier",
        "reasons": reasons,
        "profile": profile.model_dump(),
        "result": {"error": "Frontier path not implemented in MVP."},
    }