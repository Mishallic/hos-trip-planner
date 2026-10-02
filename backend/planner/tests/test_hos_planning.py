"""Pre-trip inspections and fuel stops, planned with the real default policy.

"guide p. N" is the FMCSA Interstate Truck Driver's Guide to Hours of Service
(April 2022). "DN" is a planning decision listed in the README.
"""

from dataclasses import replace

import pytest

from planner.domain.models import Activity, DutyStatus, StopReason
from planner.domain.policy import DEFAULT_POLICY

from .hos_helpers import H, first, plan, timeline


def count(events, activity: str) -> int:
    return sum(e.activity.value == activity for e in events)


class TestPreTrip:
    """D4: 30 minutes on duty before the first drive of every duty period."""

    def test_trip_starts_with_a_pre_trip(self):
        events = plan(2 * H, 3 * H)

        assert timeline(events) == [
            ("pre_trip", 0, 30),
            ("driving", 30, 2 * H + 30),
            ("pickup", 2 * H + 30, 3 * H + 30),
            ("driving", 3 * H + 30, 6 * H + 30),
            ("dropoff", 6 * H + 30, 7 * H + 30),
        ]
        assert first(events, "pre_trip").status is DutyStatus.ON_DUTY

    def test_every_ten_hour_rest_is_followed_by_a_pre_trip(self):
        events = plan(6 * H, 6 * H)

        assert timeline(events) == [
            ("pre_trip", 0, 30),
            ("driving", 30, 6 * H + 30),
            ("pickup", 6 * H + 30, 7 * H + 30),
            ("driving", 7 * H + 30, 12 * H + 30),
            ("rest", 12 * H + 30, 22 * H + 30),
            ("pre_trip", 22 * H + 30, 23 * H),
            ("driving", 23 * H, 24 * H),
            ("dropoff", 24 * H, 25 * H),
        ]

    def test_restart_mid_trip_is_followed_by_a_pre_trip(self):
        # 65 h used + 30 min pre-trip + 4.5 h driving = 70 h at 5 h.
        events = plan(6 * H, 1 * H, cycle_used_min=65 * H)

        assert timeline(events)[:5] == [
            ("pre_trip", 0, 30),
            ("driving", 30, 5 * H),
            ("restart", 5 * H, 39 * H),
            ("pre_trip", 39 * H, 39 * H + 30),
            ("driving", 39 * H + 30, 41 * H),
        ]

    def test_starting_at_seventy_restarts_then_inspects(self):
        # A pre-trip first would be wasted: no driving fits after it until the restart.
        events = plan(2 * H, 1 * H, cycle_used_min=70 * H)

        assert timeline(events)[:3] == [
            ("restart", 0, 34 * H),
            ("pre_trip", 34 * H, 34 * H + 30),
            ("driving", 34 * H + 30, 36 * H + 30),
        ]

    def test_pre_trip_starts_the_fourteen_hour_window(self):
        # Guide p. 6. The chunk 5 test again, with the pre-trip as the first work.
        # A 5 h pickup leaves 7.5 h of the window, and driving stops at 14 h, not 14.5 h.
        events = plan(1 * H, 12 * H, policy=replace(DEFAULT_POLICY, pickup_min=5 * H))

        assert timeline(events)[:5] == [
            ("pre_trip", 0, 30),
            ("driving", 30, 1 * H + 30),
            ("pickup", 1 * H + 30, 6 * H + 30),
            ("driving", 6 * H + 30, 14 * H),
            ("rest", 14 * H, 24 * H),
        ]
        assert first(events, "rest").reason is StopReason.DUTY_WINDOW

    def test_pre_trip_counts_toward_the_cycle(self):
        # Guide p. 10: 67 h + 0.5 pre-trip + 1 h drive + 1 h pickup = 69.5 h, so only
        # 30 min of driving fits before the restart. Without counting it, 1 h would.
        events = plan(1 * H, 1 * H, cycle_used_min=67 * H)

        assert first(events, "restart").start_min == 3 * H

    def test_no_pre_trip_when_nothing_is_left_to_drive(self):
        # The trip ends at the pickup point, so the last period has no drive.
        events = plan(11 * H, 0)

        assert timeline(events) == [
            ("pre_trip", 0, 30),
            ("driving", 30, 8 * H + 30),
            ("break", 8 * H + 30, 9 * H),
            ("driving", 9 * H, 12 * H),
            ("pickup", 12 * H, 13 * H),
            ("dropoff", 13 * H, 14 * H),
        ]

    def test_starting_at_the_pickup_inspects_before_loading(self):
        # The duty period starts at the pickup, so the inspection comes first.
        events = plan(0, 3 * H)

        assert timeline(events) == [
            ("pre_trip", 0, 30),
            ("pickup", 30, 1 * H + 30),
            ("driving", 1 * H + 30, 4 * H + 30),
            ("dropoff", 4 * H + 30, 5 * H + 30),
        ]

    def test_starting_at_the_pickup_at_seventy_inspects_after_the_restart(self):
        # D14: the pickup still happens, but no driving fits before the restart, so
        # an inspection before it would be wasted.
        events = plan(0, 2 * H, cycle_used_min=70 * H)

        assert timeline(events) == [
            ("pickup", 0, 1 * H),
            ("restart", 1 * H, 35 * H),
            ("pre_trip", 35 * H, 35 * H + 30),
            ("driving", 35 * H + 30, 37 * H + 30),
            ("dropoff", 37 * H + 30, 38 * H + 30),
        ]


class TestFuel:
    """D7: 30 minutes on duty at or before every 1,000 miles, starting with a full tank."""

    def test_trip_under_a_thousand_miles_has_no_fuel_stop(self):
        events = plan(9 * H, 9 * H)  # 990 miles

        assert count(events, "fuel") == 0

    def test_fuel_stop_comes_at_or_before_a_thousand_miles(self):
        # 1,100 miles. The first day ends at 605 miles, so the tank lasts 430 more
        # minutes (394.2 miles at 55 mph, rounded down to whole minutes).
        events = plan(10 * H, 10 * H)

        fuel = first(events, "fuel")
        assert count(events, "fuel") == 1
        assert (fuel.start_min, fuel.end_min) == (30 * H + 40, 31 * H + 10)
        assert 999 < fuel.start_mile <= 1000
        assert fuel.status is DutyStatus.ON_DUTY
        assert fuel.reason is StopReason.FUEL_INTERVAL

    def test_fuel_stop_counts_as_the_break(self):
        # D9: after the rest, 430 min of driving, fuel, then 230 min more. That is
        # 11 h of driving with no break, because the fuel stop reset the 8-hour count.
        events = plan(10 * H, 12 * H)

        after_rest = events[events.index(first(events, "rest")) :]
        assert [e.activity.value for e in after_rest] == [
            "rest",
            "pre_trip",
            "driving",
            "fuel",
            "driving",
            "dropoff",
        ]

    def test_break_and_fuel_due_together_make_one_stop(self):
        # D15: on day 2 the break comes due at 962.5 miles, 40 min before fuel would.
        # The driver fuels then, and that stop is also the break.
        events = plan(2 * H, 17 * H + 30, policy=replace(DEFAULT_POLICY, pickup_min=4 * H))

        fuel = first(events, "fuel")
        assert count(events, "break") == 0
        assert count(events, "fuel") == 1
        assert (fuel.start_min, fuel.end_min) == (32 * H + 30, 33 * H)
        assert fuel.start_mile == pytest.approx(962.5)
        assert fuel.reason is StopReason.BREAK_REQUIRED
        neighbours = events[events.index(fuel) - 1 : events.index(fuel) + 2]
        assert [e.activity.value for e in neighbours] == ["driving", "fuel", "driving"]

    def test_break_stays_a_break_when_fuel_is_far_off(self):
        # Day 1 of the 1,100-mile trip: the break comes at 440 miles, 560 from empty.
        events = plan(10 * H, 10 * H)

        brk = first(events, "break")
        assert brk.start_min == 8 * H + 30
        assert brk.status is DutyStatus.OFF_DUTY

    def test_long_trip_fuels_every_thousand_miles(self):
        events = plan(40 * H, 40 * H)  # 4,400 miles

        fuel_miles = [e.start_mile for e in events if e.activity is Activity.FUEL]
        assert len(fuel_miles) == 4
        gaps = [b - a for a, b in zip([0.0, *fuel_miles], fuel_miles, strict=False)]
        assert all(gap <= 1000 for gap in gaps)


class TestEverythingTogether:
    """Every rule at once, with the real defaults. plan() checks each rule's
    invariants on the timeline independently of the engine."""

    @pytest.mark.parametrize(
        ("to_pickup_h", "to_dropoff_h", "cycle_used_h"),
        [
            (0, 3, 0),
            (5, 5, 0),
            (11, 11, 0),
            (20, 30, 0),
            (40, 40, 10),
            (3, 3, 69.5),
            (10, 10, 70),
            (0, 50, 65),
            (25, 1, 50),
        ],
    )
    def test_all_rules_hold(self, to_pickup_h, to_dropoff_h, cycle_used_h):
        events = plan(int(to_pickup_h * H), int(to_dropoff_h * H), int(cycle_used_h * H))

        assert events[-1].activity is Activity.DROPOFF
