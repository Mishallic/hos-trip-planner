"""HOS engine rules, one test class per rule.

"guide p. N" is the FMCSA Interstate Truck Driver's Guide to Hours of Service
(April 2022). "DN" is a planning decision listed in the README.
"""

import pytest

from planner.domain.hos_engine import plan_trip
from planner.domain.models import Activity, DutyStatus, TripInput
from planner.domain.policy import DEFAULT_POLICY

from .hos_helpers import H, leg, plan, timeline


class TestDriving:
    def test_short_trip_is_one_drive(self):
        events = plan(2 * H, 3 * H)

        assert timeline(events) == [("driving", 0, 5 * H)]

    def test_drive_continues_across_the_legs(self):
        events = plan(1 * H, 1 * H)

        assert len(events) == 1
        assert events[0].end_mile == pytest.approx(110)

    def test_current_location_at_pickup(self):
        events = plan(0, 3 * H)

        assert timeline(events) == [("driving", 0, 3 * H)]


class TestElevenHourDrivingLimit:
    """Guide p. 6: no more than 11 hours of driving after 10 hours off duty."""

    def test_exactly_eleven_hours_needs_no_rest(self):
        events = plan(5 * H, 6 * H)

        assert timeline(events) == [("driving", 0, 11 * H)]

    def test_twelfth_hour_comes_after_a_ten_hour_rest(self):
        events = plan(6 * H, 6 * H)

        assert timeline(events) == [
            ("driving", 0, 11 * H),
            ("rest", 11 * H, 21 * H),
            ("driving", 21 * H, 22 * H),
        ]

    def test_rest_is_taken_where_the_driving_stopped(self):
        rest = plan(6 * H, 6 * H)[1]

        assert rest.start_mile == rest.end_mile == pytest.approx(11 * 55)

    @pytest.mark.parametrize("total_h", [11, 12, 22, 23, 35, 48])
    def test_never_more_than_eleven_hours_between_rests(self, total_h):
        events = plan(total_h * H // 2, total_h * H - total_h * H // 2)

        driven = 0
        for event in events:
            if event.activity is Activity.REST:
                driven = 0
            elif event.activity is Activity.DRIVING:
                driven += event.duration_min
                assert driven <= DEFAULT_POLICY.max_driving_min

    def test_long_trip_rests_once_per_eleven_hours(self):
        events = plan(12 * H, 13 * H)  # 25 hours of driving

        assert [e.activity.value for e in events] == [
            "driving",
            "rest",
            "driving",
            "rest",
            "driving",
        ]
        assert sum(e.duration_min for e in events if e.activity is Activity.DRIVING) == 25 * H


class TestTenHourRest:
    """Guide p. 6-7: 10 consecutive hours off duty reset the 11-hour limit."""

    def test_rest_lasts_ten_hours(self):
        rest = plan(6 * H, 6 * H)[1]

        assert rest.duration_min == 10 * H

    def test_rest_is_logged_in_the_sleeper_berth(self):  # D5
        rest = plan(6 * H, 6 * H)[1]

        assert rest.status is DutyStatus.SLEEPER_BERTH

    def test_rest_restores_a_full_eleven_hours(self):
        events = plan(11 * H, 11 * H)

        assert timeline(events) == [
            ("driving", 0, 11 * H),
            ("rest", 11 * H, 21 * H),
            ("driving", 21 * H, 32 * H),
        ]


class TestCycleInput:
    """Guide p. 10-11: the cycle limit is 70 hours, so more cannot have been used."""

    def test_more_than_seventy_hours_used_is_rejected(self):
        trip = TripInput(leg(60), leg(60), cycle_used_min=70 * H + 1)

        with pytest.raises(ValueError):
            plan_trip(trip)

    def test_exactly_seventy_hours_used_is_accepted(self):
        trip = TripInput(leg(60), leg(60), cycle_used_min=70 * H)

        assert plan_trip(trip)
