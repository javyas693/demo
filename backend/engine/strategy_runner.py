from backend.engine.decision_engine import DecisionEngine
from backend.strategies.neutral_strategy import TaxNeutralStrategy
from backend.strategies.harvest_strategy import HarvestStrategy
from backend.strategies.aggressive_strategy import AggressiveStrategy

class StrategyRunner:
    def __init__(self):
        self.strategies = {
            1: HarvestStrategy(),
            2: TaxNeutralStrategy(),
            3: AggressiveStrategy(),
        }

    def run(self, state, params):
        mode = DecisionEngine.decide(state)
        strategy = self.strategies.get(mode)

        if strategy is None:
            raise ValueError(f"Unknown mode {mode} returned from DecisionEngine")

        return strategy.run(state, params)
