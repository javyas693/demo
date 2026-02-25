from __future__ import annotations

from decimal import Decimal, ROUND_DOWN


def round_quantity(qty: Decimal, *, allow_fractional: bool, dp: int = 6) -> Decimal:
    if qty <= 0:
        return Decimal("0")
    if not allow_fractional:
        return qty.to_integral_value(rounding=ROUND_DOWN)
    quantum = Decimal("1").scaleb(-dp)  # 1e-dp
    return qty.quantize(quantum, rounding=ROUND_DOWN)