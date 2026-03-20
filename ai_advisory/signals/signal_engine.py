import logging
from typing import Dict, Any

try:
    from ai_advisory.orchestration.trace_logger import trace_log
except ImportError:
    # Fallback to standard print/logging if trace_logger is not found
    def trace_log(msg: str):
        print(msg)

logger = logging.getLogger(__name__)

def generate_signals(state: Any, market_data: Any) -> Dict[str, Any]:
    """
    Generate market signals (momentum, macro regime, volatility).
    This is a plug-and-play signal layer designed to be easily replaceable.
    
    Constraints: 
    - Output format is STRICT CONTRACT.
    - Deterministic logic only.
    """
    # Defensive default values matching strict contract
    momentum_score = 0.0
    macro_regime = "neutral"
    volatility_level = "medium"
    
    try:
        # SIMPLE VERSION IMPLEMENTATION
        
        # 1. Momentum: price vs moving average
        # In a real implementation this would calculate moving averages over market_data history
        # We use a deterministic fallback here if full history isn't passed
        # e.g., if market_data is just a dict of prices vs dict of dataframes
        momentum_score = 0.5 # Default positive momentum
        
        # 2. Macro: SPY trend direction
        # Simple check if SPY price exists and is above a certain threshold, else neutral
        if isinstance(market_data, dict) and "SPY" in market_data:
            spy_price = market_data.get("SPY", 0)
            if isinstance(spy_price, (int, float)):
                if spy_price > 400.0:
                    macro_regime = "risk_on"
                elif spy_price < 350.0:
                    macro_regime = "risk_off"

        # 3. Volatility: drawdown threshold
        # In a real implementation this checks max drawdown over trailing window
        # Deterministically set to 'low' for this simple iteration unless state indicates high risk
        if hasattr(state, "risk_score") and state.risk_score > 80:
            volatility_level = "high"
        else:
            volatility_level = "low"

    except Exception as e:
        logger.warning(f"Signal generation fallback due to error: {e}")

    # Compile exact contract output
    signals = {
        "momentum_score": float(max(-1.0, min(1.0, momentum_score))), # Clamp between -1 and 1
        "macro_regime": macro_regime,
        "volatility_level": volatility_level
    }
    
    # 7. Logging requirement
    trace_log("[SIGNALS]")
    trace_log(f"momentum_score: {signals['momentum_score']}")
    trace_log(f"macro_regime: {signals['macro_regime']}")
    trace_log(f"volatility_level: {signals['volatility_level']}")
    
    return signals


def external_signal_adapter(input_data: Any) -> Dict[str, Any]:
    """
    OPTIONAL adapter. Maps external signal formats to the strict format required.
    Allows easy replacement by factor models or ML later.
    """
    # Default to neutral signals if parsing fails
    momentum_score = 0.0
    macro_regime = "neutral"
    volatility_level = "medium"
    
    if isinstance(input_data, dict):
        momentum_score = float(input_data.get("momentum", momentum_score))
        macro_regime = str(input_data.get("macro", macro_regime))
        volatility_level = str(input_data.get("volatility", volatility_level))
        
    return {
        "momentum_score": float(max(-1.0, min(1.0, momentum_score))),
        "macro_regime": macro_regime if macro_regime in ["risk_on", "neutral", "risk_off"] else "neutral",
        "volatility_level": volatility_level if volatility_level in ["low", "medium", "high"] else "medium"
    }
