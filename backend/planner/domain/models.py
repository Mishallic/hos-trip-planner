"""Domain types for trip planning.

Time is integer minutes since the trip starts. Distance is miles along the route,
measured from the driver's current location. Calendar dates, time zones and place
names are added outside the engine.
"""

from dataclasses import dataclass
from enum import StrEnum


class DutyStatus(StrEnum):
    """The four lines of the log grid, top to bottom (guide p. 16-17)."""

    OFF_DUTY = "off_duty"
    SLEEPER_BERTH = "sleeper_berth"
    DRIVING = "driving"
    ON_DUTY = "on_duty"  # on duty, not driving


class Activity(StrEnum):
    """What the driver is doing. Drives the remarks, the stop list and the map."""

    PRE_TRIP = "pre_trip"
    DRIVING = "driving"
    PICKUP = "pickup"
    DROPOFF = "dropoff"
    FUEL = "fuel"
    BREAK = "break"  # 30-minute break
    REST = "rest"  # 10-hour daily rest
    RESTART = "restart"  # 34-hour cycle restart


class StopReason(StrEnum):
    """The limit that forced a stop. Shown next to rests and breaks."""

    DRIVING_LIMIT = "driving_limit"  # 11 hours of driving, guide p. 6
    DUTY_WINDOW = "duty_window"  # 14 hours since coming on duty, guide p. 6
    BREAK_REQUIRED = "break_required"  # 8 hours of driving without a break, guide p. 10
    CYCLE_LIMIT = "cycle_limit"  # 70 hours on duty in the cycle, guide p. 10-11


@dataclass(frozen=True, slots=True)
class Leg:
    """One routed leg: current location to pickup, or pickup to drop-off."""

    distance_miles: float
    drive_min: int

    def __post_init__(self) -> None:
        if self.distance_miles < 0 or self.drive_min < 0:
            raise ValueError("leg distance and driving time must not be negative")
        if self.distance_miles > 0 and self.drive_min == 0:
            raise ValueError("a leg with distance needs driving time")


@dataclass(frozen=True, slots=True)
class TripInput:
    """Everything the engine needs to schedule a trip."""

    to_pickup: Leg
    to_dropoff: Leg
    cycle_used_min: int  # on-duty minutes already used in the 70-hour cycle

    def __post_init__(self) -> None:
        if self.cycle_used_min < 0:
            raise ValueError("cycle hours used must not be negative")

    @property
    def total_miles(self) -> float:
        return self.to_pickup.distance_miles + self.to_dropoff.distance_miles


@dataclass(frozen=True, slots=True)
class Event:
    """One stretch of a single duty status. The trip timeline is a list of these."""

    activity: Activity
    status: DutyStatus
    start_min: int
    end_min: int
    start_mile: float
    end_mile: float
    reason: StopReason | None = None  # set on stops that a limit forced

    def __post_init__(self) -> None:
        if self.end_min <= self.start_min:
            raise ValueError("an event must last at least one minute")
        if (self.activity is Activity.DRIVING) != (self.status is DutyStatus.DRIVING):
            raise ValueError("only driving events use the driving status")
        if self.status is DutyStatus.DRIVING:
            if self.end_mile < self.start_mile:
                raise ValueError("driving cannot move backwards along the route")
            if self.reason is not None:
                raise ValueError("driving is never a forced stop")
        elif self.end_mile != self.start_mile:
            raise ValueError("the truck does not move outside driving events")

    @property
    def duration_min(self) -> int:
        return self.end_min - self.start_min
