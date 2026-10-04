"""The driver's clocks and the plain-language reason for each stop."""

from datetime import datetime

from hypothesis import given

from planner.domain.clocks import Clocks, clocks_before_each_event
from planner.domain.explain import explain_stop, hm, sheet_notes
from planner.domain.hos_engine import plan_trip
from planner.domain.log_builder import build_daily_logs
from planner.domain.models import Activity, DutyStatus, TripInput
from planner.domain.policy import DEFAULT_POLICY, HOUR

from .hos_helpers import leg
from .test_hos_property import PROPERTY_SETTINGS, trips

H = HOUR


def plan_with_clocks(to_pickup_min, to_dropoff_min, cycle_used_min=0):
    events = plan_trip(TripInput(leg(to_pickup_min), leg(to_dropoff_min), cycle_used_min))
    return events, clocks_before_each_event(events, cycle_used_min)


def test_clocks_start_full_except_the_cycle():
    _, clocks = plan_with_clocks(2 * H, 3 * H, cycle_used_min=20 * H)

    assert clocks[0] == Clocks(11 * H, 14 * H, 8 * H, 50 * H)


def test_clocks_run_down_and_a_rest_refills_them():
    events, clocks = plan_with_clocks(6 * H, 6 * H)
    by_kind = {e.activity: c for e, c in zip(events, clocks, strict=True)}

    rest = by_kind[Activity.REST]
    assert rest.driving_left_min == 0  # 11 h driven: that is why the driver rests
    after_rest = clocks[events.index(next(e for e in events if e.activity is Activity.REST)) + 1]
    assert after_rest.driving_left_min == 11 * H
    assert after_rest.window_left_min == 14 * H
    assert after_rest.cycle_left_min == rest.cycle_left_min  # a rest does not reset the cycle


def test_restart_refills_the_cycle():
    events, clocks = plan_with_clocks(6 * H, 6 * H, cycle_used_min=65 * H)
    restart = next(i for i, e in enumerate(events) if e.activity is Activity.RESTART)

    assert clocks[restart].cycle_left_min == 0
    assert clocks[restart + 1].cycle_left_min == 70 * H


@PROPERTY_SETTINGS
@given(trip=trips)
def test_no_drive_outlasts_the_clocks_at_its_start(trip):
    events = plan_trip(trip)
    clocks = clocks_before_each_event(events, trip.cycle_used_min)

    for event, c in zip(events, clocks, strict=True):
        if event.status is DutyStatus.DRIVING:
            limit = min(c.driving_left_min, c.window_left_min, c.break_left_min, c.cycle_left_min)
            assert 0 < event.duration_min <= limit


class TestExplanations:
    def explain(self, to_pickup_min, to_dropoff_min, cycle_used_min=0):
        events, clocks = plan_with_clocks(to_pickup_min, to_dropoff_min, cycle_used_min)
        return {
            e.activity.value: explain_stop(events, i, clocks)
            for i, e in enumerate(events)
            if e.activity is not Activity.DRIVING
        }

    def test_rest_names_the_eleven_hour_limit(self):
        text = self.explain(6 * H, 6 * H)["rest"]

        assert text.startswith("11-hour driving limit reached after 11:00 of driving.")

    def test_break_names_the_eight_hours(self):
        text = self.explain(10 * H, 1 * H)["break"]

        assert text == "30-minute break required after 8:00 of driving."

    def test_restart_when_the_cycle_is_used_up(self):
        text = self.explain(6 * H, 6 * H, cycle_used_min=65 * H)["restart"]

        assert text == "70-hour cycle used up. 34 hours off duty restart it."

    def test_restart_instead_of_a_rest_says_why(self):
        text = self.explain(12 * H, 1 * H, cycle_used_min=58 * H)["restart"]

        assert text == (
            "Only 0:30 left in the 70-hour cycle, and the rest of the trip needs 3:30 on "
            "duty, so a restart is needed anyway: 34 hours off now, in place of a 10-hour rest."
        )

    def test_restart_before_the_trip_says_why(self):
        assert self.explain(1 * H, 1 * H, cycle_used_min=67 * H)["restart"] == (
            "Only 3:00 left in the 70-hour cycle, too little for this trip, so it starts "
            "with a 34-hour restart."
        )
        assert self.explain(0, 2 * H, cycle_used_min=70 * H)["restart"] == (
            "70-hour cycle used up, so the trip starts with a 34-hour restart."
        )

    def test_restart_instead_of_a_short_drive_says_why(self):  # D20
        text = self.explain(23, 22 * H, cycle_used_min=68 * H)["restart"]

        assert text == (
            "Only 0:07 left in the 70-hour cycle, too little to be worth driving, so the "
            "34-hour restart starts here."
        )

    def test_work_past_seventy_says_it_is_allowed(self):  # D14
        text = self.explain(7 * H + 30, 30, cycle_used_min=60 * H)["dropoff"]

        assert text.endswith("Allowed past 70 hours: the limit stops driving, not work.")

    def test_fuel_on_the_road(self):
        events = plan_trip(
            TripInput(leg(10 * H), leg(12 * H), 0),
            policy=DEFAULT_POLICY.__class__(fuel_before_rest=False),
        )
        clocks = clocks_before_each_event(events, 0)
        fuel = next(i for i, e in enumerate(events) if e.activity is Activity.FUEL)

        assert explain_stop(events, fuel, clocks) == (
            "Fuel at or before every 1,000 miles (999 miles since the last fill)."
        )

    def test_every_stop_kind_has_an_explanation(self):
        texts = self.explain(40 * H, 40 * H, cycle_used_min=40 * H)

        assert set(texts) >= {"pre_trip", "pickup", "dropoff", "fuel", "break", "rest"}
        assert all(texts.values())


class TestSheetNotes:
    """A sheet that seems over a limit says why it is not."""

    def notes(self, to_pickup_min, to_dropoff_min, cycle_used_min):
        events, _ = plan_with_clocks(to_pickup_min, to_dropoff_min, cycle_used_min)
        logs = build_daily_logs(events, datetime(2026, 10, 5, 7, 0), -300, cycle_used_min)
        return {log.date.isoformat(): sheet_notes(log) for log in logs}

    def test_more_than_eleven_hours_of_driving_on_a_sheet(self):
        notes = self.notes(23, 22 * H, cycle_used_min=68 * H)

        assert notes["2026-10-07"] == [
            "13:00 of driving on one sheet is within the rules: the 11-hour limit counts "
            "from the last 10-hour rest, not from midnight, and this day holds parts of "
            "two duty periods."
        ]

    def test_more_than_seventy_hours_in_the_recap(self):
        notes = self.notes(7 * H + 30, 30, cycle_used_min=60 * H)

        assert notes["2026-10-05"] == [
            "70:30 on duty in the cycle is within the rules: past 70 hours the driver may "
            "still work, but not drive, until a 34-hour restart."
        ]

    def test_an_ordinary_day_has_none(self):
        assert self.notes(2 * H, 3 * H, cycle_used_min=20 * H) == {"2026-10-05": []}


def test_hm():
    assert [hm(0), hm(75), hm(660), hm(2040)] == ["0:00", "1:15", "11:00", "34:00"]
