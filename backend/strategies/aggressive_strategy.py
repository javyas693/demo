from backend.strategies.base_strategy import BaseStrategy
import logging

class AggressiveStrategy(BaseStrategy):
    def run(self, state, params):
        # Sell double the normal required shares to aggressively reduce exposure
        shares_to_sell = params.shares_required * 2
        
        proceeds = shares_to_sell * state.price
        cost = shares_to_sell * state.cost_basis
        
        realized_gain = max(0.0, proceeds - cost)
        taxable_gain = max(0.0, realized_gain - params.option_loss_available)
        taxes = taxable_gain * params.tax_rate
            
        action = "AGGRESSIVE_SELL" if shares_to_sell > 0 else "NO-SELL"
        
        # No new TLH creation, only consumption
        net_tlh = max(0.0, params.option_loss_available - realized_gain)
        
        logger = logging.getLogger(__name__)
        logger.debug(
            f"STRATEGY=aggressive "
            f"ACTION={action} "
            f"SHARES_SOLD={shares_to_sell} "
            f"NET_TLH={net_tlh}"
        )

        return {
            "shares_sold": shares_to_sell,
            "cash_generated": proceeds,
            "taxes": taxes,
            "realized_gain": realized_gain,
            "tlh_delta": net_tlh,
            "trigger_price": state.cost_basis * 1.2, # Matching decision engine logic conceptually
            "action": action
        }
