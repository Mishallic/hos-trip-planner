"""Builders and checks shared by the HOS engine tests."""

from planner.domain.hos_engine import plan_trip
from planner.domain.models import DutyStatus, Event, Leg, TripInput
from planner.domain.policy import DEFAULT_POLICY, HOUR, HOSPolicy

H = HOUR
OFF = {DutyStatus.OFF_DUTY, DutyStatus.SLEEPER_BERTH}


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
    assert_driving_limits_hold(events, policy)
    return events


def timeline(events: list[Event]) -> list[tuple[str, int, int]]:
    """(activity, start, end) per event: easy to read in an assertion diff."""
    return [(e.activity.value, e.start_min, e.end_min) for e in events]


def first(events: list[Event], activity: str) -> Event:
    return next(e for e in events if e.activity.value == activity)


def assert_well_formed(events: list[Event], trip: TripInput) -> None:
    """Invariants every timeline must hold, whatever the rules."""
    assert events, "a trip always has events"
    assert events[0].start_min == 0
    assert events[0].start_mile == 0
    for before, after in zip(events, events[1:], strict=False):
        assert after.start_min == before.end_min, "events must be back to back"
        assert after.start_mile == before.end_mile, "the truck cannot jump"
        assert (after.activity, after.reason) != (before.activity, before.reason), (
            "an unchanged activity must be one event"
        )
    assert abs(events[-1].end_mile - trip.total_miles) < 1e-6


def assert_driving_limits_hold(events: list[Event], policy: HOSPolicy) -> None:
    """Check the 11-hour limit and the 14-hour window without trusting the engine.

    A duty period starts with the first non-off minute after at least
    `daily_rest_min` consecutive minutes off duty or in the sleeper berth.
    """
    off_streak = policy.daily_rest_min  # the driver starts rested (D10)
    driving = 0
    window_start = 0
    for event in events:
        if event.status in OFF:
            off_streak += event.duration_min
            continue
        if off_streak >= policy.daily_rest_min:
            driving, window_start = 0, event.start_min
        off_streak = 0
        if event.status is DutyStatus.DRIVING:
            driving += event.duration_min
            assert driving <= policy.max_driving_min, f"over 11 hours driving at {event}"
            assert event.end_min <= window_start + policy.duty_window_min, (
                f"driving after the 14th hour at {event}"
            )
