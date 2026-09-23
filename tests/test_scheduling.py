from datetime import datetime, timezone

import pytest

from app.services.scheduling import (
    BUSINESS_TIMEZONE,
    DEFAULT_CLOSE_TIME,
    DEFAULT_OPEN_TIME,
    SchedulingError,
    booking_window,
    ensure_bookable_start,
    iter_slot_starts,
    windows_overlap,
)


def test_default_daily_availability_window_is_nine_to_eight() -> None:
    assert DEFAULT_OPEN_TIME.hour == 9
    assert DEFAULT_OPEN_TIME.minute == 0
    assert DEFAULT_CLOSE_TIME.hour == 20
    assert DEFAULT_CLOSE_TIME.minute == 0


def test_business_timezone_is_east_africa_time() -> None:
    assert BUSINESS_TIMEZONE.utcoffset(None).total_seconds() == 3 * 60 * 60


def test_booking_window_uses_service_duration() -> None:
    start = datetime(2026, 9, 18, 10, 0, tzinfo=timezone.utc)

    window = booking_window(start, 90)

    assert window.start_time == start
    assert window.end_time == datetime(2026, 9, 18, 11, 30, tzinfo=timezone.utc)


def test_booking_window_rejects_naive_datetime() -> None:
    with pytest.raises(SchedulingError):
        booking_window(datetime(2026, 9, 18, 10, 0), 60)


def test_ensure_bookable_start_requires_a_future_whole_hour() -> None:
    moment = datetime(2026, 9, 18, 10, 15, tzinfo=timezone.utc)

    assert ensure_bookable_start(
        datetime(2026, 9, 19, 8, 0, tzinfo=timezone.utc),
        at_time=moment,
    ) == datetime(2026, 9, 19, 8, 0, tzinfo=timezone.utc)

    with pytest.raises(SchedulingError, match="whole hour"):
        ensure_bookable_start(
            datetime(2026, 9, 19, 8, 30, tzinfo=timezone.utc),
            at_time=moment,
        )

    with pytest.raises(SchedulingError, match="future"):
        ensure_bookable_start(
            datetime(2026, 9, 18, 10, 0, tzinfo=timezone.utc),
            at_time=moment,
        )


def test_iter_slot_starts_respects_duration_and_step() -> None:
    start = datetime(2026, 9, 18, 9, 0, tzinfo=timezone.utc)
    end = datetime(2026, 9, 18, 11, 0, tzinfo=timezone.utc)

    slots = iter_slot_starts(start, end, duration_min=60, step_min=30)

    assert slots == [
        datetime(2026, 9, 18, 9, 0, tzinfo=timezone.utc),
        datetime(2026, 9, 18, 9, 30, tzinfo=timezone.utc),
        datetime(2026, 9, 18, 10, 0, tzinfo=timezone.utc),
    ]


def test_iter_slot_starts_rejects_invalid_step() -> None:
    start = datetime(2026, 9, 18, 9, 0, tzinfo=timezone.utc)
    end = datetime(2026, 9, 18, 11, 0, tzinfo=timezone.utc)

    with pytest.raises(SchedulingError):
        iter_slot_starts(start, end, duration_min=60, step_min=0)


@pytest.mark.parametrize(
    ("start", "end", "other_start", "other_end", "expected"),
    [
        (10, 11, 9, 10, False),
        (10, 11, 11, 12, False),
        (10, 11, 9, 10.5, True),
        (10, 11, 10.5, 12, True),
        (10, 11, 10, 11, True),
    ],
)
def test_windows_overlap(start, end, other_start, other_end, expected) -> None:
    day = datetime(2026, 9, 18, tzinfo=timezone.utc)

    def hour(value):
        whole = int(value)
        minute = int((value - whole) * 60)
        return day.replace(hour=whole, minute=minute)

    assert windows_overlap(hour(start), hour(end), hour(other_start), hour(other_end)) is expected
