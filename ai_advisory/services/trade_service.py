from __future__ import annotations
from dataclasses import replace
from datetime import datetime, date
from decimal import Decimal
from typing import Dict

from ai_advisory.portfolio.portfolio_state import PortfolioState
from ai_advisory.portfolio import ledger as ledger_mod
from ai_advisory.portfolio.trade_flow import (
    propose_from_latest_frontier,
    preview_buys_only,
    execute_buys_only,
)
from ai_advisory.frontier.store.fs_store import FileSystemFrontierStore
from .api_models import (
    TradePreviewRequest, TradePreviewResponse,
    TradeExecuteRequest, TradeExecuteResponse,
    BuyIntentDTO,
)


class TradeService:
    def __init__(self, store_root: str = "data/frontiers"):
        self.store = FileSystemFrontierStore(root=store_root)

    def _state_from_snapshot(self, snapshot) -> PortfolioState:
        # MVP: create an in-memory PortfolioState using holdings snapshot
        st = PortfolioState(
            schema_version="v1",
            engine_version="0.1.0",
            id="state_api",
            user_id="u_123",
            as_of=date.today(),
            created_at=datetime.now(),
        )

        # deposit cash into core sleeve
        if snapshot.cash and snapshot.cash > 0:
            ledger_mod.deposit(
                PortfolioState=st,
                user_id=st.user_id,
                created_at=datetime.now(),
                as_of=st.as_of,
                sleeve="core",
                amount=Decimal(snapshot.cash),
                idempotency_key="api:deposit",
            )

        # add positions by marking to market with implied prices (or direct position events if you have them)
        # MVP: directly mutate positions is not ideal; better is to add a "position_set" event later.
        # For now, we rely on allocate_cash_to_model only needing find_position() quantities.
        # If your PortfolioState doesn't allow direct positions, tell me and I'll adapt.

        # If PortfolioState has positions list, append.
        if hasattr(st, "positions"):
            for h in snapshot.holdings:
                st.positions.append(type(st.positions[0])(
                    symbol=h.symbol, sleeve=h.sleeve, quantity=float(h.quantity)
                )) if st.positions else st.positions.append(
                    # fallback: import your Position dataclass if needed
                    _make_position(h.symbol, h.sleeve, float(h.quantity))
                )
        return st

    def preview(self, req: TradePreviewRequest) -> TradePreviewResponse:
        proposal = propose_from_latest_frontier(
            store=self.store,
            as_of=req.proposal.as_of,
            model_id=req.proposal.model_id,
            risk_score=req.proposal.risk_score,
        )

        prices = req.prices

        def price_lookup(sym: str) -> Decimal:
            if sym.upper() not in prices:
                raise KeyError(f"Missing price for {sym}")
            return Decimal(prices[sym.upper()])

        state = self._state_from_snapshot(req.holdings)

        intents = preview_buys_only(
            PortfolioState=state,
            proposal=proposal,
            price_lookup=price_lookup,
            min_trade_notional=req.min_trade_notional,
        )

        return TradePreviewResponse(
            intents=[BuyIntentDTO(i.symbol, i.quantity, i.price, i.notional) for i in intents],
            blocked_reason=None if proposal.frontier_status.value == "APPROVED" else f"Frontier is {proposal.frontier_status.value} (preview allowed; execution blocked)",
        )

    def execute(self, req: TradeExecuteRequest) -> TradeExecuteResponse:
        proposal = propose_from_latest_frontier(
            store=self.store,
            as_of=req.proposal.as_of,
            model_id=req.proposal.model_id,
            risk_score=req.proposal.risk_score,
        )

        prices = req.prices

        def price_lookup(sym: str) -> Decimal:
            if sym.upper() not in prices:
                raise KeyError(f"Missing price for {sym}")
            return Decimal(prices[sym.upper()])

        state = self._state_from_snapshot(req.holdings)

        intents = execute_buys_only(
            PortfolioState=state,
            proposal=proposal,
            price_lookup=price_lookup,
            ledger=ledger_mod,
            store=self.store,
            run_id=req.run_id,
            user_id=req.user_id,
            min_trade_notional=req.min_trade_notional,
        )

        # after execute_buys_only, store status should be EXECUTED
        status_after = self.store.get_status(req.proposal.as_of, proposal.frontier_version).value

        return TradeExecuteResponse(
            intents=[BuyIntentDTO(i.symbol, i.quantity, i.price, i.notional) for i in intents],
            frontier_version=proposal.frontier_version,
            status_after=status_after,
        )


def _make_position(symbol: str, sleeve: str, qty: float):
    # last-resort helper if PortfolioState.Position class isn't accessible
    class _Pos:
        def __init__(self, symbol, sleeve, quantity):
            self.symbol = symbol
            self.sleeve = sleeve
            self.quantity = quantity
    return _Pos(symbol, sleeve, qty)