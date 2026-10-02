"""Builders and checks shared by the HOS engine tests."""

from planner.domain.hos_engine import plan_trip
from planner.domain.models import Activity, DutyStatus, Event, Leg, TripInput
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
    check_all(events, trip, policy)
    return events


def check_all(events: list[Event], trip: TripInput, policy: HOSPolicy) -> None:
    """Every independent check: the timeline's shape and each rule, from events alone."""
    assert_well_formed(events, trip)
    assert_driving_limits_hold(events, policy)  # 11-hour limit and 14-hour window
    assert_break_rule_holds(events, policy)
    assert_cycle_rule_holds(events, policy, trip.cycle_used_min)
    assert_pre_trip_rule_holds(events, policy)
    assert_fuel_rule_holds(events, policy)
    assert_stops_have_their_lengths(events, policy)


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


def assert_break_rule_holds(events: list[Event], policy: HOSPolicy) -> None:
    """Check the 8-hour rule without trusting the engine (guide p. 10, D9).

    Driving adds up across stops until the driver spends `break_min` consecutive
    minutes not driving, in any status.
    """
    driving = 0
    not_driving = 0
    for event in events:
        if event.status is DutyStatus.DRIVING:
            driving += event.duration_min
            not_driving = 0
            assert driving <= policy.break_after_driving_min, (
                f"over 8 hours of driving without a break at {event}"
            )
        else:
            not_driving += event.duration_min
            if not_driving >= policy.break_min:
                driving = 0


def assert_cycle_rule_holds(events: list[Event], policy: HOSPolicy, cycle_used_min: int) -> None:
    """Check the 70-hour rule without trusting the engine (guide p. 10-11, D3, D14).

    Every on-duty and driving minute counts, starting from the hours already used.
    On-duty work past 70 is allowed; driving is not. `restart_min` consecutive
    minutes off duty or in the sleeper berth reset the count.
    """
    cycle = cycle_used_min
    off_streak = 0
    for event in events:
        if event.status in OFF:
            off_streak += event.duration_min
            if off_streak >= policy.restart_min:
                cycle = 0
            continue
        off_streak = 0
        cycle += event.duration_min
        if event.status is DutyStatus.DRIVING:
            assert cycle <= policy.cycle_limit_min, f"driving past 70 hours on duty at {event}"


def duty_periods(events: list[Event], policy: HOSPolicy) -> list[list[Event]]:
    """Split the timeline at every off-duty stretch of at least `daily_rest_min`.

    Off-duty events are dropped, so each period lists only its on-duty work.
    """
    periods: list[list[Event]] = [[]]
    off_streak = 0
    for event in events:
        if event.status in OFF:
            off_streak += event.duration_min
            continue
        if off_streak >= policy.daily_rest_min and periods[-1]:
            periods.append([])
        off_streak = 0
        periods[-1].append(event)
    return periods


def assert_pre_trip_rule_holds(events: list[Event], policy: HOSPolicy) -> None:
    """D4: one pre-trip per duty period that drives, before its first drive, and no
    pre-trip in a period that does not drive."""
    if not policy.pre_trip_min:
        return
    for period in duty_periods(events, policy):
        kinds = [e.activity for e in period]
        drives = Activity.DRIVING in kinds
        assert kinds.count(Activity.PRE_TRIP) == (1 if drives else 0), f"pre-trips in {kinds}"
        if drives:
            assert kinds.index(Activity.PRE_TRIP) < kinds.index(Activity.DRIVING), (
                f"pre-trip after the first drive in {kinds}"
            )


def assert_fuel_rule_holds(events: list[Event], policy: HOSPolicy) -> None:
    """D7: never more than `fuel_interval_miles` driven between fuel stops."""
    since_fuel = 0.0
    for event in events:
        if event.activity is Activity.FUEL:
            since_fuel = 0.0
        since_fuel += event.end_mile - event.start_mile
        assert since_fuel <= policy.fuel_interval_miles + 1e-6, f"tank ran dry at {event}"


def assert_stops_have_their_lengths(events: list[Event], policy: HOSPolicy) -> None:
    """Every stop lasts exactly its policy length.

    The rule checks above pass for a plan that stops longer than needed. This one
    catches a stop that was too short to count and had to be repeated.
    """
    lengths = {
        Activity.PRE_TRIP: policy.pre_trip_min,
        Activity.PICKUP: policy.pickup_min,
        Activity.DROPOFF: policy.dropoff_min,
        Activity.FUEL: policy.fuel_stop_min,
        Activity.BREAK: policy.break_min,
        Activity.REST: policy.daily_rest_min,
        Activity.RESTART: policy.restart_min,
    }
    for event in events:
        if event.activity is not Activity.DRIVING:
            assert event.duration_min == lengths[event.activity], f"wrong length: {event}"
