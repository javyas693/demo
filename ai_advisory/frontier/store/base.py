from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from ..results import FrontierResult


class FrontierStore(ABC):
    @abstractmethod
    def exists(self, as_of: str, frontier_version: str) -> bool: ...

    @abstractmethod
    def put(self, result: FrontierResult) -> None: ...

    @abstractmethod
    def get(self, as_of: str, frontier_version: str) -> FrontierResult: ...

    @abstractmethod
    def get_latest(self, as_of: str, model_id: str) -> Optional[str]: ...

    @abstractmethod
    def set_latest(self, as_of: str, model_id: str, frontier_version: str) -> None: ...
