"""The API's JSON: a planned trip and place suggestions, shaped for the web app.

Times are local ISO strings at the home terminal's fixed offset (D17); hours are
also given as h:mm. Coordinates are rounded to 5 places, about a metre.
"""

from collections import Counter

from planner.domain.explain import explain_stop, hm, sheet_notes
from planner.domain.geometry import decode_polyline, encode_polyline, simplify
from planner.domain.log_builder import DailyLog
from planner.domain.models import Activity
from planner.providers.base import Place
from planner.services.trip_planning import TripPlan

COORD_DP = 5
MAP_TOLERANCE_DEG = 0.0001  # about 11 m: invisible on the map, a sixth of the size
STOP_KINDS = ("pre_trip", "pickup", "dropoff", "fuel", "break", "rest", "restart")


def places_json(places: list[Place]) -> list[dict]:
    return [
        {"label": p.label, "lat": round(p.lat, COORD_DP), "lon": round(p.lon, COORD_DP)}
        for p in places
    ]


def plan_json(plan: TripPlan) -> dict:
    return {
        "summary": _summary(plan),
        "warnings": plan.warnings,
        "stops": _stops(plan),
        "timeline": _timeline(plan),
        "route": _route(plan),
        "logs": [_log(plan, log) for log in plan.logs],
        "log_header": {
            **{key: value for key, value in plan.header.items() if value},
            "time_zone": plan.time_zone,
            "utc_offset": plan.start_at.isoformat()[-6:],  # e.g. "-05:00"
        },
    }


def _summary(plan: TripPlan) -> dict:
    events, legs, at = plan.events, plan.legs, plan.at
    kinds = Counter(e.activity.value for e in events)
    driving_min = sum(e.duration_min for e in events if e.activity is Activity.DRIVING)
    pickup_event = next(e for e in events if e.activity is Activity.PICKUP)
    dropoff_event = next(e for e in events if e.activity is Activity.DROPOFF)
    return {
        "from": plan.current.label,
        "pickup": plan.pickup.label,
        "dropoff": plan.dropoff.label,
        "total_miles": round(sum(leg.distance_miles for leg in legs), 1),
        "driving": hm(driving_min),
        "driving_min": driving_min,
        "elapsed": hm(events[-1].end_min),
        "elapsed_min": events[-1].end_min,
        "start": at(0),
        "pickup_arrival": at(pickup_event.start_min),
        "dropoff_arrival": at(dropoff_event.start_min),
        "end": at(events[-1].end_min),
        "stop_counts": {kind: kinds.get(kind, 0) for kind in STOP_KINDS},
        "restart_needed": kinds.get("restart", 0) > 0,
        "sheets": len(plan.logs),
    }


def _stops(plan: TripPlan) -> list[dict]:
    stops = []
    for index, event in enumerate(plan.events):
        if event.activity is Activity.DRIVING:
            continue
        place = plan.places[event.start_mile]
        stops.append(
            {
                "kind": event.activity.value,
                "status": event.status.value,
                "start": plan.at(event.start_min),
                "end": plan.at(event.end_min),
                "duration_min": event.duration_min,
                "mile": round(event.start_mile, 1),
                "lat": round(place.lat, COORD_DP),
                "lon": round(place.lon, COORD_DP),
                "place": place.name,
                "reason": event.reason.value if event.reason else None,
                "explanation": explain_stop(plan.events, index, plan.clocks, plan.policy),
            }
        )
    return stops


def _timeline(plan: TripPlan) -> list[dict]:
    at = plan.at
    return [
        {
            "kind": event.activity.value,
            "status": event.status.value,
            "start": at(event.start_min),
            "end": at(event.end_min),
            "start_mile": round(event.start_mile, 1),
            "end_mile": round(event.end_mile, 1),
            "clocks": {
                "driving_left_min": c.driving_left_min,
                "window_left_min": c.window_left_min,
                "break_left_min": c.break_left_min,
                "cycle_left_min": c.cycle_left_min,
            },
        }
        for event, c in zip(plan.events, plan.clocks, strict=True)
    ]


def _route(plan: TripPlan) -> dict:
    route, legs = plan.route, plan.legs
    line = simplify(decode_polyline(route.polyline), MAP_TOLERANCE_DEG)
    return {
        "polyline": encode_polyline(line),  # for drawing; stops use the full geometry
        "legs": [
            {
                "to": destination,
                "miles": round(leg.distance_miles, 1),
                "router_min": round(leg.duration_min),
                "planned_min": planned.drive_min,  # capped at 55 mph (D8)
                "steps": [
                    {
                        "instruction": step.instruction,
                        "miles": round(step.distance_miles, 2),
                        "lat": round(step.lat, COORD_DP),
                        "lon": round(step.lon, COORD_DP),
                    }
                    for step in leg.steps
                ],
            }
            for destination, leg, planned in zip(
                ("pickup", "dropoff"), (route.to_pickup, route.to_dropoff), legs, strict=True
            )
        ],
    }


def _log(plan: TripPlan, log: DailyLog) -> dict:
    def name(mile: float) -> str | None:
        return plan.places[mile].name

    return {
        "date": log.date.isoformat(),
        "starts_at": log.starts_at.isoformat(timespec="minutes"),
        "segments": [
            {"status": s.status.value, "start": s.start_min, "end": s.end_min} for s in log.segments
        ],
        "totals_min": {status.value: minutes for status, minutes in log.totals_min.items()},
        "totals_hm": {status.value: hm(minutes) for status, minutes in log.totals_min.items()},
        "on_duty_hours": round(log.on_duty_hours, 2),
        "miles_today": round(log.miles_today, 1),
        "from": name(log.start_mile),
        "to": name(log.end_mile),
        "remarks": [
            {
                "minute": r.minute,
                "time": f"{r.minute // 60:02d}:{r.minute % 60:02d}",
                "status": r.status.value,
                "label": r.label,
                "place": name(r.mile),
                "mile": round(r.mile, 1),
                "reasons": [reason.value for reason in r.reasons],
            }
            for r in log.remarks
        ],
        "brackets": [
            {"start": b.start_min, "end": b.end_min, "place": name(b.mile)} for b in log.brackets
        ],
        "recap": {
            "on_duty_today_min": log.recap.on_duty_today_min,
            "cycle_used_min": log.recap.cycle_used_min,
            "available_tomorrow_min": log.recap.available_tomorrow_min,
            "approximate": log.recap.approximate,  # D12
        },
        "notes": sheet_notes(log, plan.policy),
    }
