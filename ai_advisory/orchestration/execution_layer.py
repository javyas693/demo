import logging
import datetime
from typing import Dict, Any, List

from ai_advisory.portfolio.portfolio_state import PortfolioState
from ai_advisory.orchestration.trace_logger import trace_log
from ai_advisory.orchestration.ledger import record_event

def execute_trades(portfolio_state: PortfolioState, trades: List[Dict[str, Any]], prices: Dict[str, float], month: int) -> Dict[str, Any]:
    """
    Core Execution Layer: Translates trade intents into monetary and holding mutations.
    Strategies emit trades; the Execution Layer guarantees isolated state updates.
    """
    cash_change = 0.0
    positions_updated = {}
    
    # Isolate holds into pure dicts for non-destructive derivation
    inc_holds = dict(portfolio_state.income_holdings)
    mod_holds = dict(portfolio_state.model_holdings)
    new_shares = portfolio_state.shares
    
    for trade in trades:
        sym = trade["symbol"]
        qty = trade["quantity"]
        side = trade["side"].upper()
        
        # Determine execution price (allow explicit override for deterministic unwinds)
        price = trade.get("price_override", prices.get(sym, prices.get("DEFAULT", 0.0)))
        
        if side == "BUY":
            cost = qty * price
            
            # [CAPITAL CONSTRAINT] MODULE 4: FINAL SAFETY CHECK
            # Check if cost exceeds currently available cash (initial cash + accumulated cash_change from SELLs)
            current_cash = portfolio_state.cash + cash_change
            if cost > current_cash:
                qty = current_cash / price
                cost = qty * price
                trade["quantity"] = qty # adjust trade quantity downward
                
            cash_change -= cost
            
            if sym in ["JEPQ", "TLTW", "SVOL"]:
                inc_holds[sym] = inc_holds.get(sym, 0.0) + qty
            elif sym in ["VTI", "TLT", "VXUS", "BND"]:
                mod_holds[sym] = mod_holds.get(sym, 0.0) + qty
                
            positions_updated[sym] = positions_updated.get(sym, 0.0) + qty
            
        elif side == "SELL":
            proceeds = qty * price
            cash_change += proceeds
            
            if sym in ["JEPQ", "TLTW", "SVOL"]:
                inc_holds[sym] = inc_holds.get(sym, 0.0) - qty
            elif sym in ["VTI", "TLT", "VXUS", "BND"]:
                mod_holds[sym] = mod_holds.get(sym, 0.0) - qty
            else:
                # Default assume legacy concentrated position
                new_shares -= qty
                
            positions_updated[sym] = positions_updated.get(sym, 0.0) - qty

        event = {
            "timestamp": datetime.datetime.now().isoformat(),
            "month": month,
            "type": "TRADE_EXECUTED",
            "symbol": sym,
            "side": side,
            "quantity": qty,
            "price": price,
            "notional": qty * price
        }
        record_event(event)

    # Emit Trace Log
    if len(trades) > 0:
        trace_log(f"\n--- [EXECUTION LAYER] ---")
        trace_log(f"Trades Executed: {len(trades)}")
        trace_log(f"Cash Δ: {cash_change:,.2f}")
        trace_log(f"Positions Updated: {positions_updated}")

    # emit validation using generic orchestrator logic later
    final_cash = portfolio_state.cash + cash_change

    return {
        "cash_change": cash_change,
        "positions_updated": positions_updated,
        "executed_trades": trades,
        "new_income_holdings": inc_holds,
        "new_model_holdings": mod_holds,
        "new_shares": new_shares
    }
