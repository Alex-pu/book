from datetime import datetime, timezone
from uuid import uuid4

from app.models.booking import Booking
from app.services.sms import booking_confirmed_message, checkout_thanks_message


def test_booking_confirmed_message_uses_booking_details() -> None:
    booking = Booking(
        id=uuid4(),
        service_id=uuid4(),
        staff_id=uuid4(),
        customer_name="Amina",
        customer_phone="254712345678",
        start_time=datetime(2026, 9, 18, 14, 30, tzinfo=timezone.utc),
        end_time=datetime(2026, 9, 18, 15, 30, tzinfo=timezone.utc),
        status="confirmed",
    )

    message = booking_confirmed_message(booking)

    assert message.phone == "254712345678"
    assert message.template == "booking_confirmed"
    assert "18 Sep 2026 14:30" in message.body


def test_checkout_thanks_message() -> None:
    message = checkout_thanks_message("254700000000")

    assert message.phone == "254700000000"
    assert message.template == "checkin_thanks"
    assert "Thank you" in message.body
