from decimal import Decimal, ROUND_HALF_UP


KES_CENT = Decimal("0.01")


def calculate_fee(amount: Decimal, fee_percent: Decimal) -> tuple[Decimal, Decimal]:
    fee = (amount * fee_percent / Decimal("100")).quantize(KES_CENT, rounding=ROUND_HALF_UP)
    net = (amount - fee).quantize(KES_CENT, rounding=ROUND_HALF_UP)
    return fee, net
