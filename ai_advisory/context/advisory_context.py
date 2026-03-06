from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ai_advisory.api.http_models import ClientProfile
from ai_advisory.portfolio.portfolio_state import PortfolioState


@dataclass
class AdvisoryContext:
    """
    AdvisoryContext provides the unified state used by the orchestrator.

    It combines:

    - ClientProfile (client preferences)
    - PortfolioState (current holdings and cash)

    Future versions may extend this with:

    - FamilyContext
    - Account structures
    - Market data
    """

    client: ClientProfile
    portfolio: PortfolioState
    family: Optional[object] = None