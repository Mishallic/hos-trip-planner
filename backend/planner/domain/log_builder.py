"""Turns the engine's timeline into daily log sheets, one per calendar day.

Pure Python. Times on a sheet are minutes since that day's midnight in the home
terminal's time zone. The whole trip uses the terminal's UTC offset at the trip
start (D17), so every sheet is exactly 24 hours, even across a DST change.
"""

import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from .clocks import DutyClocks
from .models import ON_DUTY_STATUSES, Activity, DutyStatus, Event, StopReason
from .policy import DEFAULT_POLICY, HOSPolicy

DAY_MIN = 24 * 60

ACTIVITY_LABELS = {
    None: "Off duty",
    Activity.PRE_TRIP: "Pre-trip inspection",
    Activity.DRIVING: "Driving",
    Activity.PICKUP: "Pickup",
    Activity.DROPOFF: "Drop-off",
    Activity.FUEL: "Fuel",
    Activity.BREAK: "30-minute break",
    Activity.REST: "10-hour rest",
    Activity.RESTART: "34-hour restart",
}


@dataclass(frozen=True, slots=True)
class Segment:
    """A stretch of one duty status on a sheet: what the grid line draws."""

    status: DutyStatus
    start_min: int  # minutes since midnight, 0-1440
    end_min: int


@dataclass(frozen=True, slots=True)
class Remark:
    """A change of duty status, written under the grid with its location."""

    minute: int  # minutes since midnight on this sheet
    status: DutyStatus
    label: str  # e.g. "Pre-trip inspection, Pickup" when one status covers both
    activities: tuple[Activity | None, ...]
    reasons: tuple[StopReason, ...]  # limits that forced these stops, if any
    mile: float  # position along the route; place names are added outside the domain


@dataclass(frozen=True, slots=True)
class Bracket:
    """A stretch where the truck did not move, drawn under the grid (guide p. 18)."""

    start_min: int
    end_min: int
    mile: float


@dataclass(frozen=True, slots=True)
class Recap:
    """End-of-day 70-hour recap. Approximate (D12): earlier days are only known as
    the cycle hours entered for the trip."""

    on_duty_today_min: int  # lines 3 and 4
    cycle_used_min: int  # A: hours on duty in the cycle, through today
    available_tomorrow_min: int  # B: 70 hours minus A, never below zero
    approximate: bool = True  # always, for now: no day-by-day history is entered (D12)


@dataclass(frozen=True, slots=True)
class DailyLog:
    date: date
    starts_at: datetime  # midnight, with the fixed home-terminal offset (D17)
    segments: tuple[Segment, ...]
    totals_min: dict[DutyStatus, int]  # per grid line; always sums to 1440
    miles_today: float
    start_mile: float
    end_mile: float
    remarks: tuple[Remark, ...]
    brackets: tuple[Bracket, ...]
    recap: Recap

    @property
    def on_duty_hours(self) -> float:
        """Lines 3 and 4 as decimal hours, as written and circled on a paper log."""
        on_duty_min = self.totals_min[DutyStatus.DRIVING] + self.totals_min[DutyStatus.ON_DUTY]
        return on_duty_min / 60


@dataclass(slots=True)
class _Piece:
    """A stretch of the padded timeline, on an axis of minutes since day 1's midnight."""

    status: DutyStatus
    activity: Activity | None
    reason: StopReason | None
    start: int
    end: int
    start_mile: float
    end_mile: float
    on_trip: bool = field(default=True)  # False for the off-duty padding around the trip

    def mile_at(self, minute: int) -> float:
        if self.end_mile == self.start_mile:
            return self.start_mile
        share = (minute - self.start) / (self.end - self.start)
        return self.start_mile + (self.end_mile - self.start_mile) * share


def build_daily_logs(
    events: list[Event],
    trip_start: datetime,
    utc_offset_min: int,
    cycle_used_min: int,
    policy: HOSPolicy = DEFAULT_POLICY,
) -> list[DailyLog]:
    """One sheet per calendar day the trip touches, in the home terminal's time.

    `trip_start` is the local wall-clock time at the terminal, without tzinfo;
    seconds are dropped. `utc_offset_min` is the terminal's offset at that moment.
    """
    if not events:
        raise ValueError("a trip needs at least one event")
    if trip_start.tzinfo is not None:
        raise ValueError("trip_start must be a local time without tzinfo")

    tz = timezone(timedelta(minutes=utc_offset_min))
    day1 = datetime.combine(trip_start.date(), datetime.min.time(), tz)
    offset = trip_start.hour * 60 + trip_start.minute
    pieces = _padded_pieces(events, offset)
    day_count = max(1, math.ceil(pieces[-1].end / DAY_MIN))
    pieces = _pad_to_midnight(pieces, day_count)

    cycle_by_day = _cycle_used_at_end_of_each_day(pieces, day_count, cycle_used_min, policy)
    work_start = next(p.start for p in pieces if p.status in ON_DUTY_STATUSES)
    work_end = max(p.end for p in pieces if p.status in ON_DUTY_STATUSES)
    remarks_by_day = _remarks(pieces)

    logs = []
    for day in range(day_count):
        day_pieces = _clip(pieces, day * DAY_MIN, (day + 1) * DAY_MIN)
        totals = dict.fromkeys(DutyStatus, 0)
        for piece in day_pieces:
            totals[piece.status] += piece.end - piece.start
        on_duty_today = totals[DutyStatus.DRIVING] + totals[DutyStatus.ON_DUTY]
        cycle = cycle_by_day[day]
        logs.append(
            DailyLog(
                date=(day1 + timedelta(days=day)).date(),
                starts_at=day1 + timedelta(days=day),
                segments=_segments(day_pieces, day),
                totals_min=totals,
                miles_today=sum(
                    p.end_mile - p.start_mile for p in day_pieces if p.status is DutyStatus.DRIVING
                ),
                start_mile=day_pieces[0].start_mile,
                end_mile=day_pieces[-1].end_mile,
                remarks=tuple(remarks_by_day.get(day, ())),
                brackets=_brackets(day_pieces, day, work_start, work_end),
                recap=Recap(
                    on_duty_today_min=on_duty_today,
                    cycle_used_min=cycle,
                    available_tomorrow_min=max(0, policy.cycle_limit_min - cycle),
                ),
            )
        )
    return logs


def _padded_pieces(events: list[Event], offset: int) -> list[_Piece]:
    """The trip on the day axis, with off duty from day 1's midnight to the start (D10)."""
    pieces = []
    if offset:
        pieces.append(_Piece(DutyStatus.OFF_DUTY, None, None, 0, offset, 0.0, 0.0, on_trip=False))
    for e in events:
        pieces.append(
            _Piece(
                e.status,
                e.activity,
                e.reason,
                offset + e.start_min,
                offset + e.end_min,
                e.start_mile,
                e.end_mile,
            )
        )
    return pieces


def _pad_to_midnight(pieces: list[_Piece], day_count: int) -> list[_Piece]:
    """Off duty from the drop-off to the last day's midnight (D10). None if it ends there."""
    last = pieces[-1]
    if last.end < day_count * DAY_MIN:
        pieces.append(
            _Piece(
                DutyStatus.OFF_DUTY,
                None,
                None,
                last.end,
                day_count * DAY_MIN,
                last.end_mile,
                last.end_mile,
                on_trip=False,
            )
        )
    return pieces


def _clip(pieces: list[_Piece], start: int, end: int) -> list[_Piece]:
    """The parts of `pieces` inside [start, end); driving miles split in proportion."""
    clipped = []
    for p in pieces:
        if p.end <= start or p.start >= end:
            continue
        s, e = max(p.start, start), min(p.end, end)
        clipped.append(
            _Piece(p.status, p.activity, p.reason, s, e, p.mile_at(s), p.mile_at(e), p.on_trip)
        )
    return clipped


def _segments(day_pieces: list[_Piece], day: int) -> tuple[Segment, ...]:
    """Grid segments, with neighbours on the same line merged."""
    segments: list[Segment] = []
    base = day * DAY_MIN
    for p in day_pieces:
        if segments and segments[-1].status is p.status:
            segments[-1] = Segment(p.status, segments[-1].start_min, p.end - base)
        else:
            segments.append(Segment(p.status, p.start - base, p.end - base))
    return tuple(segments)


def _remarks(pieces: list[_Piece]) -> dict[int, list[Remark]]:
    """One remark per change of duty status, filed on the sheet where it happens.

    The driver was off duty before the trip (D10). A status that carries on past
    midnight is not a change, so the next sheet gets no remark for it.
    """
    runs: list[list[_Piece]] = []
    for p in pieces:
        if runs and runs[-1][-1].status is p.status:
            runs[-1].append(p)
        else:
            runs.append([p])

    by_day: dict[int, list[Remark]] = {}
    previous_status = DutyStatus.OFF_DUTY
    for run in runs:
        status = run[0].status
        if status is not previous_status:
            activities = tuple(dict.fromkeys(p.activity for p in run))
            day, minute = divmod(run[0].start, DAY_MIN)
            by_day.setdefault(day, []).append(
                Remark(
                    minute=minute,
                    status=status,
                    label=", ".join(ACTIVITY_LABELS[a] for a in activities),
                    activities=activities,
                    reasons=tuple(dict.fromkeys(p.reason for p in run if p.reason)),
                    mile=run[0].start_mile,
                )
            )
        previous_status = status
    return by_day


def _brackets(
    day_pieces: list[_Piece], day: int, work_start: int, work_end: int
) -> tuple[Bracket, ...]:
    """Stretches where the truck stood still, from the first on-duty minute of the
    trip to the last, as on the guide's completed grid (p. 18). The off-duty time
    before reporting and after the drop-off gets none."""
    brackets: list[Bracket] = []
    base = day * DAY_MIN
    for p in day_pieces:
        s, e = max(p.start, work_start), min(p.end, work_end)
        if p.status is DutyStatus.DRIVING or s >= e:
            continue
        if brackets and brackets[-1].end_min == s - base:
            brackets[-1] = Bracket(brackets[-1].start_min, e - base, brackets[-1].mile)
        else:
            brackets.append(Bracket(s - base, e - base, p.start_mile))
    return tuple(brackets)


def _cycle_used_at_end_of_each_day(
    pieces: list[_Piece], day_count: int, cycle_used_min: int, policy: HOSPolicy
) -> list[int]:
    """Recap line A for each day (D12): the hours entered plus on-duty time since,
    back to zero once 34 consecutive hours off complete a restart (guide p. 11)."""
    clocks = DutyClocks(cycle_used_min=cycle_used_min)
    by_day = []
    for day in range(day_count):
        for p in _clip(pieces, day * DAY_MIN, (day + 1) * DAY_MIN):
            if p.on_trip:  # padding is outside the plan; the hours entered cover it
                clocks.advance(p.status, p.start, p.end - p.start, policy)
        by_day.append(clocks.cycle_used_min)
    return by_day
