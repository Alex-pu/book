from decimal import Decimal

from app.services.fees import calculate_fee


def test_calculate_fee_returns_fee_and_net() -> None:
    fee, net = calculate_fee(Decimal("1000.00"), Decimal("5"))

    assert fee == Decimal("50.00")
    assert net == Decimal("950.00")


def test_calculate_fee_rounds_to_cents() -> None:
    fee, net = calculate_fee(Decimal("999.99"), Decimal("2.5"))

    assert fee == Decimal("25.00")
    assert net == Decimal("974.99")
