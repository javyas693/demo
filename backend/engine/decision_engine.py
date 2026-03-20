import logging

class DecisionEngine:
    @staticmethod
    def decide(state):
        logger = logging.getLogger(__name__)
        
        mode = 2
        reason_codes = ["DEFAULT_TAX_NEUTRAL"]
        
        # We assume state has these attributes or we default them
        price = getattr(state, "current_price", None) or getattr(state, "price", 0.0)
        cost_basis = getattr(state, "cost_basis", 0.0)
        unrealized_gain = price - cost_basis
        tlh_inventory = getattr(state, "tlh_inventory", 0.0)
        client_constraint = getattr(state, "client_constraint", "none")
        
        if price < cost_basis:
            mode = 1
            reason_codes = ["PRICE_BELOW_COST_BASIS", "PRIORITIZE_HARVEST"]
        elif price > cost_basis * 1.2:
            mode = 3
            reason_codes = ["HIGH_UNREALIZED_GAIN", "SWITCH_AGGRESSIVE"]
            
        logger.info(
            f"\n[DECISION TRACE]\n"
            f"price={price}\n"
            f"cost_basis={cost_basis}\n"
            f"gain={unrealized_gain}\n"
            f"tlh={tlh_inventory}\n"
            f"constraint={client_constraint}\n"
            f"mode={mode}\n"
            f"reasons={reason_codes}\n"
        )
        return mode
