"""Plain-language reasons for each stop, and notes for log sheets that look over a limit.

Pure Python. Built from the timeline, the clocks and the sheets, never from engine
internals.
"""

from .clocks import Clocks
from .log_builder import DailyLog
from .models import Activity, DutyStatus, Event, StopReason
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
            loading = f"Pickup: loading, {hm(event.duration_min)} on duty."
            return loading + _past_limit(event, before)
        case Activity.DROPOFF, _:
            return (
                f"Drop-off: unloading, {hm(event.duration_min)} on duty. Trip complete."
                + _past_limit(event, before)
            )
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
            if index == 0:
                if before.cycle_left_min == 0:
                    return "70-hour cycle used up, so the trip starts with a 34-hour restart."
                return (
                    f"Only {hm(before.cycle_left_min)} left in the 70-hour cycle, too little "
                    "for this trip, so it starts with a 34-hour restart."
                )
            if before.cycle_left_min == 0:
                return "70-hour cycle used up. 34 hours off duty restart it."
            short_min = max(1, policy.min_drive_min)
            if min(before.driving_left_min, before.window_left_min) < short_min:  # D19
                return (
                    f"Only {hm(before.cycle_left_min)} left in the 70-hour cycle, and the rest "
                    f"of the trip needs {hm(_work_until_last_drive(events, index))} on duty, "
                    "so a restart is needed anyway: 34 hours off now, in place of a 10-hour rest."
                )
            return (  # D20
                f"Only {hm(before.cycle_left_min)} left in the 70-hour cycle, too little to be "
                "worth driving, so the 34-hour restart starts here."
            )
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
                    "tank would not last the next shift." + _past_limit(event, before)
                )
            return (
                f"Fuel at or before every {policy.fuel_interval_miles:,.0f} miles "
                f"({miles:,.0f} miles since the last fill)."
            )
    return ""


def sheet_notes(log: DailyLog, policy: HOSPolicy = DEFAULT_POLICY) -> list[str]:
    """Why a sheet that seems to break a limit does not.

    The 11- and 14-hour limits run per duty period, not per calendar day, and the
    70-hour limit stops driving, not work. A reader checking one sheet against them
    would see a violation where there is none.
    """
    notes = []
    driving_min = log.totals_min[DutyStatus.DRIVING]
    on_duty_min = driving_min + log.totals_min[DutyStatus.ON_DUTY]
    if driving_min > policy.max_driving_min:
        notes.append(
            f"{hm(driving_min)} of driving on one sheet is within the rules: the 11-hour "
            "limit counts from the last 10-hour rest, not from midnight, and this day "
            "holds parts of two duty periods."
        )
    elif on_duty_min > policy.duty_window_min:
        notes.append(
            f"{hm(on_duty_min)} on duty on one sheet is within the rules: the 14-hour "
            "window limits driving, not other work, and starts again after each "
            "10-hour rest."
        )
    if log.recap.cycle_used_min > policy.cycle_limit_min:
        notes.append(
            f"{hm(log.recap.cycle_used_min)} on duty in the cycle is within the rules: "
            "past 70 hours the driver may still work, but not drive, until a 34-hour "
            "restart."
        )
    return notes


def _past_limit(event: Event, before: Clocks) -> str:
    """A sentence for on-duty work that runs past the 70 hours or the 14-hour window."""
    if before.cycle_left_min < event.duration_min:
        return " Allowed past 70 hours: the limit stops driving, not work."
    if before.window_left_min < event.duration_min:
        return " Allowed after the 14-hour window: it stops driving, not work."
    return ""


def _work_until_last_drive(events: list[Event], index: int) -> int:
    """On-duty minutes after events[index] up to the end of the last drive."""
    last_drive = max(
        (i for i, e in enumerate(events) if e.status is DutyStatus.DRIVING), default=index
    )
    return sum(
        e.duration_min
        for e in events[index + 1 : last_drive + 1]
        if e.status in (DutyStatus.DRIVING, DutyStatus.ON_DUTY)
    )


def _miles_since_fuel(events: list[Event], index: int) -> float:
    start_mile = 0.0
    for event in events[:index]:
        if event.activity is Activity.FUEL:
            start_mile = event.end_mile
    return events[index].start_mile - start_mile
