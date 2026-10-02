"""Plain-language reasons for each stop, shown next to it in the stop list.

Pure Python. Built from the timeline and the clocks, never from engine internals.
"""

from .clocks import Clocks
from .models import Activity, Event, StopReason
from .policy import DEFAULT_POLICY, HOSPolicy


def hm(minutes: float) -> str:
    """Minutes as h:mm, e.g. 660 -> "11:00", 75 -> "1:15"."""
    whole = round(minutes)
    return f"{whole // 60}:{whole % 60:02d}"


def explain_stop(
    events: list[Event],
    index: int,
    clocks: list[Clocks],
    policy: HOSPolicy = DEFAULT_POLICY,
) -> str:
    """Why the driver stops at events[index], in one sentence."""
    event = events[index]
    before = clocks[index]
    driven_today = policy.max_driving_min - before.driving_left_min
    driven_since_break = policy.break_after_driving_min - before.break_left_min
    following = events[index + 1] if index + 1 < len(events) else None

    match event.activity, event.reason:
        case Activity.PRE_TRIP, _:
            return "Pre-trip inspection at the start of the duty period."
        case Activity.PICKUP, _:
            return f"Pickup: loading, {hm(event.duration_min)} on duty."
        case Activity.DROPOFF, _:
            return f"Drop-off: unloading, {hm(event.duration_min)} on duty. Trip complete."
        case Activity.REST, StopReason.DRIVING_LIMIT:
            return (
                f"11-hour driving limit reached after {hm(driven_today)} of driving. "
                f"{hm(event.duration_min)} in the sleeper berth resets the 11- and 14-hour clocks."
            )
        case Activity.REST, StopReason.DUTY_WINDOW:
            return (
                f"14-hour window closed after {hm(driven_today)} of driving. "
                f"{hm(event.duration_min)} in the sleeper berth starts a new window."
            )
        case Activity.REST, _:
            return f"{hm(event.duration_min)} rest."
        case Activity.RESTART, _:
            if before.cycle_left_min > 0:
                return (
                    f"Only {hm(before.cycle_left_min)} left in the 70-hour cycle, not enough "
                    "for the rest of the trip, so a 34-hour restart instead of a 10-hour rest."
                )
            return "70-hour cycle used up. 34 hours off duty restart it."
        case Activity.BREAK, _:
            return f"30-minute break required after {hm(driven_since_break)} of driving."
        case Activity.FUEL, StopReason.BREAK_REQUIRED:
            return (
                f"Fuel stop that also counts as the 30-minute break, due after "
                f"{hm(driven_since_break)} of driving."
            )
        case Activity.FUEL, _:
            miles = _miles_since_fuel(events, index)
            if following and following.activity in (Activity.REST, Activity.RESTART):
                return (
                    f"Fuel before the rest: {miles:,.0f} miles since the last fill, and the "
                    "tank would not last the next shift."
                )
            return (
                f"Fuel at or before every {policy.fuel_interval_miles:,.0f} miles "
                f"({miles:,.0f} miles since the last fill)."
            )
    return ""


def _miles_since_fuel(events: list[Event], index: int) -> float:
    start_mile = 0.0
    for event in events[:index]:
        if event.activity is Activity.FUEL:
            start_mile = event.end_mile
    return events[index].start_mile - start_mile
