"""HOSPolicy values and the domain types' invariants.

"guide p. N" is the FMCSA Interstate Truck Driver's Guide to Hours of Service
(April 2022). "DN" is a planning decision listed in the README.
"""

import dataclasses

import pytest

from planner.domain.models import Activity, DutyStatus, Event, Leg, TripInput
from planner.domain.policy import DEFAULT_POLICY, HOUR, HOSPolicy


class TestPolicyLimits:
    def test_driving_limit_and_window_match_guide_p6(self):
        assert DEFAULT_POLICY.max_driving_min == 11 * HOUR
        assert DEFAULT_POLICY.duty_window_min == 14 * HOUR
        assert DEFAULT_POLICY.daily_rest_min == 10 * HOUR

    def test_break_matches_guide_p10(self):
        assert DEFAULT_POLICY.break_after_driving_min == 8 * HOUR
        assert DEFAULT_POLICY.break_min == 30

    def test_cycle_and_restart_match_guide_p10_p11(self):
        assert DEFAULT_POLICY.cycle_limit_min == 70 * HOUR
        assert DEFAULT_POLICY.restart_min == 34 * HOUR

    def test_assumptions_match_decisions(self):
        assert DEFAULT_POLICY.pre_trip_min == 30  # D4
        assert DEFAULT_POLICY.fuel_interval_miles == 1000  # D7
        assert DEFAULT_POLICY.fuel_stop_min == 30  # D7
        assert DEFAULT_POLICY.max_avg_speed_mph == 55  # D8
        assert DEFAULT_POLICY.pickup_min == DEFAULT_POLICY.dropoff_min == 60  # D13

    def test_policy_is_immutable(self):
        with pytest.raises(dataclasses.FrozenInstanceError):
            DEFAULT_POLICY.max_driving_min = 12 * HOUR

    def test_limits_can_be_overridden_for_tests(self):
        assert HOSPolicy(max_driving_min=10 * HOUR).max_driving_min == 10 * HOUR


class TestStatusForActivity:
    @pytest.mark.parametrize(
        ("activity", "status"),
        [
            (Activity.DRIVING, DutyStatus.DRIVING),
            (Activity.PRE_TRIP, DutyStatus.ON_DUTY),  # D4
            (Activity.PICKUP, DutyStatus.ON_DUTY),  # D13
            (Activity.DROPOFF, DutyStatus.ON_DUTY),  # D13
            (Activity.FUEL, DutyStatus.ON_DUTY),  # D7, guide p. 5 and 18
            (Activity.REST, DutyStatus.SLEEPER_BERTH),  # D5
            (Activity.BREAK, DutyStatus.OFF_DUTY),  # D5
            (Activity.RESTART, DutyStatus.OFF_DUTY),  # D11
        ],
    )
    def test_every_activity_has_a_log_line(self, activity, status):
        assert DEFAULT_POLICY.status_for(activity) is status


class TestSpeedCap:
    """D8: never plan faster than 55 mph on average."""

    def test_router_faster_than_cap_is_slowed_to_55_mph(self):
        assert DEFAULT_POLICY.drive_minutes(550, router_min=480) == 600

    def test_router_slower_than_cap_is_kept(self):
        assert DEFAULT_POLICY.drive_minutes(110, router_min=150) == 150

    def test_partial_minutes_round_up(self):
        assert DEFAULT_POLICY.drive_minutes(100, router_min=90.2) == 110  # 109.09 -> 110

    def test_zero_distance_is_zero_minutes(self):
        assert DEFAULT_POLICY.drive_minutes(0, router_min=0) == 0


class TestLeg:
    def test_rejects_negative_values(self):
        with pytest.raises(ValueError):
            Leg(distance_miles=-1, drive_min=10)

    def test_rejects_distance_without_time(self):
        with pytest.raises(ValueError):
            Leg(distance_miles=5, drive_min=0)

    def test_zero_mile_leg_is_valid(self):
        assert Leg(distance_miles=0, drive_min=0).drive_min == 0

    def test_rejects_driving_time_without_distance(self):
        # The engine divides miles by minutes; 0 miles in 30 minutes made that 0 mph.
        with pytest.raises(ValueError, match="without distance"):
            Leg(distance_miles=0, drive_min=30)


class TestTripInput:
    def test_rejects_negative_cycle_hours(self):
        with pytest.raises(ValueError):
            TripInput(Leg(0, 0), Leg(10, 11), cycle_used_min=-1)

    def test_current_location_at_pickup_is_valid(self):
        trip = TripInput(Leg(distance_miles=0, drive_min=0), Leg(250, 273), cycle_used_min=0)
        assert trip.to_pickup.drive_min == 0
        assert trip.total_miles == 250

    def test_total_miles(self):
        trip = TripInput(Leg(100, 110), Leg(250, 273), cycle_used_min=0)
        assert trip.total_miles == 350


class TestEvent:
    def drive(self, **overrides):
        values = dict(
            activity=Activity.DRIVING,
            status=DutyStatus.DRIVING,
            start_min=0,
            end_min=60,
            start_mile=0.0,
            end_mile=55.0,
        )
        return Event(**(values | overrides))

    def test_duration(self):
        assert self.drive().duration_min == 60

    def test_rejects_zero_length(self):
        with pytest.raises(ValueError):
            self.drive(end_min=0)

    def test_rejects_driving_backwards(self):
        with pytest.raises(ValueError):
            self.drive(end_mile=-1.0)

    def test_rejects_moving_while_not_driving(self):
        with pytest.raises(ValueError):
            Event(Activity.FUEL, DutyStatus.ON_DUTY, 0, 30, 10.0, 12.0)

    def test_rejects_driving_status_on_other_activities(self):
        with pytest.raises(ValueError):
            Event(Activity.FUEL, DutyStatus.DRIVING, 0, 30, 10.0, 10.0)
