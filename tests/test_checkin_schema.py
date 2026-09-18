import pytest
from pydantic import ValidationError

from app.schemas.checkin import CheckinCreate


def test_checkin_requires_booking_or_customer_name() -> None:
    with pytest.raises(ValidationError):
        CheckinCreate()


def test_checkin_accepts_walk_in_customer_name() -> None:
    payload = CheckinCreate(customer_name="Walk-in Guest")

    assert payload.customer_name == "Walk-in Guest"
    assert payload.booking_id is None
