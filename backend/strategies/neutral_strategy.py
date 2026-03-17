from backend.strategies.base_strategy import BaseStrategy

class TaxNeutralStrategy(BaseStrategy):
    def run(self, state, params):
        trigger_price = state.cost_basis * (1.0 + params.trigger_percent)
        
        if state.price < trigger_price:
            return {
                "shares_sold": 0,
                "cash_generated": 0.0,
                "taxes": 0.0,
                "realized_gain": 0.0,
                "tlh_delta": params.option_loss_available, # If no sell, full option loss is carried over to TLH pool
                "trigger_price": trigger_price,
                "action": "NO-SELL"
            }
            
        shares_to_sell = params.shares_required
        proceeds = shares_to_sell * state.price
        cost = shares_to_sell * state.cost_basis
        
        realized_gain = max(0.0, proceeds - cost)
        
        taxable_gain = max(0.0, realized_gain - params.option_loss_available)
        taxes = taxable_gain * params.tax_rate
            
        action = "SELL" if shares_to_sell > 0 else "NO-SELL"
        
        net_tlh = max(0.0, params.option_loss_available - realized_gain)
        
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(
            f"STRATEGY=tax_neutral "
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
            "trigger_price": trigger_price,
            "action": action
        }
