"""Pre-trip inspections, fuel stops and long trips, planned with the real default policy.

"guide p. N" is the FMCSA Interstate Truck Driver's Guide to Hours of Service
(April 2022). "DN" is a planning decision listed in the README.
"""

from dataclasses import replace

import pytest

from planner.domain.hos_engine import plan_trip
from planner.domain.models import Activity, DutyStatus, Leg, StopReason, TripInput
from planner.domain.policy import DEFAULT_POLICY

from .hos_helpers import H, check_all, first, plan, timeline

WITHOUT_D20 = replace(DEFAULT_POLICY, min_drive_min=0)

# The D7 and D15 tests switch off fuelling before a rest (D16), which would move
# their fuel stops to the rest before them. TestFuelBeforeRest covers D16.
NO_EARLY_FUEL = replace(DEFAULT_POLICY, fuel_before_rest=False)


def count(events, activity: str) -> int:
    return sum(e.activity.value == activity for e in events)


def drive_min(miles: float) -> int:
    """Minutes of driving for a leg of `miles` at 55 mph, like hos_helpers.leg."""
    return round(miles * 60 / 55)


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
        # 65 h used + 30 min pre-trip + 4.5 h driving = 70 h at 5 h. The trip is long
        # enough that driving those hours first beats restarting before it starts.
        events = plan(6 * H, 6 * H, cycle_used_min=65 * H)

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
        events = plan(1 * H, 11 * H, cycle_used_min=67 * H)

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

    def test_starting_at_the_pickup_at_seventy_restarts_then_inspects_and_loads(self):
        # Loading first (D14) would end at the same minute, but with an hour worked
        # past 70; on a tie the plan within the 70 hours wins (D19).
        events = plan(0, 2 * H, cycle_used_min=70 * H)

        assert timeline(events) == [
            ("restart", 0, 34 * H),
            ("pre_trip", 34 * H, 34 * H + 30),
            ("pickup", 34 * H + 30, 35 * H + 30),
            ("driving", 35 * H + 30, 37 * H + 30),
            ("dropoff", 37 * H + 30, 38 * H + 30),
        ]

    def test_no_short_drive_between_loading_and_a_restart(self):
        # D20: 68 h + 30 min pre-trip + 23 min drive + 1 h pickup leaves 7 minutes.
        # Driving them and then restarting looks like a mistake on the log; the driver
        # restarts at the shipper instead, and the drop-off is no later.
        events = plan(23, 22 * H, cycle_used_min=68 * H)
        without = plan(23, 22 * H, cycle_used_min=68 * H, policy=WITHOUT_D20)

        assert [e.activity.value for e in events][:4] == [
            "pre_trip", "driving", "pickup", "restart",
        ]  # fmt: skip
        assert [(e.activity.value, e.duration_min) for e in without][3] == ("driving", 7)
        assert events[-1].end_min == without[-1].end_min

    def test_a_short_first_shift_is_traded_for_a_restart_before_the_trip(self):
        # D19: at 67 h, inspecting, driving 1 h, loading and driving 30 min, then
        # restarting, needs a second inspection. Restarting first ends 30 min sooner.
        events = plan(1 * H, 1 * H, cycle_used_min=67 * H)

        assert [e.activity.value for e in events] == [
            "restart", "pre_trip", "driving", "pickup", "driving", "dropoff",
        ]  # fmt: skip
        assert events[-1].end_min == 38 * H + 30


class TestFuel:
    """D7: 30 minutes on duty at or before every 1,000 miles, starting with a full tank."""

    def test_trip_under_a_thousand_miles_has_no_fuel_stop(self):
        events = plan(9 * H, 9 * H)  # 990 miles

        assert count(events, "fuel") == 0

    def test_fuel_stop_comes_at_or_before_a_thousand_miles(self):
        # 1,100 miles. The first day ends at 605 miles, so the tank lasts 430 more
        # minutes (394.2 miles at 55 mph, rounded down to whole minutes).
        events = plan(10 * H, 10 * H, policy=NO_EARLY_FUEL)

        fuel = first(events, "fuel")
        assert count(events, "fuel") == 1
        assert (fuel.start_min, fuel.end_min) == (30 * H + 40, 31 * H + 10)
        assert 999 < fuel.start_mile <= 1000
        assert fuel.status is DutyStatus.ON_DUTY
        assert fuel.reason is StopReason.FUEL_INTERVAL

    def test_fuel_stop_counts_as_the_break(self):
        # D9: after the rest, 430 min of driving, fuel, then 230 min more. That is
        # 11 h of driving with no break, because the fuel stop reset the 8-hour count.
        events = plan(10 * H, 12 * H, policy=NO_EARLY_FUEL)

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
        events = plan(2 * H, 17 * H + 30, policy=replace(NO_EARLY_FUEL, pickup_min=4 * H))

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


class TestFuelBeforeRest:
    """D16: fuel just before a rest when the tank won't last the next shift."""

    def test_two_thousand_mile_trip_no_longer_fuels_near_the_end(self):
        # Without D16 the stops fall at ~1,000 and ~2,000 miles, the second only
        # 20 miles from the drop-off. With it, the second moves to just before the
        # last rest at 1,815 miles, where 185 miles of fuel would not reach the end.
        # The first stays on the road: at 999 miles it is also day 2's break (D9).
        events = plan(4 * H, 32 * H + 44)  # 220 + 1,800 miles
        without_d16 = plan(4 * H, 32 * H + 44, policy=NO_EARLY_FUEL)

        fuels = [e for e in events if e.activity is Activity.FUEL]
        assert [f.start_mile for f in fuels] == pytest.approx([999.17, 1815], abs=0.01)
        assert events[events.index(fuels[1]) + 1].activity is Activity.REST
        assert events[-1].end_mile - fuels[-1].start_mile > 200
        assert len(fuels) == count(without_d16, "fuel")
        assert events[-1].end_min == without_d16[-1].end_min

    def test_no_early_fuel_when_the_tank_covers_the_next_shift(self):
        # 1,158 miles, so one fuel stop either way. A 7 h pickup ends day 1 at 357.5
        # miles. The 642.5 miles left in the tank cover a full 605-mile shift, so the
        # driver rests without fuelling and fuels before the second rest instead.
        events = plan(1 * H, 20 * H + 3, policy=replace(DEFAULT_POLICY, pickup_min=7 * H))

        rests = [e for e in events if e.activity is Activity.REST]
        assert rests[0].start_mile == pytest.approx(357.5)
        assert events[events.index(rests[0]) - 1].activity is Activity.DRIVING
        assert events[events.index(rests[1]) - 1].activity is Activity.FUEL
        assert count(events, "fuel") == 1

    def test_no_early_fuel_when_it_would_add_a_stop(self):
        # 2,600 miles. Fuelling before every rest (605, 1,210, 1,815) would need 3
        # stops; the trip needs only 2. At the second rest, fuelling would add one,
        # so the driver waits and fuels on the road.
        events = plan(0, 47 * H + 16)  # 2,599.7 miles

        assert count(events, "fuel") == 2

    @pytest.mark.parametrize("to_pickup_h", [0, 3, 9, 15])
    @pytest.mark.parametrize("to_dropoff_h", [10, 20, 37, 48, 75])
    @pytest.mark.parametrize("cycle_used_h", [0, 40])
    def test_never_more_fuel_stops_or_a_longer_trip(self, to_pickup_h, to_dropoff_h, cycle_used_h):
        args = (to_pickup_h * H, to_dropoff_h * H, cycle_used_h * H)
        with_d16, without_d16 = plan(*args), plan(*args, policy=NO_EARLY_FUEL)

        assert count(with_d16, "fuel") <= count(without_d16, "fuel")
        assert with_d16[-1].end_min <= without_d16[-1].end_min


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


class TestRestartsOnLongTrips:
    """D19: more than a cycle of work ahead takes the fewest 34-hour restarts, not
    one at every 11-hour stop."""

    @pytest.mark.parametrize(
        ("to_pickup_miles", "to_dropoff_miles", "restarts_before_d19"),
        [(3300, 3300, 6), (2000, 2300, 2)],
    )
    def test_one_restart_from_an_empty_cycle(
        self, to_pickup_miles, to_dropoff_miles, restarts_before_d19
    ):
        # 6,600 mi is about 130 h on duty before the last drive ends, 4,300 mi about
        # 85 h: more than the 70 h the driver starts with, so at least one restart,
        # and within 70 h plus one restart's 70 h, so one is enough.
        events = plan(drive_min(to_pickup_miles), drive_min(to_dropoff_miles))

        assert count(events, "restart") == 1 < restarts_before_d19

    def test_the_cycle_is_driven_out_before_the_restart(self):
        # 6,600 mi: one restart covers the trip only if all 70 h of the first cycle
        # are used, so the driver keeps going until the cycle runs out mid-shift.
        events = plan(drive_min(3300), drive_min(3300))

        restart = first(events, "restart")
        on_duty_before = sum(
            e.duration_min
            for e in events
            if e.end_min <= restart.start_min
            and e.status in (DutyStatus.ON_DUTY, DutyStatus.DRIVING)
        )
        assert on_duty_before == DEFAULT_POLICY.cycle_limit_min
        assert restart.reason is StopReason.CYCLE_LIMIT

    def test_one_restart_when_the_estimate_is_close(self):
        # Found by the production smoke test: Miami -> Seattle -> Boston with 15 h used
        # (routed legs below). The rule alone restarted early with 7:30 of cycle left
        # and needed a second restart; driving the cycle out needs one, a day sooner.
        trip = TripInput(Leg(3302.7, 3603), Leg(3039.3, 3316), cycle_used_min=15 * H)
        events = plan_trip(trip)
        check_all(events, trip, DEFAULT_POLICY)

        assert count(events, "restart") == 1
