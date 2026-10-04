"""Every hours-of-service limit and planning assumption, in one place.

Limits cite the FMCSA "Interstate Truck Driver's Guide to Hours of Service"
(April 2022) by page. Assumptions cite the planning decisions (D1, D2, ...)
listed in the README. All times are integer minutes.
"""

import math
from dataclasses import dataclass

from .models import Activity, DutyStatus

HOUR = 60


@dataclass(frozen=True, slots=True)
class HOSPolicy:
    # Limits for a property-carrying driver on the 70-hour / 8-day schedule.
    max_driving_min: int = 11 * HOUR  # 11-hour driving limit, guide p. 6
    duty_window_min: int = 14 * HOUR  # 14-hour driving window, guide p. 6
    daily_rest_min: int = 10 * HOUR  # off duty that resets the 11 and 14, guide p. 6-7
    break_after_driving_min: int = 8 * HOUR  # cumulative driving before a break, guide p. 10
    break_min: int = 30  # consecutive non-driving minutes, guide p. 10
    cycle_limit_min: int = 70 * HOUR  # 70 hours on duty in 8 days, guide p. 10-11
    restart_min: int = 34 * HOUR  # consecutive off duty that resets the cycle, guide p. 11

    # Planning assumptions.
    # D4: on duty at the start of each duty period that drives (trip start, after every
    # 10-hour rest or 34-hour restart), before loading if the period starts at the
    # pickup. Per duty period, not per day.
    # 0 turns it off, which lets tests look at the FMCSA limits on their own.
    pre_trip_min: int = 30
    pickup_min: int = 60  # D13
    dropoff_min: int = 60  # D13
    fuel_interval_miles: float = 1000.0  # D7; math.inf turns fuel stops off
    fuel_stop_min: int = 30  # D7
    fuel_merge_window_min: int = 60  # D15: fuel due this soon is taken at the break instead
    fuel_before_rest: bool = True  # D16: fuel before a rest when the tank won't last the next shift
    max_avg_speed_mph: float = 55.0  # D8
    # D20: no drive shorter than this just before a rest, restart or break, when taking
    # the stop where the driver is costs no restart and at most this long. 0 turns it off.
    min_drive_min: int = 15
    rest_status: DutyStatus = DutyStatus.SLEEPER_BERTH  # D5
    break_status: DutyStatus = DutyStatus.OFF_DUTY  # D5
    restart_status: DutyStatus = DutyStatus.OFF_DUTY  # D11

    def status_for(self, activity: Activity) -> DutyStatus:
        """The log line an activity is drawn on."""
        match activity:
            case Activity.DRIVING:
                return DutyStatus.DRIVING
            case Activity.REST:
                return self.rest_status
            case Activity.BREAK:
                return self.break_status
            case Activity.RESTART:
                return self.restart_status
            case Activity.PRE_TRIP | Activity.PICKUP | Activity.DROPOFF | Activity.FUEL:
                return DutyStatus.ON_DUTY

    def drive_minutes(self, distance_miles: float, router_min: float) -> int:
        """Driving time for a leg: the router's estimate, but never faster than the cap (D8).

        Free routers estimate car travel times, which are too fast for a loaded truck.
        """
        if distance_miles <= 0:
            return 0
        capped_min = distance_miles * HOUR / self.max_avg_speed_mph
        # Subtract a hair before rounding up so float noise (600.0000001) stays 600.
        return max(1, math.ceil(max(router_min, capped_min) - 1e-9))


DEFAULT_POLICY = HOSPolicy()
