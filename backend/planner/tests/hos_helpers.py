"""Builders and checks shared by the HOS engine tests."""

from planner.domain.hos_engine import plan_trip
from planner.domain.models import Event, Leg, TripInput
from planner.domain.policy import DEFAULT_POLICY, HOUR, HOSPolicy

H = HOUR


def leg(drive_min: int, mph: float = 55.0) -> Leg:
    """A leg that takes `drive_min` minutes at a steady `mph`."""
    return Leg(distance_miles=drive_min * mph / 60, drive_min=drive_min)


def plan(
    to_pickup_min: int,
    to_dropoff_min: int,
    cycle_used_min: int = 0,
    policy: HOSPolicy = DEFAULT_POLICY,
) -> list[Event]:
    trip = TripInput(leg(to_pickup_min), leg(to_dropoff_min), cycle_used_min)
    events = plan_trip(trip, policy)
    assert_well_formed(events, trip)
    return events


def timeline(events: list[Event]) -> list[tuple[str, int, int]]:
    """(activity, start, end) per event: easy to read in an assertion diff."""
    return [(e.activity.value, e.start_min, e.end_min) for e in events]


def assert_well_formed(events: list[Event], trip: TripInput) -> None:
    """Invariants every timeline must hold, whatever the rules."""
    assert events, "a trip always has events"
    assert events[0].start_min == 0
    assert events[0].start_mile == 0
    for before, after in zip(events, events[1:], strict=False):
        assert after.start_min == before.end_min, "events must be back to back"
        assert after.start_mile == before.end_mile, "the truck cannot jump"
        assert after.activity is not before.activity, "same activity must be one event"
    assert abs(events[-1].end_mile - trip.total_miles) < 1e-6
