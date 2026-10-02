"""Schedules a trip under the hours-of-service rules.

The engine drives as far as every clock allows, inserts the stop that the
binding limit requires, and repeats until the trip is done. It works in
minutes since the trip starts and miles along the route (see models.py).
Limits come from HOSPolicy; nothing here hard-codes a number.
"""

from dataclasses import dataclass

from .models import Activity, DutyStatus, Event, Leg, TripInput
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
    off_streak_min: int = 0  # consecutive off-duty or sleeper minutes up to now


class _Scheduler:
    def __init__(self, trip: TripInput, policy: HOSPolicy) -> None:
        self.trip = trip
        self.policy = policy
        self.clocks = _Clocks()
        self.now = 0
        self.mile = 0.0
        self.events: list[Event] = []

    def run(self) -> list[Event]:
        self._drive_leg(self.trip.to_pickup)
        self._drive_leg(self.trip.to_dropoff)
        return self.events

    def _drive_leg(self, leg: Leg) -> None:
        start_mile = self.mile
        driven_min = 0
        while driven_min < leg.drive_min:
            allowed_min = self._driving_allowed_min()
            if allowed_min <= 0:
                self._take_required_stop()
                continue
            step_min = min(leg.drive_min - driven_min, allowed_min)
            driven_min += step_min
            # Position from the leg start, so rounding never drifts across steps.
            end_mile = start_mile + leg.distance_miles * driven_min / leg.drive_min
            self._record(Activity.DRIVING, step_min, end_mile)

    def _driving_allowed_min(self) -> int:
        """How long the driver may keep driving right now."""
        return self.policy.max_driving_min - self.clocks.driving_min  # guide p. 6

    def _take_required_stop(self) -> None:
        """Insert the stop that lets driving continue."""
        # 11 hours driven: 10 consecutive hours off before driving again (guide p. 6-7).
        self._record(Activity.REST, self.policy.daily_rest_min)

    def _record(self, activity: Activity, minutes: int, end_mile: float | None = None) -> None:
        status = self.policy.status_for(activity)
        end_mile = self.mile if end_mile is None else end_mile
        start_min, start_mile = self.now, self.mile

        # Continue the previous event when nothing changed, e.g. driving across legs.
        if self.events and self.events[-1].activity is activity:
            previous = self.events.pop()
            start_min, start_mile = previous.start_min, previous.start_mile

        self.events.append(
            Event(activity, status, start_min, self.now + minutes, start_mile, end_mile)
        )
        self._update_clocks(status, minutes)
        self.now += minutes
        self.mile = end_mile

    def _update_clocks(self, status: DutyStatus, minutes: int) -> None:
        clocks = self.clocks
        if status in OFF_STATUSES:
            clocks.off_streak_min += minutes
            if clocks.off_streak_min >= self.policy.daily_rest_min:
                clocks.driving_min = 0  # guide p. 6-7
            return

        clocks.off_streak_min = 0
        if status is DutyStatus.DRIVING:
            clocks.driving_min += minutes
