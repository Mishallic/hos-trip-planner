"""Schedules a trip under the hours-of-service rules.

The engine drives as far as every clock allows, inserts the stop that the
binding limit requires, and repeats until the trip is done. It works in
minutes since the trip starts and miles along the route (see models.py).
Limits come from HOSPolicy; nothing here hard-codes a number.
"""

import math
from dataclasses import dataclass

from .models import Activity, DutyStatus, Event, Leg, StopReason, TripInput
from .policy import DEFAULT_POLICY, HOSPolicy

OFF_STATUSES = frozenset({DutyStatus.OFF_DUTY, DutyStatus.SLEEPER_BERTH})
EPSILON = 1e-9  # float slack when converting miles to whole minutes
# A legitimate plan needs at most 3 stops in a row before driving again (say rest,
# pre-trip, fuel). More than this means no stop is freeing the clocks: fail loudly
# instead of looping forever.
MAX_STOPS_WITHOUT_DRIVING = 10


def plan_trip(trip: TripInput, policy: HOSPolicy = DEFAULT_POLICY) -> list[Event]:
    """Return the trip's timeline: consecutive events from the start to the drop-off."""
    if trip.cycle_used_min > policy.cycle_limit_min:
        raise ValueError(f"cycle hours used cannot exceed {policy.cycle_limit_min // 60} hours")
    return _Scheduler(trip, policy).run()


@dataclass
class _Clocks:
    """What the rules need to know about the driver's recent past.

    The driver starts rested (D10) with a full tank (D7), so every clock starts
    at zero except the cycle, which starts at the hours already used (D3).
    """

    driving_min: int = 0  # driving since the last 10-hour rest (11-hour limit)
    window_start_min: int | None = None  # first on-duty minute since that rest (14-hour window)
    off_streak_min: int = 0  # consecutive off-duty or sleeper minutes up to now
    driving_since_break_min: int = 0  # driving since the last qualifying break (8-hour rule)
    not_driving_streak_min: int = 0  # consecutive non-driving minutes of any status up to now
    cycle_used_min: int = 0  # on duty in the current 70-hour cycle, seeded from the input (D3)
    pre_trip_done: bool = False  # inspected in the current duty period (D4)
    miles_since_fuel: float = 0.0  # driven since the last fuel stop (D7)


class _Scheduler:
    def __init__(self, trip: TripInput, policy: HOSPolicy) -> None:
        self.trip = trip
        self.policy = policy
        self.clocks = _Clocks(cycle_used_min=trip.cycle_used_min)
        self.now = 0
        self.mile = 0.0
        self.events: list[Event] = []
        self.drive_left_min = trip.to_pickup.drive_min + trip.to_dropoff.drive_min
        self.pickup_done = False
        self.miles_per_min = 0.0  # speed on the leg being driven

    def run(self) -> list[Event]:
        # On-duty work is allowed even when the clocks forbid driving (D14),
        # so pickup and drop-off happen on arrival and any rest comes after.
        self._drive_leg(self.trip.to_pickup)
        self._pre_trip_before_pickup()
        self._record(Activity.PICKUP, self.policy.pickup_min)  # D13
        self.pickup_done = True
        self._drive_leg(self.trip.to_dropoff)
        self._record(Activity.DROPOFF, self.policy.dropoff_min)  # D13
        return self.events

    def _pre_trip_before_pickup(self) -> None:
        """D4: when the duty period starts at the pickup, inspect first, then load.

        Skipped when no driving would fit after the inspection and the pickup; the
        pre-trip then comes after the rest or restart, before the first drive.
        """
        if not self.policy.pre_trip_min or self.clocks.pre_trip_done:
            return
        if self.clocks.window_start_min is not None or not self.trip.to_dropoff.drive_min:
            return  # not the start of a duty period, or nothing to drive afterwards
        work_min = self.policy.pre_trip_min + self.policy.pickup_min
        after_min, _ = self._driving_allowance(work_min, on_duty=True)
        if after_min > 0:
            self._record(Activity.PRE_TRIP, self.policy.pre_trip_min)

    def _drive_leg(self, leg: Leg) -> None:
        start_mile = self.mile
        driven_min = 0
        if leg.drive_min:
            self.miles_per_min = leg.distance_miles / leg.drive_min
        stops_in_a_row = 0
        while driven_min < leg.drive_min:
            if stops_in_a_row > MAX_STOPS_WITHOUT_DRIVING:
                raise RuntimeError(f"no stop lets driving resume at minute {self.now}")
            stops_in_a_row += 1

            if self.policy.pre_trip_min and not self.clocks.pre_trip_done:
                # D4: inspect before the first drive of each duty period, unless a limit
                # would leave no driving time after it; that stop then comes first.
                after_min, limit = self._driving_allowance(self.policy.pre_trip_min, on_duty=True)
                if after_min <= 0:
                    self._take_required_stop(limit)
                else:
                    self._record(Activity.PRE_TRIP, self.policy.pre_trip_min)
                continue

            allowed_min, limit = self._driving_allowance()
            if allowed_min <= 0:
                self._take_required_stop(limit)
                continue

            fuel_in_min = self._minutes_until_fuel()
            if fuel_in_min <= 0:
                # D7: at or before every 1,000 miles, on duty.
                self._record(
                    Activity.FUEL, self.policy.fuel_stop_min, reason=StopReason.FUEL_INTERVAL
                )
                continue

            stops_in_a_row = 0
            step_min = min(leg.drive_min - driven_min, allowed_min, fuel_in_min)
            driven_min += step_min
            self.drive_left_min -= step_min
            # Position from the leg start, so rounding never drifts across steps.
            end_mile = start_mile + leg.distance_miles * driven_min / leg.drive_min
            self._record(Activity.DRIVING, step_min, end_mile)

    def _driving_allowance(
        self, after_min: int = 0, on_duty: bool = False
    ) -> tuple[int, StopReason]:
        """Minutes the driver may keep driving, and the limit that will stop them.

        With `after_min`, the answer is for after a stop of that length (on duty or
        not) taken now. When two limits run out at the same minute, the one listed
        first is reported.
        """
        clocks, policy = self.clocks, self.policy
        window_start_min = self.now if clocks.window_start_min is None else clocks.window_start_min
        window_used_min = self.now + after_min - window_start_min
        cycle_used_min = clocks.cycle_used_min + (after_min if on_duty else 0)
        since_break_min = clocks.driving_since_break_min
        if after_min and clocks.not_driving_streak_min + after_min >= policy.break_min:
            since_break_min = 0
        limits = [
            # Listed first: on a tie with a rest limit the restart is taken, and it covers both.
            (policy.cycle_limit_min - cycle_used_min, StopReason.CYCLE_LIMIT),  # guide p. 10-11
            (policy.max_driving_min - clocks.driving_min, StopReason.DRIVING_LIMIT),  # guide p. 6
            (policy.duty_window_min - window_used_min, StopReason.DUTY_WINDOW),  # guide p. 6
            # Listed after the rest limits: on a tie the rest is taken, and it covers the break.
            (policy.break_after_driving_min - since_break_min, StopReason.BREAK_REQUIRED),  # p. 10
        ]
        return min(limits, key=lambda limit: limit[0])

    def _take_required_stop(self, reason: StopReason) -> None:
        """Insert the stop that lets driving continue."""
        match reason:
            case StopReason.CYCLE_LIMIT:
                # 70 hours on duty: 34 consecutive hours off restart the cycle (guide p. 11, D11).
                self._rest(Activity.RESTART, self.policy.restart_min, reason)
            case StopReason.DRIVING_LIMIT | StopReason.DUTY_WINDOW:
                if self._restart_instead_of_rest():
                    # D19: a restart is coming anyway, so take it now instead of
                    # resting 10 hours first. Same driving, 10 hours sooner.
                    self._rest(Activity.RESTART, self.policy.restart_min, StopReason.CYCLE_LIMIT)
                else:
                    # 10 consecutive hours off before driving again (guide p. 6-7).
                    self._rest(Activity.REST, self.policy.daily_rest_min, reason)
            case StopReason.BREAK_REQUIRED:
                after_min, limit = self._driving_allowance(self.policy.break_min)
                if after_min <= 0:
                    # No driving would fit after the break, so take the longer stop now.
                    self._take_required_stop(limit)
                elif self._minutes_until_fuel() <= self.policy.fuel_merge_window_min:
                    # D15: fuel due soon anyway. One fuel stop also counts as the break (D9).
                    self._record(Activity.FUEL, self.policy.fuel_stop_min, reason=reason)
                else:
                    # 8 hours of driving: 30 minutes off the wheel, off duty (guide p. 10, D5).
                    self._record(Activity.BREAK, self.policy.break_min, reason=reason)

    def _rest(self, activity: Activity, minutes: int, reason: StopReason) -> None:
        """A 10-hour rest or 34-hour restart, fuelling first when that saves a stop later."""
        if self._should_fuel_before_rest():
            self._record(Activity.FUEL, self.policy.fuel_stop_min, reason=StopReason.FUEL_INTERVAL)
        self._record(activity, minutes, reason=reason)

    def _should_fuel_before_rest(self) -> bool:
        """D16: fuel now, while stopped anyway, instead of on the road after the rest.

        Only when the trip needs more fuel, the tank will not last the next full
        shift, fuelling now does not add a fuel stop to the rest of the trip, and the
        fuel stop it replaces would not have doubled as the next shift's break.
        """
        if not self.policy.fuel_before_rest or self.drive_left_min == 0:
            return False
        stops_left = self._fuel_stops_left()
        if stops_left == 0:
            return False
        tank_left_miles = self.policy.fuel_interval_miles - self.clocks.miles_since_fuel
        miles_left = self.trip.total_miles - self.mile
        next_shift_miles = min(miles_left, self.policy.max_driving_min * self.miles_per_min)
        if tank_left_miles >= next_shift_miles:
            return False
        if 1 + self._fuel_stops_left(miles_since_fuel=0.0) > stops_left:
            return False
        # A fuel stop on the road can also be the next shift's break (D9). When it
        # would split that shift into two stretches of at most 8 hours, fuelling now
        # would cost a separate break later, so wait.
        shift_min = min(self.drive_left_min, self.policy.max_driving_min)
        break_after_min = self.policy.break_after_driving_min
        fuel_in_min = self._minutes_until_fuel()
        return not (
            shift_min > break_after_min
            and shift_min - break_after_min <= fuel_in_min <= break_after_min
        )

    def _minutes_until_fuel(self) -> int:
        """Whole minutes of driving left before the next fuel stop, at the current speed.

        Rounded down, so the stop always comes at or before the interval (D7).
        """
        tank_left_miles = self.policy.fuel_interval_miles - self.clocks.miles_since_fuel
        if math.isinf(tank_left_miles):
            return 10**9
        return math.floor(tank_left_miles / self.miles_per_min + EPSILON)

    def _fuel_stops_left(self, miles_since_fuel: float | None = None) -> int:
        """Fuel stops still needed: one each time the tank runs out with miles to go."""
        interval = self.policy.fuel_interval_miles
        if math.isinf(interval):
            return 0
        if miles_since_fuel is None:
            miles_since_fuel = self.clocks.miles_since_fuel
        miles_left = self.trip.total_miles - self.mile
        return max(0, math.ceil((miles_since_fuel + miles_left) / interval - EPSILON) - 1)

    def _restart_instead_of_rest(self) -> bool:
        """D19: take the 34-hour restart now, in place of this 10-hour rest?

        Only when the cycle cannot cover the work still to come and keeping the hours
        left would not save a restart. With one cycle of work or less ahead, that is
        always so: one restart covers the rest of the trip. With more, the driver
        rests and drives the cycle out, unless what is left of it is too little to
        save a restart anyway, e.g. less than the next shift's pre-trip.
        """
        policy = self.policy
        cycle_left_min = policy.cycle_limit_min - self.clocks.cycle_used_min
        needed_min = self._cycle_needed_min()
        if cycle_left_min >= needed_min:
            return False
        restarts_if_now = math.ceil(needed_min / policy.cycle_limit_min)
        # Kept hours that run out during the next shift stop it there: after that
        # restart, the shift starts over with a pre-trip of its own.
        cut_short_min = policy.pre_trip_min if cycle_left_min < policy.duty_window_min else 0
        restarts_if_later = math.ceil(
            (needed_min + cut_short_min - cycle_left_min) / policy.cycle_limit_min
        )
        return restarts_if_now <= restarts_if_later

    def _cycle_needed_min(self) -> int:
        """A lower bound on the on-duty minutes still needed before the last drive ends.

        Work after the last drive (the drop-off) is left out: on-duty work past 70
        hours is allowed (D14), so it never needs room in the cycle.
        """
        if self.drive_left_min == 0:
            return 0
        needed_min = self.drive_left_min
        # Each duty period starts with a pre-trip (D4) and drives at most 11 hours.
        max_driving_min = self.policy.max_driving_min
        duty_periods = math.ceil(self.drive_left_min / max_driving_min) if max_driving_min else 1
        needed_min += duty_periods * self.policy.pre_trip_min
        needed_min += self._fuel_stops_left() * self.policy.fuel_stop_min
        if not self.pickup_done and self.trip.to_dropoff.drive_min > 0:
            needed_min += self.policy.pickup_min
        return needed_min

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
        if activity is Activity.PRE_TRIP:
            self.clocks.pre_trip_done = True
        elif activity is Activity.FUEL:
            self.clocks.miles_since_fuel = 0.0
        elif activity is Activity.DRIVING:
            self.clocks.miles_since_fuel += end_mile - self.mile
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
                # A full rest resets the 11-hour limit and the 14-hour window (guide p. 6-7),
                # and the next duty period needs its own pre-trip (D4).
                clocks.driving_min = 0
                clocks.window_start_min = None
                clocks.pre_trip_done = False
            if clocks.off_streak_min >= self.policy.restart_min:
                clocks.cycle_used_min = 0  # the 34-hour restart (guide p. 11)
            return

        # All on-duty time counts toward the cycle, not just driving (guide p. 10).
        clocks.cycle_used_min += minutes
        clocks.off_streak_min = 0
        if clocks.window_start_min is None:
            # The window starts with any work, not with the first drive (guide p. 6).
            clocks.window_start_min = self.now
        if status is DutyStatus.DRIVING:
            clocks.driving_min += minutes
