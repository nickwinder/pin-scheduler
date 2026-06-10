# tests/test_slots.py
import pytest
from datetime import datetime, time, timedelta

from slots import next_slots, taken_from_rows

WINDOW = dict(
    window_start=time(8, 0),
    window_end=time(20, 0),
    interval=timedelta(minutes=60),
)


def test_first_slot_respects_margin():
    now = datetime(2026, 6, 12, 8, 50)
    slots = next_slots(**WINDOW, taken=set(), now=now, count=1)
    # earliest allowed is 9:10, so 9:00 is skipped
    assert slots == [datetime(2026, 6, 12, 10, 0)]


def test_skips_taken_slots():
    now = datetime(2026, 6, 12, 7, 0)
    taken = {datetime(2026, 6, 12, 8, 0)}
    slots = next_slots(**WINDOW, taken=taken, now=now, count=2)
    assert slots == [datetime(2026, 6, 12, 9, 0), datetime(2026, 6, 12, 10, 0)]


def test_window_end_is_inclusive():
    now = datetime(2026, 6, 12, 19, 30)
    slots = next_slots(**WINDOW, taken=set(), now=now, count=1)
    assert slots == [datetime(2026, 6, 12, 20, 0)]


def test_rolls_over_to_next_day():
    now = datetime(2026, 6, 12, 19, 45)
    slots = next_slots(**WINDOW, taken=set(), now=now, count=2)
    assert slots == [datetime(2026, 6, 13, 8, 0), datetime(2026, 6, 13, 9, 0)]


def test_thirty_minute_interval():
    now = datetime(2026, 6, 12, 7, 0)
    slots = next_slots(
        window_start=time(8, 0), window_end=time(20, 0),
        interval=timedelta(minutes=30), taken=set(), now=now, count=3,
    )
    assert slots == [
        datetime(2026, 6, 12, 8, 0),
        datetime(2026, 6, 12, 8, 30),
        datetime(2026, 6, 12, 9, 0),
    ]


def test_inverted_window_raises():
    with pytest.raises(ValueError):
        next_slots(
            window_start=time(20, 0), window_end=time(8, 0),
            interval=timedelta(minutes=60), taken=set(),
            now=datetime(2026, 6, 12, 7, 0), count=1,
        )


def test_nonpositive_interval_raises():
    with pytest.raises(ValueError):
        next_slots(
            window_start=time(8, 0), window_end=time(20, 0),
            interval=timedelta(0), taken=set(),
            now=datetime(2026, 6, 12, 7, 0), count=1,
        )


def test_taken_from_rows_rejects_aware_datetimes():
    rows = [{"status": "scheduled", "scheduled_time": "2026-06-12T09:00+12:00"}]
    with pytest.raises(ValueError):
        taken_from_rows(rows)


def test_taken_from_rows_collects_scheduled():
    rows = [
        {"status": "scheduled", "scheduled_time": "2026-06-12T09:00"},
        {"status": "approved", "scheduled_time": ""},
    ]
    assert taken_from_rows(rows) == {datetime(2026, 6, 12, 9, 0)}
