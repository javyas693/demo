from backend.strategies.base_strategy import BaseStrategy

class HarvestStrategy(BaseStrategy):
    def run(self, state, params):
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(
            f"STRATEGY=harvest "
            f"ACTION=HARVEST_ONLY "
            f"SHARES_SOLD=0"
        )

        return {
            "shares_sold": 0,
            "cash_generated": 0.0,
            "taxes": 0.0,
            "realized_gain": 0.0,
            "tlh_delta": params.option_loss_available,
            "trigger_price": state.cost_basis,
            "action": "HARVEST_ONLY"
        }
