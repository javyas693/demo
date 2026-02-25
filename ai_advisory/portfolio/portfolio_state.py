from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, date


@dataclass
class Position:
    symbol: str
    quantity: float
    last_price: float
    sleeve: str = "core"

    @property
    def market_value(self) -> float:
        return float(self.quantity) * float(self.last_price)


@dataclass
class PortfolioState:
    schema_version: str
    engine_version: str
    id: str
    user_id: str
    as_of: date
    created_at: datetime

    cash_by_sleeve: Dict[str, float] = field(default_factory=lambda: {"core": 0.0, "income": 0.0})
    positions: List[Position] = field(default_factory=list)
    applied_event_ids: set = field(default_factory=set)

    def cash_total(self) -> float:
        return sum(self.cash_by_sleeve.values())

    def total_market_value(self) -> float:
        return sum(p.market_value for p in self.positions)

    def total_portfolio_value(self) -> float:
        return self.cash_total() + self.total_market_value()

    def find_position(self, symbol: str, sleeve: str) -> Optional[Position]:
        for p in self.positions:
            if p.symbol == symbol and p.sleeve == sleeve:
                return p
        return None

    def upsert_position(self, symbol: str, sleeve: str, quantity_delta: float, price: float):
        pos = self.find_position(symbol, sleeve)
        if pos is None:
            self.positions.append(Position(symbol, quantity_delta, price, sleeve))
        else:
            pos.quantity += quantity_delta
            pos.last_price = price

        self.positions = [p for p in self.positions if abs(p.quantity) > 1e-9]