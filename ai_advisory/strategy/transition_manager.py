import uuid
from datetime import datetime
from typing import List

from ai_advisory.api.plan_models import TradeAction, TradePlan
from ai_advisory.core.frontier_status import FrontierStatus
from ai_advisory.frontier.store.base import FrontierStore
from ai_advisory.frontier.weights import weights_tuple_to_dict


class TransitionManager:
    """
    Bridge between CP unwinds and MP allocations.
    """

    def __init__(self, store: FrontierStore, as_of: str, model_id: str):
        self.store = store
        self.as_of = as_of
        self.model_id = model_id

    def get_reinvestment_orders(
        self, net_proceeds: float, risk_score: int
    ) -> List[TradePlan]:
        """
        Calculates the reinvestment TradePlans given the proceeds to deploy.
        
        1. Loads the APPROVED weights from the FrontierStore for the given risk_score.
        2. Calculates the dollar amount for each ETF in the target frontier.
        3. Generates a list of TradePlan objects (Action: BUY).
        """
        fv = self.store.get_latest(self.as_of, self.model_id)
        if not fv:
            raise ValueError(
                f"No frontier found for model {self.model_id} as of {self.as_of}"
            )

        status = self.store.get_status(self.as_of, fv)
        if status != FrontierStatus.APPROVED:
            raise ValueError(f"Frontier {fv} is not APPROVED (status: {status.value})")

        fr = self.store.get(self.as_of, fv)

        # Risk score is 1-indexed (1..N)
        if risk_score < 1 or risk_score > len(fr.points_sampled):
            raise ValueError(f"Invalid risk_score {risk_score}")

        p = fr.points_sampled[risk_score - 1]

        # Extract weights
        if isinstance(p.weights, dict):
            w_map = {str(k): float(v) for k, v in p.weights.items()}
            assets = tuple(fr.assets)
        else:
            assets = tuple(fr.assets)
            w_map = weights_tuple_to_dict(tuple(float(x) for x in p.weights), assets)

        # Normalize weights to ensure they sum to 1
        s = sum(float(v) for v in w_map.values())
        if s > 0:
            w_map = {k: float(v) / s for k, v in w_map.items()}

        actions = []
        for ticker, weight in w_map.items():
            amount = net_proceeds * weight
            if amount > 0:
                actions.append(
                    TradeAction(
                        type="BUY",
                        symbol=ticker,
                        dollars=amount,
                        model_key=f"{self.model_id}:{fv}",
                        notes=f"Reinvesting {weight:.2%} of net proceeds into {ticker}",
                    )
                )

        plan = TradePlan(
            plan_id=str(uuid.uuid4()),
            program_key=f"transition_{self.model_id}_{risk_score}",
            created_at=datetime.utcnow(),
            summary=f"Reinvest ${net_proceeds:,.2f} into model {self.model_id} at risk score {risk_score}",
            why=["Reinvesting concentrated position sale proceeds into target frontier"],
            cash_delta_estimate=-net_proceeds,  # Spending the proceeds
            actions=actions,
            requires_approval=True,
        )

        return [plan]
