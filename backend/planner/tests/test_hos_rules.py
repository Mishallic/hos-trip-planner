"""HOS engine rules, one test class per rule.

"guide p. N" is the FMCSA Interstate Truck Driver's Guide to Hours of Service
(April 2022). "DN" is a planning decision listed in the README.
"""

import pytest

from planner.domain.hos_engine import plan_trip
from planner.domain.models import Activity, DutyStatus, StopReason, TripInput
from planner.domain.policy import DEFAULT_POLICY, HOSPolicy

from .hos_helpers import H, first, leg, plan, timeline

# A long pickup (detention at the shipper) makes the 14-hour window bind before
# the 11-hour limit. Only the assumption changes; every FMCSA limit stays real.
LONG_PICKUP = HOSPolicy(pickup_min=4 * H)


def activities(events) -> list[str]:
    return [e.activity.value for e in events]


class TestDriving:
    def test_short_trip(self):
        events = plan(2 * H, 3 * H)

        assert timeline(events) == [
            ("driving", 0, 2 * H),
            ("pickup", 2 * H, 3 * H),
            ("driving", 3 * H, 6 * H),
            ("dropoff", 6 * H, 7 * H),
        ]

    def test_current_location_at_pickup(self):
        events = plan(0, 3 * H)

        assert timeline(events) == [
            ("pickup", 0, 1 * H),
            ("driving", 1 * H, 4 * H),
            ("dropoff", 4 * H, 5 * H),
        ]


class TestPickupAndDropoff:
    """D13: pickup and drop-off each take 1 hour, on duty."""

    def test_both_last_one_hour_on_duty(self):
        events = plan(2 * H, 3 * H)

        for activity in ("pickup", "dropoff"):
            event = first(events, activity)
            assert event.duration_min == 1 * H
            assert event.status is DutyStatus.ON_DUTY

    def test_pickup_is_at_the_end_of_the_first_leg(self):
        pickup = first(plan(2 * H, 3 * H), "pickup")

        assert pickup.start_mile == pytest.approx(2 * 55)

    def test_trip_ends_with_the_dropoff(self):
        events = plan(2 * H, 3 * H)

        assert events[-1].activity is Activity.DROPOFF


class TestElevenHourDrivingLimit:
    """Guide p. 6: no more than 11 hours of driving after 10 hours off duty."""

    def test_exactly_eleven_hours_needs_no_rest(self):
        events = plan(5 * H, 6 * H)

        assert Activity.REST not in {e.activity for e in events}

    def test_twelfth_hour_comes_after_a_ten_hour_rest(self):
        events = plan(6 * H, 6 * H)

        assert timeline(events) == [
            ("driving", 0, 6 * H),
            ("pickup", 6 * H, 7 * H),
            ("driving", 7 * H, 12 * H),
            ("rest", 12 * H, 22 * H),
            ("driving", 22 * H, 23 * H),
            ("dropoff", 23 * H, 24 * H),
        ]
        assert first(events, "rest").reason is StopReason.DRIVING_LIMIT

    def test_rest_is_taken_where_the_driving_stopped(self):
        rest = first(plan(6 * H, 6 * H), "rest")

        assert rest.start_mile == rest.end_mile == pytest.approx(11 * 55)

    @pytest.mark.parametrize("total_h", [11, 12, 22, 23, 35, 48])
    def test_never_more_than_eleven_hours_between_rests(self, total_h):
        # plan() checks the limit on every timeline; this runs it over many lengths.
        plan(total_h * H // 2, total_h * H - total_h * H // 2)

    def test_long_trip(self):
        events = plan(12 * H, 13 * H)  # 25 hours of driving

        assert activities(events) == [
            "driving",
            "break",
            "driving",
            "rest",
            "driving",
            "pickup",
            "driving",
            "break",
            "driving",
            "rest",
            "driving",
            "dropoff",
        ]
        assert sum(e.duration_min for e in events if e.activity is Activity.DRIVING) == 25 * H


class TestTenHourRest:
    """Guide p. 6-7: 10 consecutive hours off duty reset the 11- and 14-hour clocks."""

    def test_rest_lasts_ten_hours_in_the_sleeper_berth(self):  # D5
        rest = first(plan(6 * H, 6 * H), "rest")

        assert rest.duration_min == 10 * H
        assert rest.status is DutyStatus.SLEEPER_BERTH

    def test_rest_restores_a_full_eleven_hours(self):
        events = plan(11 * H, 11 * H)

        assert timeline(events) == [
            ("driving", 0, 8 * H),
            ("break", 8 * H, 8 * H + 30),
            ("driving", 8 * H + 30, 11 * H + 30),
            ("pickup", 11 * H + 30, 12 * H + 30),
            ("rest", 12 * H + 30, 22 * H + 30),
            ("driving", 22 * H + 30, 30 * H + 30),  # 8 h + 3 h = a full 11 again
            ("break", 30 * H + 30, 31 * H),
            ("driving", 31 * H, 34 * H),
            ("dropoff", 34 * H, 35 * H),
        ]

    def test_rest_restarts_the_fourteen_hour_window(self):
        events = plan(0, 30 * H, policy=LONG_PICKUP)

        assert timeline(events) == [
            ("pickup", 0, 4 * H),
            ("driving", 4 * H, 12 * H),
            ("break", 12 * H, 12 * H + 30),
            ("driving", 12 * H + 30, 14 * H),
            ("rest", 14 * H, 24 * H),
            ("driving", 24 * H, 32 * H),  # a new window from 24 h
            ("break", 32 * H, 32 * H + 30),
            ("driving", 32 * H + 30, 35 * H + 30),
            ("rest", 35 * H + 30, 45 * H + 30),
            ("driving", 45 * H + 30, 53 * H + 30),
            ("break", 53 * H + 30, 54 * H),
            ("driving", 54 * H, 55 * H + 30),
            ("dropoff", 55 * H + 30, 56 * H + 30),
        ]
        rests = [e for e in events if e.activity is Activity.REST]
        assert [r.reason for r in rests] == [StopReason.DUTY_WINDOW, StopReason.DRIVING_LIMIT]


class TestFourteenHourWindow:
    """Guide p. 6: no driving after the 14th hour since coming on duty."""

    def test_window_counts_from_the_first_on_duty_minute_not_the_first_drive(self):
        # Pickup is the first work here. Chunk 8 adds the pre-trip and re-tests this.
        events = plan(0, 15 * H, policy=LONG_PICKUP)

        assert timeline(events)[:5] == [
            ("pickup", 0, 4 * H),
            ("driving", 4 * H, 12 * H),
            ("break", 12 * H, 12 * H + 30),
            ("driving", 12 * H + 30, 14 * H),  # stops at 14 h: the window began at 0
            ("rest", 14 * H, 24 * H),
        ]

    def test_window_can_end_driving_mid_leg(self):
        events = plan(1 * H, 12 * H, policy=LONG_PICKUP)

        assert timeline(events) == [
            ("driving", 0, 1 * H),
            ("pickup", 1 * H, 5 * H),
            ("driving", 5 * H, 13 * H),
            ("break", 13 * H, 13 * H + 30),
            ("driving", 13 * H + 30, 14 * H),
            ("rest", 14 * H, 24 * H),
            ("driving", 24 * H, 27 * H + 30),
            ("dropoff", 27 * H + 30, 28 * H + 30),
        ]

    def test_on_duty_work_is_not_limited_by_the_window(self):
        # D14, guide p. 6 and 18: other work after the 14th hour is allowed.
        events = plan(10 * H + 30, 2 * H, policy=LONG_PICKUP)

        pickup = first(events, "pickup")
        assert pickup.start_min == 11 * H  # 10.5 h of driving plus the break
        assert pickup.end_min == 15 * H  # runs past the window's end at 14 h
        assert events[events.index(pickup) + 1].activity is Activity.REST

    def test_window_expiring_at_the_end_of_pickup_puts_the_rest_after_it(self):
        events = plan(9 * H + 30, 2 * H, policy=LONG_PICKUP)

        assert timeline(events) == [
            ("driving", 0, 8 * H),
            ("break", 8 * H, 8 * H + 30),
            ("driving", 8 * H + 30, 10 * H),
            ("pickup", 10 * H, 14 * H),
            ("rest", 14 * H, 24 * H),
            ("driving", 24 * H, 26 * H),
            ("dropoff", 26 * H, 27 * H),
        ]
        assert first(events, "rest").reason is StopReason.DUTY_WINDOW

    def test_window_expiring_at_dropoff_still_allows_the_dropoff(self):
        events = plan(1 * H, 8 * H + 30, policy=LONG_PICKUP)

        assert timeline(events)[-2:] == [
            ("driving", 13 * H + 30, 14 * H),
            ("dropoff", 14 * H, 15 * H),  # D14; nothing left to drive, so no rest
        ]


class TestWindowAndDrivingLimitTogether:
    """Guide p. 6: both limits apply; whichever runs out first forces the rest."""

    def test_driving_limit_first(self):
        rest = first(plan(6 * H, 6 * H), "rest")

        assert rest.start_min == 12 * H  # 11 h driven, only 12 h of the window used
        assert rest.reason is StopReason.DRIVING_LIMIT

    def test_window_first(self):
        rest = first(plan(1 * H, 12 * H, policy=LONG_PICKUP), "rest")

        assert rest.start_min == 14 * H  # window used up after only 9.5 h of driving
        assert rest.reason is StopReason.DUTY_WINDOW

    def test_both_at_the_same_minute_reports_the_driving_limit(self):
        # 2.5 h pickup + 8 h driving + 30 min break + 3 h driving: 11 h driven at 14 h.
        events = plan(0, 12 * H, policy=HOSPolicy(pickup_min=2 * H + 30))

        rest = first(events, "rest")
        assert rest.start_min == 14 * H
        assert rest.reason is StopReason.DRIVING_LIMIT


class TestThirtyMinuteBreak:
    """Guide p. 10: a 30-minute break after 8 hours of cumulative driving."""

    def test_break_comes_exactly_at_eight_hours_of_driving(self):
        events = plan(10 * H, 1 * H)

        assert timeline(events)[:3] == [
            ("driving", 0, 8 * H),
            ("break", 8 * H, 8 * H + 30),
            ("driving", 8 * H + 30, 10 * H + 30),
        ]
        assert first(events, "break").reason is StopReason.BREAK_REQUIRED

    def test_break_is_thirty_minutes_off_duty(self):  # D5
        brk = first(plan(10 * H, 1 * H), "break")

        assert brk.duration_min == 30
        assert brk.status is DutyStatus.OFF_DUTY

    def test_break_is_taken_where_the_driving_stopped(self):
        brk = first(plan(10 * H, 1 * H), "break")

        assert brk.start_mile == brk.end_mile == pytest.approx(8 * 55)

    def test_driving_counts_cumulatively_across_short_stops(self):
        # A 20-minute pickup is too short to count, so 5 h + 5 h still needs a break.
        events = plan(5 * H, 5 * H, policy=HOSPolicy(pickup_min=20))

        assert timeline(events) == [
            ("driving", 0, 5 * H),
            ("pickup", 5 * H, 5 * H + 20),
            ("driving", 5 * H + 20, 8 * H + 20),
            ("break", 8 * H + 20, 8 * H + 50),  # after 8 h of driving, not 8 h in a row
            ("driving", 8 * H + 50, 10 * H + 50),
            ("dropoff", 10 * H + 50, 11 * H + 50),
        ]

    def test_one_hour_pickup_counts_as_the_break(self):
        # D9: any 30 consecutive non-driving minutes reset the count, on duty included.
        events = plan(7 * H + 30, 3 * H)

        assert Activity.BREAK not in {e.activity for e in events}

    def test_pickup_between_two_long_drives_avoids_a_break(self):
        # D9: 7.5 h + pickup + 7.5 h. Without D9 a break would come 30 min after the
        # pickup. With it, the 11-hour limit ends the day first and no break is needed.
        events = plan(7 * H + 30, 7 * H + 30)

        assert Activity.BREAK not in {e.activity for e in events}
        assert timeline(events)[:4] == [
            ("driving", 0, 7 * H + 30),
            ("pickup", 7 * H + 30, 8 * H + 30),
            ("driving", 8 * H + 30, 12 * H),
            ("rest", 12 * H, 22 * H),
        ]

    def test_break_does_not_pause_or_extend_the_window(self):
        # Pickup at 1-5 h, so the window still ends at 14 h despite the break at 13 h.
        events = plan(1 * H, 12 * H, policy=LONG_PICKUP)

        brk = first(events, "break")
        rest = first(events, "rest")
        assert (brk.start_min, brk.end_min) == (13 * H, 13 * H + 30)
        assert rest.start_min == 14 * H
        assert rest.reason is StopReason.DUTY_WINDOW

    def test_rest_due_at_the_same_minute_replaces_the_break(self):
        # Pickup resets the count, then 8 h of driving brings 11 h driven and 8 h
        # since the break together. The 10-hour rest also satisfies the break.
        events = plan(3 * H, 9 * H)

        assert Activity.BREAK not in {e.activity for e in events}
        rest = first(events, "rest")
        assert rest.start_min == 12 * H
        assert rest.reason is StopReason.DRIVING_LIMIT


class TestCycleInput:
    """Guide p. 10-11: the cycle limit is 70 hours, so more cannot have been used."""

    def test_more_than_seventy_hours_used_is_rejected(self):
        trip = TripInput(leg(60), leg(60), cycle_used_min=70 * H + 1)

        with pytest.raises(ValueError):
            plan_trip(trip)

    def test_exactly_seventy_hours_used_is_accepted(self):
        trip = TripInput(leg(60), leg(60), cycle_used_min=70 * H)

        assert plan_trip(trip)


def test_default_policy_is_used_when_none_is_given():
    trip = TripInput(leg(6 * H), leg(6 * H), cycle_used_min=0)

    assert plan_trip(trip) == plan_trip(trip, DEFAULT_POLICY)
