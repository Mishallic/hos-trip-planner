"""The driver's clocks: how much of each limit is left at the start of every event.

Pure Python, and worked out from the timeline alone, independently of the engine's
own bookkeeping. The UI shows these as the 11 / 14 / 8 / 70 meters.
"""

from dataclasses import dataclass

from .models import DutyStatus, Event
from .policy import DEFAULT_POLICY, HOSPolicy

OFF_STATUSES = frozenset({DutyStatus.OFF_DUTY, DutyStatus.SLEEPER_BERTH})


@dataclass(frozen=True, slots=True)
class Clocks:
    driving_left_min: int  # of the 11-hour driving limit
    window_left_min: int  # of the 14-hour window; full until the first work of the period
    break_left_min: int  # of driving before a 30-minute break is due
    cycle_left_min: int  # of the 70-hour cycle


def clocks_before_each_event(
    events: list[Event], cycle_used_min: int, policy: HOSPolicy = DEFAULT_POLICY
) -> list[Clocks]:
    """One Clocks per event: what was left just before it began."""
    driving = 0  # since the last 10-hour rest
    window_start: int | None = None
    since_break = 0
    not_driving = 0
    off_streak = 0
    cycle = cycle_used_min
    result = []

    for event in events:
        window_used = 0 if window_start is None else event.start_min - window_start
        result.append(
            Clocks(
                driving_left_min=max(0, policy.max_driving_min - driving),
                window_left_min=max(0, policy.duty_window_min - window_used),
                break_left_min=max(0, policy.break_after_driving_min - since_break),
                cycle_left_min=max(0, policy.cycle_limit_min - cycle),
            )
        )

        minutes = event.duration_min
        if event.status is DutyStatus.DRIVING:
            since_break += minutes
            not_driving = 0
        else:
            not_driving += minutes
            if not_driving >= policy.break_min:
                since_break = 0

        if event.status in OFF_STATUSES:
            off_streak += minutes
            if off_streak >= policy.daily_rest_min:
                driving, window_start = 0, None
            if off_streak >= policy.restart_min:
                cycle = 0
            continue

        off_streak = 0
        cycle += minutes
        if window_start is None:
            window_start = event.start_min
        if event.status is DutyStatus.DRIVING:
            driving += minutes

    return result
