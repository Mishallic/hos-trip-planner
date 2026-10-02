"""Property test: random trips never break a rule.

Hypothesis generates trips across the whole input range and every timeline goes
through the same independent checks as the hand-written tests (hos_helpers). The
run is derandomized, so CI sees the same examples every time.
"""

import time
from dataclasses import astuple

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from planner.domain.hos_engine import plan_trip
from planner.domain.models import Leg, TripInput
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


def _timed(func, *args) -> float:
    start = time.perf_counter()
    func(*args)
    return time.perf_counter() - start
