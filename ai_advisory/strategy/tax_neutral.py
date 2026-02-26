from __future__ import annotations

from dataclasses import dataclass
from math import floor


@dataclass
class TaxNeutralSellResult:
    shares_sold: int
    trigger_met: bool
    trigger_price: float
    realized_stock_gain: float
    stock_sale_proceeds: float
    remainder_loss_added_to_tlh: float


def handle_option_loss_tax_neutral_single_lot(
    *,
    shares: float,
    cost_basis: float,
    cash: float,
    option_loss_abs: float,
    current_price: float,
    share_reduction_trigger_pct: float,
) -> tuple[TaxNeutralSellResult, float, float, float]:
    """
    Returns:
      (result, new_shares, new_cash, tlh_delta)

    NOTE: taxes are NOT computed here (engine owns tax rate + tax accumulation).
    """
    option_loss_abs = float(option_loss_abs)
    current_price = float(current_price)

    trigger_price = float(cost_basis) * (1.0 + float(share_reduction_trigger_pct))
    trigger_met = current_price >= trigger_price

    if not trigger_met:
        # TLH only; no share selling.
        result = TaxNeutralSellResult(
            shares_sold=0,
            trigger_met=False,
            trigger_price=trigger_price,
            realized_stock_gain=0.0,
            stock_sale_proceeds=0.0,
            remainder_loss_added_to_tlh=option_loss_abs,
        )
        return result, float(shares), float(cash), option_loss_abs

    gain_per_share = current_price - float(cost_basis)
    if gain_per_share <= 0:
        result = TaxNeutralSellResult(
            shares_sold=0,
            trigger_met=True,
            trigger_price=trigger_price,
            realized_stock_gain=0.0,
            stock_sale_proceeds=0.0,
            remainder_loss_added_to_tlh=option_loss_abs,
        )
        return result, float(shares), float(cash), option_loss_abs

    shares_to_sell = int(floor(option_loss_abs / gain_per_share))
    shares_to_sell = min(shares_to_sell, int(shares))

    if shares_to_sell <= 0:
        result = TaxNeutralSellResult(
            shares_sold=0,
            trigger_met=True,
            trigger_price=trigger_price,
            realized_stock_gain=0.0,
            stock_sale_proceeds=0.0,
            remainder_loss_added_to_tlh=option_loss_abs,
        )
        return result, float(shares), float(cash), option_loss_abs

    realized_stock_gain = float(shares_to_sell) * gain_per_share
    stock_sale_proceeds = float(shares_to_sell) * current_price

    new_shares = float(shares) - float(shares_to_sell)
    new_cash = float(cash) + stock_sale_proceeds

    remainder_loss = option_loss_abs - realized_stock_gain
    tlh_delta = remainder_loss if remainder_loss > 0 else 0.0

    result = TaxNeutralSellResult(
        shares_sold=int(shares_to_sell),
        trigger_met=True,
        trigger_price=trigger_price,
        realized_stock_gain=float(realized_stock_gain),
        stock_sale_proceeds=float(stock_sale_proceeds),
        remainder_loss_added_to_tlh=float(tlh_delta),
    )
    return result, new_shares, new_cash, float(tlh_delta)