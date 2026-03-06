from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .http_models import ClientProfile, ProfilePatch


class ProfileStore:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> ClientProfile:
        if not self.path.exists():
            # default empty profile
            return ClientProfile()

        data = json.loads(self.path.read_text(encoding="utf-8"))
        return ClientProfile.model_validate(data)

    def save(self, profile: ClientProfile) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")

    def patch(self, patch: ProfilePatch) -> ClientProfile:
        profile = self.load()

        # scalar updates
        upd = patch.model_dump(exclude_unset=True)
        for k in ["cash_to_invest", "risk_score", "objective", "income_target_annual", "concentration_threshold_pct"]:
            if k in upd:
                setattr(profile, k, upd[k])

        # positions (upsert by symbol)
        if patch.positions is not None:
            by_symbol = {p.symbol.upper(): p for p in profile.positions}
            for p in patch.positions:
                by_symbol[p.symbol.upper()] = p
            profile.positions = list(by_symbol.values())

        self.save(profile)
        return profile

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()