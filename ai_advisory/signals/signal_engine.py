import logging
from typing import Any, Dict, List, Optional

try:
    from ai_advisory.orchestration.trace_logger import trace_log
except ImportError:
    def trace_log(msg: str):
        print(msg)

logger = logging.getLogger(__name__)


def generate_signals(
    state: Any,
    market_data: Any,
    price_history: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """
    Generate market signals: momentum, macro regime, volatility.

    Inputs
    ------
    state        : PortfolioState — used for risk_score, concentration_pct
    market_data  : dict of {ticker: current_price}
    price_history: optional list of recent CP prices (most recent last).
                   When provided, momentum is computed from real price trend.

    Output contract (frozen — downstream code depends on these keys):
      momentum_score  : float  [-1.0, 1.0]   negative = bearish, positive = bullish
      macro_regime    : str    "risk_on" | "neutral" | "risk_off"
      volatility_level: str    "low" | "medium" | "high"
      unwind_urgency  : float  [0.0, 1.0]   composite unwind signal
    """
    momentum_score   = 0.0
    macro_regime     = "neutral"
    volatility_level = "medium"
    unwind_urgency   = 0.0

    try:
        # ── 1. Momentum from real price history ──────────────────────────────
        if price_history and len(price_history) >= 3:
            momentum_score = _compute_momentum(price_history)
        elif isinstance(market_data, dict):
            # Fallback: SPY-based macro proxy
            spy = market_data.get("SPY", 0)
            if isinstance(spy, (int, float)) and spy > 0:
                momentum_score = 0.3 if spy > 400 else (-0.3 if spy < 350 else 0.0)

        # ── 2. Macro regime from SPY level ───────────────────────────────────
        if isinstance(market_data, dict) and "SPY" in market_data:
            spy = market_data.get("SPY", 0)
            if isinstance(spy, (int, float)):
                if spy > 420:
                    macro_regime = "risk_on"
                elif spy < 350:
                    macro_regime = "risk_off"

        # ── 3. Volatility from risk score + momentum magnitude ───────────────
        risk_score = getattr(state, "risk_score", 50)
        mom_magnitude = abs(momentum_score)

        if risk_score > 75 or mom_magnitude > 0.6:
            volatility_level = "high"
        elif risk_score < 30 and mom_magnitude < 0.2:
            volatility_level = "low"
        else:
            volatility_level = "medium"

        # ── 4. Composite unwind urgency ──────────────────────────────────────
        # Combines concentration, momentum direction, and macro regime.
        # Used by orchestrator to decide unwind rate — separate from the binary
        # enable_unwind gate.
        concentration = getattr(state, "concentration_pct", 0.0) * 100.0
        tlh_remaining = getattr(state, "tlh_inventory", 0.0)

        # Concentration pressure: 0 at threshold, scales to 1 at full concentration
        concentration_threshold = 15.0  # matches orchestrator
        concentration_pressure = max(0.0, (concentration - concentration_threshold) / 85.0)

        # Momentum penalty: bearish momentum → sell faster
        # Bullish momentum → hold, let price run
        momentum_penalty = max(0.0, -momentum_score)  # 0 when bullish, up to 1 when deeply bearish

        # TLH availability: more TLH → more room to unwind tax-efficiently
        tlh_factor = min(1.0, tlh_remaining / 100_000.0) if tlh_remaining > 0 else 0.0

        # Regime adjustment
        regime_mult = {"risk_on": 0.7, "neutral": 1.0, "risk_off": 1.3}.get(macro_regime, 1.0)

        unwind_urgency = min(1.0, concentration_pressure * (0.5 + 0.5 * momentum_penalty) * regime_mult)

    except Exception as e:
        logger.warning(f"Signal generation error: {e}")

    signals = {
        "momentum_score":   float(max(-1.0, min(1.0, momentum_score))),
        "macro_regime":     macro_regime,
        "volatility_level": volatility_level,
        "unwind_urgency":   float(max(0.0, min(1.0, unwind_urgency))),
    }

    trace_log("[SIGNALS]")
    trace_log(f"momentum_score: {signals['momentum_score']:.3f}")
    trace_log(f"macro_regime: {signals['macro_regime']}")
    trace_log(f"volatility_level: {signals['volatility_level']}")
    trace_log(f"unwind_urgency: {signals['unwind_urgency']:.3f}")

    return signals


def _compute_momentum(price_history: List[float]) -> float:
    """
    Compute momentum score from a list of prices (most recent last).

    Uses a simple dual-window approach:
      - Short window (3 periods): recent direction
      - Long window (all): trend direction
    Returns a score in [-1.0, 1.0].
    """
    prices = [float(p) for p in price_history if p and p > 0]
    if len(prices) < 3:
        return 0.0

    # Short-term return: last 3 periods
    short_return = (prices[-1] - prices[-3]) / prices[-3]

    # Long-term return: full window
    long_return = (prices[-1] - prices[0]) / prices[0]

    # Blend: 60% short, 40% long — normalized to [-1, 1]
    raw = 0.6 * short_return + 0.4 * long_return

    # Clamp to [-1, 1]: a 20%+ move saturates the signal
    return float(max(-1.0, min(1.0, raw / 0.20)))


def external_signal_adapter(input_data: Any) -> Dict[str, Any]:
    """
    Maps external signal formats to the strict internal contract.
    Allows easy replacement by factor models or ML later.
    """
    momentum_score   = 0.0
    macro_regime     = "neutral"
    volatility_level = "medium"

    if isinstance(input_data, dict):
        momentum_score   = float(input_data.get("momentum", momentum_score))
        macro_regime     = str(input_data.get("macro", macro_regime))
        volatility_level = str(input_data.get("volatility", volatility_level))

    return {
        "momentum_score":   float(max(-1.0, min(1.0, momentum_score))),
        "macro_regime":     macro_regime if macro_regime in ("risk_on", "neutral", "risk_off") else "neutral",
        "volatility_level": volatility_level if volatility_level in ("low", "medium", "high") else "medium",
        "unwind_urgency":   0.0,
    }
