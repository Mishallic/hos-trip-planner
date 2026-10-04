"""Property test: random trips never break a rule.

Hypothesis generates trips across the whole input range and every timeline goes
through the same independent checks as the hand-written tests (hos_helpers). The
run is derandomized, so CI sees the same examples every time. The restart rule (D19)
is also compared with the rule it replaced: never more restarts, never a later end.
"""

import itertools
import time
from dataclasses import astuple, replace

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from planner.domain.hos_engine import _Scheduler, plan_trip
from planner.domain.models import Activity, Event, Leg, TripInput
from planner.domain.policy import DEFAULT_POLICY, HOUR

from .hos_helpers import check_all

PROPERTY_SETTINGS = settings(
    max_examples=400,
    derandomize=True,  # the same examples on every run, here and in CI
    database=None,
    deadline=None,  # timing is checked separately; CI machines vary
    suppress_health_check=[HealthCheck.too_slow],
)


def routed_leg(miles: float, router_mph: float) -> Leg:
    """A leg as the planning service builds it: router time, capped at 55 mph (D8)."""
    if miles == 0:
        return Leg(distance_miles=0, drive_min=0)
    router_min = miles / router_mph * 60
    return Leg(distance_miles=miles, drive_min=DEFAULT_POLICY.drive_minutes(miles, router_min))


miles = st.floats(min_value=1, max_value=3000, allow_nan=False, allow_infinity=False)
router_mph = st.floats(min_value=30, max_value=70, allow_nan=False, allow_infinity=False)

trips = st.builds(
    TripInput,
    to_pickup=st.builds(routed_leg, st.one_of(st.just(0.0), miles), router_mph),
    to_dropoff=st.builds(routed_leg, miles, router_mph),
    cycle_used_min=st.integers(min_value=0, max_value=70 * 4).map(lambda quarters: quarters * 15),
)


@PROPERTY_SETTINGS
@given(trip=trips)
def test_random_trips_never_break_a_rule(trip):
    events = plan_trip(trip)

    check_all(events, trip, DEFAULT_POLICY)
    assert abs(events[-1].end_mile - trip.total_miles) < 1e-6
    assert all(e.duration_min > 0 for e in events)
    # Terminates with a sensible number of events: a handful per hour of driving.
    drive_h = (trip.to_pickup.drive_min + trip.to_dropoff.drive_min) / HOUR
    assert len(events) <= 10 + 2 * drive_h


@PROPERTY_SETTINGS
@given(trip=trips)
def test_planning_is_deterministic(trip):
    first_run = [astuple(e) for e in plan_trip(trip)]
    second_run = [astuple(e) for e in plan_trip(trip)]

    assert first_run == second_run


def test_five_thousand_mile_trip_plans_quickly():
    trip = TripInput(
        to_pickup=routed_leg(400, router_mph=60),
        to_dropoff=routed_leg(4600, router_mph=60),
        cycle_used_min=40 * HOUR,
    )
    plan_trip(trip)  # warm up imports and caches

    best_s = min(_timed(plan_trip, trip) for _ in range(3))

    assert best_s < 0.1, f"took {best_s * 1000:.1f} ms"


class PreviousRestartRule(_Scheduler):
    """The engine before D19, kept only as the yardstick for the tests below.

    At every 10-hour rest where the cycle left could not cover the work still to come
    (counting one pre-trip), it restarted instead, even with several cycles of work
    ahead, so long trips restarted after every shift.
    """

    def _restart_instead_of_rest(self) -> bool:
        if self.drive_left_min == 0:
            return False
        policy = self.policy
        needed_min = self.drive_left_min + policy.pre_trip_min
        needed_min += self._fuel_stops_left() * policy.fuel_stop_min
        if not self.pickup_done and self.trip.to_dropoff.drive_min > 0:
            needed_min += policy.pickup_min
        return policy.cycle_limit_min - self.clocks.cycle_used_min < needed_min


def restarts_and_end(events: list[Event]) -> tuple[int, int]:
    return sum(e.activity is Activity.RESTART for e in events), events[-1].end_min


# D20 may end a plan up to 15 minutes later to avoid a short drive, so D19 is
# compared with it turned off, and D20 has its own test below.
WITHOUT_D20 = replace(DEFAULT_POLICY, min_drive_min=0)


def no_worse_than_before_d19(trip: TripInput) -> str | None:
    """None, or why the plan takes more restarts or ends later than before D19."""
    now = plan_trip(trip, WITHOUT_D20)
    check_all(now, trip, DEFAULT_POLICY)
    restarts, end = restarts_and_end(now)
    restarts_before, end_before = restarts_and_end(PreviousRestartRule(trip, DEFAULT_POLICY).run())
    if restarts <= restarts_before and end <= end_before:
        return None
    before = f"before D19 {restarts_before} restarts, ending at {end_before} min"
    return f"{trip}: {restarts} restarts, ending at {end} min; {before}"


long_trips = st.builds(
    TripInput,
    to_pickup=st.builds(routed_leg, st.one_of(st.just(0.0), st.floats(1, 4000)), router_mph),
    to_dropoff=st.builds(routed_leg, st.floats(1, 4500), router_mph),
    cycle_used_min=st.integers(min_value=0, max_value=70 * 4).map(lambda quarters: quarters * 15),
)


@PROPERTY_SETTINGS
@given(trip=st.one_of(trips, long_trips))
def test_d19_never_adds_a_restart_or_time_to_a_trip(trip):
    assert no_worse_than_before_d19(trip) is None


def test_d19_on_a_grid_of_trips():
    # Short to coast-to-coast-and-back legs, at three speeds, from an empty cycle to a full one.
    grid = itertools.product(
        [0, 300, 1500, 3300],  # miles to the pickup
        [400, 1800, 3000, 4500],  # miles to the drop-off
        [0, 30 * HOUR, 52 * HOUR, 58 * HOUR, 63 * HOUR, 69 * HOUR + 30, 70 * HOUR],  # cycle used
        [50, 55, 62],  # mph
    )
    worse = [
        problem
        for pickup, dropoff, used, mph in grid
        if (
            problem := no_worse_than_before_d19(
                TripInput(steady_leg(pickup, mph), steady_leg(dropoff, mph), used)
            )
        )
    ]

    assert worse == []


@PROPERTY_SETTINGS
@given(trip=st.one_of(trips, long_trips))
def test_d20_costs_no_restart_and_at_most_a_quarter_hour(trip):
    plan = plan_trip(trip)
    without = plan_trip(trip, WITHOUT_D20)

    check_all(plan, trip, DEFAULT_POLICY)
    restarts, end = restarts_and_end(plan)
    restarts_without, end_without = restarts_and_end(without)
    assert restarts <= restarts_without
    assert end <= end_without + DEFAULT_POLICY.min_drive_min
    if end > end_without:
        assert not short_drive_before_a_stop(plan)


def short_drive_before_a_stop(events: list[Event]) -> bool:
    stops = {Activity.REST, Activity.RESTART, Activity.BREAK}
    return any(
        event.activity is Activity.DRIVING
        and event.duration_min < DEFAULT_POLICY.min_drive_min
        and following.activity in stops
        for event, following in itertools.pairwise(events)
    )


def steady_leg(miles: float, mph: float) -> Leg:
    return Leg(distance_miles=miles, drive_min=round(miles / mph * 60))


def _timed(func, *args) -> float:
    start = time.perf_counter()
    func(*args)
    return time.perf_counter() - start
