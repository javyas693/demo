from backend.strategies.neutral_strategy import TaxNeutralStrategy
from backend.strategies.harvest_strategy import HarvestStrategy

class StrategyRunner:
    def __init__(self):
        self.strategies = {
            "tax_neutral": TaxNeutralStrategy(),
            "harvest": HarvestStrategy(),
        }

    def run(self, strategy_name, state, params):
        strategy = self.strategies.get(strategy_name)

        if strategy is None:
            raise ValueError(f"Unknown strategy {strategy_name}")

        return strategy.run(state, params)
