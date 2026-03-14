from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class FrontierStatus(str, Enum):
    DRAFT = "DRAFT"
    LOCKED = "LOCKED"
    APPROVED = "APPROVED"
    EXECUTED = "EXECUTED"
    ARCHIVED = "ARCHIVED"


@dataclass(frozen=True)
class FrontierProvenance:
    """
    Immutable metadata that ties a frontier to an input state and engine version.
    """
    engine_version: str
    schema_version: str
    state_id: str
    state_as_of: str  # use ISO date string to avoid tz pitfalls in metadata
    input_hash: str
    created_at: str  # ISO datetime


@dataclass
class FrontierRecord:
    """
    Wraps the frontier data with status + provenance.
    """
    id: str
    status: FrontierStatus
    provenance: FrontierProvenance

    locked_at: Optional[str] = None
    approved_at: Optional[str] = None
    executed_at: Optional[str] = None
    archived_at: Optional[str] = None

    # Optional: store frontier_hash to detect drift
    frontier_hash: Optional[str] = None

    def lock(self, now_iso: Optional[str] = None) -> None:
        if self.status != FrontierStatus.DRAFT:
            raise ValueError(f"Can only lock from DRAFT. Current={self.status}")
        self.status = FrontierStatus.LOCKED
        self.locked_at = now_iso or datetime.utcnow().isoformat()

    def approve(self, now_iso: Optional[str] = None) -> None:
        if self.status != FrontierStatus.LOCKED:
            raise ValueError(f"Can only approve from LOCKED. Current={self.status}")
        self.status = FrontierStatus.APPROVED
        self.approved_at = now_iso or datetime.utcnow().isoformat()

    def mark_executed(self, now_iso: Optional[str] = None) -> None:
        if self.status != FrontierStatus.APPROVED:
            raise ValueError(f"Can only execute from APPROVED. Current={self.status}")
        self.status = FrontierStatus.EXECUTED
        self.executed_at = now_iso or datetime.utcnow().isoformat()

    def archive(self, now_iso: Optional[str] = None) -> None:
        if self.status not in (FrontierStatus.DRAFT, FrontierStatus.LOCKED, FrontierStatus.APPROVED, FrontierStatus.EXECUTED):
            raise ValueError(f"Invalid status for archive: {self.status}")
        self.status = FrontierStatus.ARCHIVED
        self.archived_at = now_iso or datetime.utcnow().isoformat()