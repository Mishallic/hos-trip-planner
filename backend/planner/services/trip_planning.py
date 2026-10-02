"""Plans a trip end to end. The only place that wires the map services to the rules.

resolve places -> route -> time zone -> engine -> clocks -> daily logs -> stop names
-> one lean, JSON-ready response.
"""

from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from functools import cache
from time import perf_counter
from zoneinfo import ZoneInfo

from planner.domain.clocks import clocks_before_each_event
from planner.domain.explain import explain_stop, hm
from planner.domain.geometry import RoutePath, decode_polyline, encode_polyline, simplify
from planner.domain.hos_engine import plan_trip
from planner.domain.log_builder import build_daily_logs
from planner.domain.models import Activity, Leg, TripInput
from planner.domain.policy import DEFAULT_POLICY, HOSPolicy
from planner.providers.base import (
    Cache,
    Geocoder,
    NotFound,
    Place,
    ReverseGeocoder,
    Route,
    Router,
    Unroutable,
)
from planner.providers.cache import DjangoCache
from planner.providers.geocoding import FallbackGeocoder
from planner.providers.http import make_client
from planner.providers.nominatim import NominatimGeocoder
from planner.providers.osrm import OsrmRouter
from planner.providers.photon import PhotonGeocoder
from planner.providers.places import nearest_town
from planner.providers.timezones import timezone_at, utc_offset_min

COORD_DP = 5
MAP_TOLERANCE_DEG = 0.0001  # about 11 m: invisible on the map, a sixth of the size
PLACES_LIMIT = 6
STOP_KINDS = ("pre_trip", "pickup", "dropoff", "fuel", "break", "rest", "restart")


class FieldError(Exception):
    """A problem with one input, reported as 422 {field, code}."""

    def __init__(self, field: str, code: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.code = code


@dataclass(frozen=True)
class PlaceInput:
    """Either a place the user picked from autocomplete, or text to look up."""

    label: str | None = None
    lat: float | None = None
    lon: float | None = None
    query: str | None = None


@dataclass(frozen=True)
class PlanRequest:
    current: PlaceInput
    pickup: PlaceInput
    dropoff: PlaceInput
    cycle_used_min: int
    start_time: datetime | None = None  # local wall time at the home terminal
    home_tz: str | None = None  # IANA name; defaults to the current location's zone
    header: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Providers:
    geocoder: Geocoder
    router: Router
    towns: ReverseGeocoder
    timezone_at: Callable[[float, float], str]
    cache: Cache | None = None
    now: Callable[[ZoneInfo], datetime] = datetime.now


@cache
def default_providers() -> Providers:
    client = make_client()
    return Providers(
        geocoder=FallbackGeocoder(PhotonGeocoder(client), NominatimGeocoder(client)),
        router=OsrmRouter(client),
        towns=nearest_town(),
        timezone_at=timezone_at,
        cache=DjangoCache(),
    )


PLACES_CACHE_SECONDS = 24 * 3600


def search_places(query: str, providers: Providers) -> list[dict]:
    """Autocomplete: up to six places in the US, Canada or Mexico."""
    return [
        {"label": p.label, "lat": round(p.lat, COORD_DP), "lon": round(p.lon, COORD_DP)}
        for p in _search(query, providers)
    ]


def _search(query: str, providers: Providers) -> list[Place]:
    """Search, cached per query: retyping the same text, or planning with it after
    seeing it in autocomplete, costs nothing."""
    key = "places:" + " ".join(query.casefold().split())
    cached = providers.cache.get(key) if providers.cache else None
    if cached is not None:
        return [Place(*row) for row in cached]
    places = providers.geocoder.search(query, PLACES_LIMIT)
    if providers.cache:
        rows = [(p.label, p.lat, p.lon, p.country_code) for p in places]
        providers.cache.set(key, rows, PLACES_CACHE_SECONDS)
    return places


def plan(
    request: PlanRequest,
    providers: Providers,
    policy: HOSPolicy = DEFAULT_POLICY,
    timings: dict[str, float] | None = None,
) -> dict:
    """The full plan. If `timings` is given, it receives each stage's milliseconds."""
    clock = _StageClock(timings)
    # Looked up in parallel: each text search waits about a second on the service.
    fields = (
        ("current", request.current),
        ("pickup", request.pickup),
        ("dropoff", request.dropoff),
    )
    with ThreadPoolExecutor(max_workers=3) as pool:
        current, pickup, dropoff = pool.map(lambda f: _resolve(*f, providers), fields)
    clock.lap("geocode")
    try:
        route = providers.router.route(current, pickup, dropoff)
    except Unroutable as exc:
        raise FieldError("route", exc.code, "No road route connects these places.") from exc
    clock.lap("route")

    tz_name = request.home_tz or providers.timezone_at(current.lat, current.lon)
    start = request.start_time or providers.now(ZoneInfo(tz_name)).replace(tzinfo=None)
    start = start.replace(second=0, microsecond=0)
    offset_min = utc_offset_min(tz_name, start)  # fixed for the whole trip (D17)

    legs = [
        Leg(leg.distance_miles, policy.drive_minutes(leg.distance_miles, leg.duration_min))
        for leg in (route.to_pickup, route.to_dropoff)
    ]
    events = plan_trip(TripInput(*legs, cycle_used_min=request.cycle_used_min), policy)
    clocks = clocks_before_each_event(events, request.cycle_used_min, policy)
    logs = build_daily_logs(events, start, offset_min, request.cycle_used_min, policy)

    path = RoutePath(
        [
            (leg.distance_miles, decode_polyline(leg.polyline))
            for leg in (route.to_pickup, route.to_dropoff)
        ]
    )
    names: dict[float, str | None] = {}

    def place_at(mile: float) -> tuple[float, float, str | None]:
        lat, lon = path.locate(mile)
        key = round(mile, 1)
        if key not in names:
            names[key] = providers.towns.city_state(lat, lon)
        return round(lat, COORD_DP), round(lon, COORD_DP), names[key]

    trip_tz = timezone(timedelta(minutes=offset_min))
    start_at = start.replace(tzinfo=trip_tz)

    def at(minutes: int) -> str:
        return (start_at + timedelta(minutes=minutes)).isoformat(timespec="minutes")

    response = {
        "summary": _summary(events, legs, logs, at, current, pickup, dropoff),
        "stops": _stops(events, clocks, at, place_at, policy),
        "timeline": _timeline(events, clocks, at),
        "route": _route(route, legs),
        "logs": [_log(log, place_at) for log in logs],
        "log_header": {
            **{key: value for key, value in request.header.items() if value},
            "time_zone": tz_name,
            "utc_offset": start_at.isoformat()[-6:],  # e.g. "-05:00"
        },
    }
    clock.lap("compute")  # time zone, engine, clocks, logs, stop names, response
    return response


class _StageClock:
    def __init__(self, timings: dict[str, float] | None) -> None:
        self.timings = timings
        self.last = perf_counter()

    def lap(self, stage: str) -> None:
        now = perf_counter()
        if self.timings is not None:
            self.timings[stage] = (now - self.last) * 1000
        self.last = now


def _resolve(field_name: str, given: PlaceInput, providers: Providers) -> Place:
    if given.lat is not None and given.lon is not None:  # picked: no lookup needed
        return Place(given.label or f"{given.lat:.4f}, {given.lon:.4f}", given.lat, given.lon)
    try:
        found = _search(given.query or "", providers)
    except NotFound:
        found = []
    if not found:
        raise FieldError(
            field_name,
            "not_found",
            f'No place in the US, Canada or Mexico matches "{given.query}".',
        )
    return found[0]


def _summary(events, legs, logs, at, current, pickup, dropoff) -> dict:
    kinds = Counter(e.activity.value for e in events)
    driving_min = sum(e.duration_min for e in events if e.activity is Activity.DRIVING)
    pickup_event = next(e for e in events if e.activity is Activity.PICKUP)
    dropoff_event = next(e for e in events if e.activity is Activity.DROPOFF)
    return {
        "from": current.label,
        "pickup": pickup.label,
        "dropoff": dropoff.label,
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
        "sheets": len(logs),
    }


def _stops(events, clocks, at, place_at, policy) -> list[dict]:
    stops = []
    for index, event in enumerate(events):
        if event.activity is Activity.DRIVING:
            continue
        lat, lon, place = place_at(event.start_mile)
        stops.append(
            {
                "kind": event.activity.value,
                "status": event.status.value,
                "start": at(event.start_min),
                "end": at(event.end_min),
                "duration_min": event.duration_min,
                "mile": round(event.start_mile, 1),
                "lat": lat,
                "lon": lon,
                "place": place,
                "reason": event.reason.value if event.reason else None,
                "explanation": explain_stop(events, index, clocks, policy),
            }
        )
    return stops


def _timeline(events, clocks, at) -> list[dict]:
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
        for event, c in zip(events, clocks, strict=True)
    ]


def _route(route: Route, legs: list[Leg]) -> dict:
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


def _log(log, place_at) -> dict:
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
        "from": place_at(log.start_mile)[2],
        "to": place_at(log.end_mile)[2],
        "remarks": [
            {
                "minute": r.minute,
                "time": f"{r.minute // 60:02d}:{r.minute % 60:02d}",
                "status": r.status.value,
                "label": r.label,
                "place": place_at(r.mile)[2],
                "mile": round(r.mile, 1),
                "reasons": [reason.value for reason in r.reasons],
            }
            for r in log.remarks
        ],
        "brackets": [
            {"start": b.start_min, "end": b.end_min, "place": place_at(b.mile)[2]}
            for b in log.brackets
        ],
        "recap": {
            "on_duty_today_min": log.recap.on_duty_today_min,
            "cycle_used_min": log.recap.cycle_used_min,
            "available_tomorrow_min": log.recap.available_tomorrow_min,
            "approximate": True,  # D12
        },
    }
