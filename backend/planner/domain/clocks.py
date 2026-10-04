"""The driver's clocks: how much of each limit is left.

DutyClocks is the one place that says how each minute of each duty status moves the
clocks. The engine schedules with it, the stop list shows it at every stop, and the
daily recap counts the cycle with it. The tests check every plan against a separate,
independent statement of the rules (tests/hos_helpers.py).
"""

from dataclasses import dataclass

from .models import OFF_DUTY_STATUSES, DutyStatus, Event
from .policy import DEFAULT_POLICY, HOSPolicy


@dataclass(frozen=True, slots=True)
class Clocks:
    driving_left_min: int  # of the 11-hour driving limit
    window_left_min: int  # of the 14-hour window; full until the first work of the period
    break_left_min: int  # of driving before a 30-minute break is due
    cycle_left_min: int  # of the 70-hour cycle


@dataclass(slots=True)
class DutyClocks:
    """What the rules need to know about the driver's recent past.

    The driver starts rested (D10), so every clock starts at zero except the cycle,
    which starts at the hours already used (D3).
    """

    cycle_used_min: int = 0  # on duty in the current 70-hour cycle
    driving_min: int = 0  # driving since the last 10-hour rest (11-hour limit)
    window_start_min: int | None = None  # first on-duty minute since that rest (14-hour window)
    driving_since_break_min: int = 0  # driving since the last qualifying break (8-hour rule)
    not_driving_streak_min: int = 0  # consecutive non-driving minutes of any status up to now
    off_streak_min: int = 0  # consecutive off-duty or sleeper minutes up to now

    def advance(self, status: DutyStatus, start_min: int, minutes: int, policy: HOSPolicy) -> None:
        """Move the clocks over `minutes` of `status`, starting at `start_min`."""
        # 8-hour rule: driving counts cumulatively until 30 consecutive minutes of
        # any non-driving status, on duty included (guide p. 10, D9).
        if status is DutyStatus.DRIVING:
            self.driving_since_break_min += minutes
            self.not_driving_streak_min = 0
        else:
            self.not_driving_streak_min += minutes
            if self.not_driving_streak_min >= policy.break_min:
                self.driving_since_break_min = 0

        if status in OFF_DUTY_STATUSES:
            self.off_streak_min += minutes
            if self.rested(policy):
                # A full rest resets the 11-hour limit and the 14-hour window (guide p. 6-7).
                self.driving_min = 0
                self.window_start_min = None
            if self.off_streak_min >= policy.restart_min:
                self.cycle_used_min = 0  # the 34-hour restart (guide p. 11)
            return

        # All on-duty time counts toward the cycle, not just driving (guide p. 10).
        self.cycle_used_min += minutes
        self.off_streak_min = 0
        if self.window_start_min is None:
            # The window starts with any work, not with the first drive (guide p. 6).
            self.window_start_min = start_min
        if status is DutyStatus.DRIVING:
            self.driving_min += minutes

    def rested(self, policy: HOSPolicy) -> bool:
        """True after 10 consecutive hours off: a new duty period starts with the next work."""
        return self.off_streak_min >= policy.daily_rest_min

    def left(self, now_min: int, policy: HOSPolicy) -> Clocks:
        """What is left of each limit at `now_min`."""
        window_used_min = 0 if self.window_start_min is None else now_min - self.window_start_min
        return Clocks(
            driving_left_min=max(0, policy.max_driving_min - self.driving_min),
            window_left_min=max(0, policy.duty_window_min - window_used_min),
            break_left_min=max(0, policy.break_after_driving_min - self.driving_since_break_min),
            cycle_left_min=max(0, policy.cycle_limit_min - self.cycle_used_min),
        )


def clocks_before_each_event(
    events: list[Event], cycle_used_min: int, policy: HOSPolicy = DEFAULT_POLICY
) -> list[Clocks]:
    """One Clocks per event: what was left just before it began. The UI shows these as
    the 11 / 14 / 8 / 70 meters."""
    clocks = DutyClocks(cycle_used_min=cycle_used_min)
    result = []
    for event in events:
        result.append(clocks.left(event.start_min, policy))
        clocks.advance(event.status, event.start_min, event.duration_min, policy)
    return result
