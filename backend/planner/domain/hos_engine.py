"""Schedules a trip under the hours-of-service rules.

The engine drives as far as every clock allows, inserts the stop that the
binding limit requires, and repeats until the trip is done. It works in
minutes since the trip starts and miles along the route (see models.py).
Limits come from HOSPolicy; nothing here hard-codes a number.
"""

from dataclasses import dataclass

from .models import Activity, DutyStatus, Event, Leg, StopReason, TripInput
from .policy import DEFAULT_POLICY, HOSPolicy

OFF_STATUSES = frozenset({DutyStatus.OFF_DUTY, DutyStatus.SLEEPER_BERTH})


def plan_trip(trip: TripInput, policy: HOSPolicy = DEFAULT_POLICY) -> list[Event]:
    """Return the trip's timeline: consecutive events from the start to the drop-off."""
    if trip.cycle_used_min > policy.cycle_limit_min:
        raise ValueError(f"cycle hours used cannot exceed {policy.cycle_limit_min // 60} hours")
    return _Scheduler(trip, policy).run()


@dataclass
class _Clocks:
    """What the rules need to know about the driver's recent past.

    The driver starts rested (D10), so every clock starts at zero.
    """

    driving_min: int = 0  # driving since the last 10-hour rest (11-hour limit)
    window_start_min: int | None = None  # first on-duty minute since that rest (14-hour window)
    off_streak_min: int = 0  # consecutive off-duty or sleeper minutes up to now
    driving_since_break_min: int = 0  # driving since the last qualifying break (8-hour rule)
    not_driving_streak_min: int = 0  # consecutive non-driving minutes of any status up to now


class _Scheduler:
    def __init__(self, trip: TripInput, policy: HOSPolicy) -> None:
        self.trip = trip
        self.policy = policy
        self.clocks = _Clocks()
        self.now = 0
        self.mile = 0.0
        self.events: list[Event] = []

    def run(self) -> list[Event]:
        # On-duty work is allowed even when the clocks forbid driving (D14),
        # so pickup and drop-off happen on arrival and any rest comes after.
        self._drive_leg(self.trip.to_pickup)
        self._record(Activity.PICKUP, self.policy.pickup_min)  # D13
        self._drive_leg(self.trip.to_dropoff)
        self._record(Activity.DROPOFF, self.policy.dropoff_min)  # D13
        return self.events

    def _drive_leg(self, leg: Leg) -> None:
        start_mile = self.mile
        driven_min = 0
        while driven_min < leg.drive_min:
            allowed_min, limit = self._driving_allowance()
            if allowed_min <= 0:
                self._take_required_stop(limit)
                continue
            step_min = min(leg.drive_min - driven_min, allowed_min)
            driven_min += step_min
            # Position from the leg start, so rounding never drifts across steps.
            end_mile = start_mile + leg.distance_miles * driven_min / leg.drive_min
            self._record(Activity.DRIVING, step_min, end_mile)

    def _driving_allowance(self) -> tuple[int, StopReason]:
        """Minutes the driver may keep driving right now, and the limit that will stop them.

        When two limits run out at the same minute, the one listed first is reported.
        """
        clocks, policy = self.clocks, self.policy
        window_used_min = (
            0 if clocks.window_start_min is None else self.now - clocks.window_start_min
        )
        limits = [
            (policy.max_driving_min - clocks.driving_min, StopReason.DRIVING_LIMIT),  # guide p. 6
            (policy.duty_window_min - window_used_min, StopReason.DUTY_WINDOW),  # guide p. 6
            # Listed after the rest limits: on a tie the rest is taken, and it covers the break.
            (
                policy.break_after_driving_min - clocks.driving_since_break_min,
                StopReason.BREAK_REQUIRED,
            ),  # guide p. 10
        ]
        return min(limits, key=lambda limit: limit[0])

    def _take_required_stop(self, reason: StopReason) -> None:
        """Insert the stop that lets driving continue."""
        match reason:
            case StopReason.DRIVING_LIMIT | StopReason.DUTY_WINDOW:
                # 10 consecutive hours off before driving again (guide p. 6-7).
                self._record(Activity.REST, self.policy.daily_rest_min, reason=reason)
            case StopReason.BREAK_REQUIRED:
                # 8 hours of driving: 30 minutes off the wheel, logged off duty (guide p. 10, D5).
                self._record(Activity.BREAK, self.policy.break_min, reason=reason)

    def _record(
        self,
        activity: Activity,
        minutes: int,
        end_mile: float | None = None,
        reason: StopReason | None = None,
    ) -> None:
        status = self.policy.status_for(activity)
        end_mile = self.mile if end_mile is None else end_mile
        start_min, start_mile = self.now, self.mile

        # Continue the previous event when nothing changed, e.g. driving split by a limit check.
        previous = self.events[-1] if self.events else None
        if previous and previous.activity is activity and previous.reason is reason:
            self.events.pop()
            start_min, start_mile = previous.start_min, previous.start_mile

        self.events.append(
            Event(activity, status, start_min, self.now + minutes, start_mile, end_mile, reason)
        )
        self._update_clocks(status, minutes)
        self.now += minutes
        self.mile = end_mile

    def _update_clocks(self, status: DutyStatus, minutes: int) -> None:
        clocks = self.clocks

        # 8-hour rule: driving counts cumulatively until 30 consecutive minutes of
        # any non-driving status, on duty included (guide p. 10, D9).
        if status is DutyStatus.DRIVING:
            clocks.driving_since_break_min += minutes
            clocks.not_driving_streak_min = 0
        else:
            clocks.not_driving_streak_min += minutes
            if clocks.not_driving_streak_min >= self.policy.break_min:
                clocks.driving_since_break_min = 0

        if status in OFF_STATUSES:
            clocks.off_streak_min += minutes
            if clocks.off_streak_min >= self.policy.daily_rest_min:
                # A full rest resets the 11-hour limit and the 14-hour window (guide p. 6-7).
                clocks.driving_min = 0
                clocks.window_start_min = None
            return

        clocks.off_streak_min = 0
        if clocks.window_start_min is None:
            # The window starts with any work, not with the first drive (guide p. 6).
            clocks.window_start_min = self.now
        if status is DutyStatus.DRIVING:
            clocks.driving_min += minutes
