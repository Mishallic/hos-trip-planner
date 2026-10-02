"""Daily log sheets built from a timeline.

"guide p. N" is the FMCSA Interstate Truck Driver's Guide to Hours of Service
(April 2022). "DN" is a planning decision listed in the README.
"""

from datetime import date, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from planner.domain.hos_engine import plan_trip
from planner.domain.log_builder import DAY_MIN, Bracket, Segment, build_daily_logs
from planner.domain.models import Activity, DutyStatus, Event, StopReason, TripInput
from planner.domain.policy import DEFAULT_POLICY, HOUR

from .hos_helpers import leg
from .test_hos_property import PROPERTY_SETTINGS, trips

H = HOUR
OFF, SB, DR, ON = (
    DutyStatus.OFF_DUTY,
    DutyStatus.SLEEPER_BERTH,
    DutyStatus.DRIVING,
    DutyStatus.ON_DUTY,
)
CST = -6 * 60


def events_from(*spec: tuple[Activity, int, float]) -> list[Event]:
    """Back-to-back events from (activity, minutes, miles driven) triples."""
    events, now, mile = [], 0, 0.0
    for activity, minutes, miles in spec:
        events.append(
            Event(
                activity,
                DEFAULT_POLICY.status_for(activity),
                now,
                now + minutes,
                mile,
                mile + miles,
            )
        )
        now, mile = now + minutes, mile + miles
    return events


def build(events, start=datetime(2026, 10, 5, 8, 0), cycle_used_min=0, offset=CST):
    return build_daily_logs(events, start, offset, cycle_used_min)


def lines(log) -> list[tuple[DutyStatus, int, int]]:
    return [(s.status, s.start_min, s.end_min) for s in log.segments]


class TestOneDayTrip:
    EVENTS = events_from(
        (Activity.PRE_TRIP, 30, 0),
        (Activity.DRIVING, 2 * H, 110),
        (Activity.PICKUP, 1 * H, 0),
        (Activity.DRIVING, 3 * H, 165),
        (Activity.DROPOFF, 1 * H, 0),
    )

    def test_one_sheet_padded_with_off_duty_before_and_after(self):  # D10
        [log] = build(self.EVENTS)  # 08:00 to 15:30

        assert log.date == date(2026, 10, 5)
        assert lines(log) == [
            (OFF, 0, 8 * H),
            (ON, 8 * H, 8 * H + 30),
            (DR, 8 * H + 30, 10 * H + 30),
            (ON, 10 * H + 30, 11 * H + 30),
            (DR, 11 * H + 30, 14 * H + 30),
            (ON, 14 * H + 30, 15 * H + 30),
            (OFF, 15 * H + 30, DAY_MIN),
        ]

    def test_totals_sum_to_24_hours(self):  # guide p. 16
        [log] = build(self.EVENTS)

        assert log.totals_min == {OFF: 16 * H + 30, SB: 0, DR: 5 * H, ON: 2 * H + 30}
        assert sum(log.totals_min.values()) == DAY_MIN
        assert log.on_duty_hours == 7.5

    def test_miles_and_positions(self):
        [log] = build(self.EVENTS)

        assert log.miles_today == pytest.approx(275)
        assert (log.start_mile, log.end_mile) == (0, 275)

    def test_one_remark_per_change_of_status(self):  # guide p. 17
        [log] = build(self.EVENTS)

        assert [(r.minute, r.status, r.label, r.mile) for r in log.remarks] == [
            (8 * H, ON, "Pre-trip inspection", 0),
            (8 * H + 30, DR, "Driving", 0),
            (10 * H + 30, ON, "Pickup", 110),
            (11 * H + 30, DR, "Driving", 110),
            (14 * H + 30, ON, "Drop-off", 275),
            (15 * H + 30, OFF, "Off duty", 275),
        ]

    def test_brackets_cover_every_stop_but_not_the_off_duty_padding(self):  # guide p. 18
        [log] = build(self.EVENTS)

        assert log.brackets == (
            Bracket(8 * H, 8 * H + 30, 0),
            Bracket(10 * H + 30, 11 * H + 30, 110),
            Bracket(14 * H + 30, 15 * H + 30, 275),
        )


class TestMidnight:
    def test_event_crossing_midnight_is_split_with_its_miles(self):
        # Driving 23:00-01:00 at 55 mph: 55 miles on each sheet.
        events = events_from(
            (Activity.PRE_TRIP, 30, 0),
            (Activity.DRIVING, 2 * H, 110),
            (Activity.DROPOFF, 1 * H, 0),
        )
        day1, day2 = build(events, start=datetime(2026, 10, 5, 22, 30))

        assert lines(day1)[-1] == (DR, 23 * H, DAY_MIN)
        assert lines(day2)[0] == (DR, 0, 1 * H)
        assert day1.miles_today == pytest.approx(55)
        assert day2.miles_today == pytest.approx(55)
        assert day1.end_mile == day2.start_mile == pytest.approx(55)

    def test_status_carrying_on_past_midnight_is_not_a_new_remark(self):
        # The rest starts at 20:00 on day 1 and runs to 06:00 on day 2.
        events = events_from(
            (Activity.PRE_TRIP, 30, 0),
            (Activity.DRIVING, 11 * H + 30, 632.5),
            (Activity.REST, 10 * H, 0),
            (Activity.DRIVING, 1 * H, 55),
            (Activity.DROPOFF, 1 * H, 0),
        )
        day1, day2 = build(events)

        assert [(r.minute, r.label) for r in day1.remarks][-1] == (20 * H, "10-hour rest")
        assert [(r.minute, r.label) for r in day2.remarks] == [
            (6 * H, "Driving"),
            (7 * H, "Drop-off"),
            (8 * H, "Off duty"),
        ]
        assert lines(day2)[0] == (SB, 0, 6 * H)

    def test_trip_ending_exactly_at_midnight_has_no_empty_extra_sheet(self):
        events = events_from((Activity.PRE_TRIP, 30, 0), (Activity.DRIVING, 30, 27.5))

        logs = build(events, start=datetime(2026, 10, 5, 23, 0))

        assert len(logs) == 1
        assert lines(logs[0])[-1] == (DR, 23 * H + 30, DAY_MIN)
        assert logs[0].remarks[-1].label == "Driving"  # no "Off duty" at the end

    def test_trip_ending_one_minute_after_midnight_gets_a_second_sheet(self):
        events = events_from((Activity.PRE_TRIP, 30, 0), (Activity.DRIVING, 31, 28))

        logs = build(events, start=datetime(2026, 10, 5, 23, 0))

        assert len(logs) == 2
        assert lines(logs[1]) == [(DR, 0, 1), (OFF, 1, DAY_MIN)]

    def test_trip_starting_at_midnight_has_no_padding_before_it(self):
        events = events_from((Activity.PRE_TRIP, 30, 0), (Activity.DRIVING, 1 * H, 55))

        [log] = build(events, start=datetime(2026, 10, 5, 0, 0))

        assert lines(log)[0] == (ON, 0, 30)
        assert log.remarks[0].minute == 0  # off duty before the trip, so a change at 00:00

    def test_rest_across_midnight_gets_a_bracket_on_both_sheets(self):
        events = events_from(
            (Activity.PRE_TRIP, 30, 0),
            (Activity.DRIVING, 11 * H + 30, 632.5),
            (Activity.REST, 10 * H, 0),
            (Activity.DRIVING, 1 * H, 55),
            (Activity.DROPOFF, 1 * H, 0),
        )
        day1, day2 = build(events)

        assert day1.brackets[-1] == Bracket(20 * H, DAY_MIN, 632.5)
        assert day2.brackets[0] == Bracket(0, 6 * H, 632.5)


class TestMergingAndLabels:
    def test_same_status_activities_share_a_segment_and_a_remark(self):
        # Pre-trip then pickup: both on duty, so one line and one remark.
        events = events_from(
            (Activity.PRE_TRIP, 30, 0),
            (Activity.PICKUP, 1 * H, 0),
            (Activity.DRIVING, 1 * H, 55),
            (Activity.DROPOFF, 1 * H, 0),
        )
        [log] = build(events)

        assert lines(log)[1] == (ON, 8 * H, 9 * H + 30)
        assert log.remarks[0].label == "Pre-trip inspection, Pickup"
        assert log.remarks[0].activities == (Activity.PRE_TRIP, Activity.PICKUP)

    def test_remark_keeps_the_reason_a_stop_was_forced(self):
        events = plan_trip(TripInput(leg(9 * H), leg(1 * H), 0))
        [log] = build(events, start=datetime(2026, 10, 5, 6, 0))

        brk = next(r for r in log.remarks if r.status is OFF and r.minute < 20 * H)
        assert brk.label == "30-minute break"
        assert brk.reasons == (StopReason.BREAK_REQUIRED,)


class TestRecap:
    """D12: A = cycle hours entered + on duty since, B = 70 - A."""

    EVENTS = events_from(
        (Activity.PRE_TRIP, 30, 0),
        (Activity.DRIVING, 11 * H + 30, 632.5),
        (Activity.REST, 10 * H, 0),
        (Activity.PRE_TRIP, 30, 0),
        (Activity.DRIVING, 1 * H, 55),
        (Activity.DROPOFF, 1 * H, 0),
    )

    def test_a_adds_each_days_on_duty_time_to_the_hours_entered(self):
        day1, day2 = build(self.EVENTS, cycle_used_min=40 * H)

        assert day1.recap.on_duty_today_min == 12 * H
        assert day1.recap.cycle_used_min == 52 * H
        assert day1.recap.available_tomorrow_min == 18 * H
        assert day2.recap.on_duty_today_min == 2 * H + 30
        assert day2.recap.cycle_used_min == 54 * H + 30

    def test_restart_resets_a(self):
        events = events_from(
            (Activity.PRE_TRIP, 30, 0),
            (Activity.DRIVING, 4 * H, 220),
            (Activity.RESTART, 34 * H, 0),
            (Activity.PRE_TRIP, 30, 0),
            (Activity.DRIVING, 2 * H, 110),
            (Activity.DROPOFF, 1 * H, 0),
        )
        # 08:00 start: the restart runs from 12:30 on day 1 to 22:30 on day 2. Then
        # day 2 has a pre-trip and 1 h of driving before midnight.
        day1, day2, day3 = build(events, cycle_used_min=60 * H)

        assert day1.recap.cycle_used_min == 64 * H + 30
        assert day2.recap.cycle_used_min == 1 * H + 30  # back to zero at 22:30, then 1.5 h
        assert day3.recap.cycle_used_min == 3 * H + 30

    def test_b_never_goes_below_zero(self):
        # D14: on-duty work past 70 is allowed, so A can pass 70.
        events = events_from((Activity.DRIVING, 1 * H, 55), (Activity.DROPOFF, 1 * H, 0))
        [log] = build(events, cycle_used_min=69 * H)

        assert log.recap.cycle_used_min == 71 * H
        assert log.recap.available_tomorrow_min == 0


class TestTimeZone:
    def test_fixed_offset_keeps_every_sheet_24_hours_across_dst(self):  # D17
        # US DST starts at 02:00 on 8 March 2026. The terminal's offset at the start
        # (CST, -6 h) is kept for the whole trip.
        events = plan_trip(TripInput(leg(20 * H), leg(20 * H), 0))
        logs = build(events, start=datetime(2026, 3, 7, 18, 0), offset=CST)

        assert len(logs) >= 3
        assert [log.date for log in logs[:3]] == [
            date(2026, 3, 7),
            date(2026, 3, 8),
            date(2026, 3, 9),
        ]
        for log in logs:
            assert sum(log.totals_min.values()) == DAY_MIN
            assert log.starts_at.utcoffset() == timedelta(hours=-6)

    def test_seconds_are_dropped(self):
        events = events_from((Activity.DRIVING, 1 * H, 55), (Activity.DROPOFF, 1 * H, 0))

        [log] = build(events, start=datetime(2026, 10, 5, 8, 0, 45))

        assert lines(log)[1] == (DR, 8 * H, 9 * H)

    def test_aware_start_is_rejected(self):
        events = events_from((Activity.DRIVING, 1 * H, 55))
        aware = datetime(2026, 10, 5, 8, 0).astimezone()

        with pytest.raises(ValueError):
            build_daily_logs(events, aware, CST, 0)


def test_instructors_worked_example_totals():
    # The paper-log video: off duty to 6:30, 30 min pre-trip, drive, 30 min scale
    # (on duty), drive, 30 min break (off duty), drive to 17:30, 1.5 h off duty,
    # then the sleeper berth for the night. Totals: 8.5 + 5 + 9.5 + 1 = 24.
    events = events_from(
        (Activity.PRE_TRIP, 30, 0),
        (Activity.DRIVING, 2 * H, 110),
        (Activity.FUEL, 30, 0),  # stands in for the scale: 30 min on duty
        (Activity.DRIVING, 3 * H, 165),
        (Activity.BREAK, 30, 0),
        (Activity.DRIVING, 4 * H + 30, 247.5),
        (Activity.BREAK, 1 * H + 30, 0),  # off duty after driving
        (Activity.REST, 5 * H, 0),  # sleeper berth to midnight
    )
    [log] = build(events, start=datetime(2026, 10, 5, 6, 30))

    assert log.totals_min == {OFF: 8 * H + 30, SB: 5 * H, DR: 9 * H + 30, ON: 1 * H}
    assert log.on_duty_hours == 10.5
    assert [s.status for s in log.segments][-2:] == [OFF, SB]
    assert isinstance(log.segments[0], Segment)


# Property test: random engine trips, started at a random local time.

starts = st.datetimes(min_value=datetime(2026, 1, 1), max_value=datetime(2027, 12, 31, 23, 59)).map(
    lambda d: d.replace(second=0, microsecond=0)
)
offsets = st.integers(min_value=-10 * 60, max_value=-3 * 60).map(lambda m: m - m % 30)


@PROPERTY_SETTINGS
@given(trip=trips, start=starts, offset=offsets)
def test_random_trips_make_valid_sheets(trip, start, offset):
    events = plan_trip(trip)
    logs = build_daily_logs(events, start, offset, trip.cycle_used_min)

    # One sheet per calendar day the trip touches; ending at midnight adds none.
    trip_end = start + timedelta(minutes=events[-1].end_min)
    last_day = (trip_end - timedelta(minutes=1)).date()
    assert len(logs) == (last_day - start.date()).days + 1
    assert [log.date for log in logs] == [
        start.date() + timedelta(days=i) for i in range(len(logs))
    ]

    for log in logs:
        assert sum(log.totals_min.values()) == DAY_MIN
        assert log.segments[0].start_min == 0
        assert log.segments[-1].end_min == DAY_MIN
        for before, after in zip(log.segments, log.segments[1:], strict=False):
            assert before.end_min == after.start_min
            assert before.status is not after.status
        assert all(s.end_min > s.start_min for s in log.segments)
        assert log.starts_at.utcoffset() == timedelta(minutes=offset)

    assert sum(log.miles_today for log in logs) == pytest.approx(trip.total_miles, abs=1e-6)
    assert logs[-1].end_mile == pytest.approx(trip.total_miles, abs=1e-6)

    # One remark per change of duty status, counted from the events directly.
    statuses = [OFF] + [e.status for e in events]
    if trip_end.time() != datetime.min.time():
        statuses.append(OFF)  # off duty after the drop-off
    changes = sum(a is not b for a, b in zip(statuses, statuses[1:], strict=False))
    assert sum(len(log.remarks) for log in logs) == changes
