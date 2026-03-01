from __future__ import annotations

from ai_advisory.frontier.store.fs_store import FileSystemFrontierStore
from ai_advisory.portfolio.trade_flow import propose_from_latest_frontier
from .api_models import FrontierProposalRequest, FrontierProposalResponse


class FrontierService:
    def __init__(self, store_root: str = "data/frontiers"):
        self.store = FileSystemFrontierStore(root=store_root)

    def propose(self, req: FrontierProposalRequest) -> FrontierProposalResponse:
        p = propose_from_latest_frontier(
            store=self.store,
            as_of=req.as_of,
            model_id=req.model_id,
            risk_score=req.risk_score,
        )
        return FrontierProposalResponse(
            as_of=p.as_of,
            model_id=p.model_id,
            frontier_version=p.frontier_version,
            frontier_status=p.frontier_status.value,
            risk_score=p.risk_score,
            exp_return=p.exp_return,
            vol=p.vol,
            sharpe=p.sharpe,
            target_weights=p.target_weights,
        )