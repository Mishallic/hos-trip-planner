"""Plans a trip end to end. The only place that wires the map services to the rules.

resolve places -> route -> time zone -> engine -> clocks -> daily logs -> stop names.
The API shapes the result as JSON (api/presenters.py).
"""

import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from functools import cache
from time import perf_counter
from zoneinfo import ZoneInfo

from planner.domain.clocks import Clocks, clocks_before_each_event
from planner.domain.geometry import RoutePath
from planner.domain.hos_engine import plan_trip
from planner.domain.log_builder import DailyLog, build_daily_logs
from planner.domain.models import Activity, Event, Leg, TripInput
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
from planner.providers.regions import COUNTRIES
from planner.providers.timezones import timezone_at, utc_offset_min

PLACES_LIMIT = 6


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
    towns = nearest_town()
    return Providers(
        geocoder=FallbackGeocoder(
            PhotonGeocoder(client), NominatimGeocoder(client), spelled_like=towns.spelled_like
        ),
        router=OsrmRouter(client),
        towns=towns,
        timezone_at=timezone_at,
        cache=DjangoCache(),
    )


PLACES_CACHE_SECONDS = 24 * 3600


def search_places(query: str, providers: Providers) -> list[Place]:
    """Autocomplete: up to six places in the US, Canada or Mexico."""
    return _search(query, providers)


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


@dataclass(frozen=True, slots=True)
class PlacePoint:
    """Where a mile of the route is, and what it is called on the log."""

    lat: float
    lon: float
    name: str | None  # "Joliet, IL", "near Colorado City, TX" (D18)


@dataclass(frozen=True)
class TripPlan:
    """A planned trip: the timeline and everything derived from it."""

    current: Place
    pickup: Place
    dropoff: Place
    route: Route
    legs: tuple[Leg, Leg]  # as planned: the router's miles, driving capped at 55 mph (D8)
    events: list[Event]
    clocks: list[Clocks]  # what was left just before each event
    logs: list[DailyLog]
    start_at: datetime  # the trip start at the home terminal's fixed UTC offset (D17)
    time_zone: str  # the home terminal's IANA name
    header: dict[str, str]
    places: dict[float, PlacePoint]  # every mile a stop, remark or sheet mentions
    warnings: list[str]
    policy: HOSPolicy

    def at(self, minutes: int) -> str:
        """Minutes since the start as local time, e.g. "2026-10-05T07:00-05:00"."""
        return (self.start_at + timedelta(minutes=minutes)).isoformat(timespec="minutes")


def plan(
    request: PlanRequest,
    providers: Providers,
    policy: HOSPolicy = DEFAULT_POLICY,
    timings: dict[str, float] | None = None,
) -> TripPlan:
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

    to_pickup, to_dropoff = (
        Leg(leg.distance_miles, policy.drive_minutes(leg.distance_miles, leg.duration_min))
        for leg in (route.to_pickup, route.to_dropoff)
    )
    events = plan_trip(TripInput(to_pickup, to_dropoff, request.cycle_used_min), policy)
    logs = build_daily_logs(events, start, offset_min, request.cycle_used_min, policy)
    result = TripPlan(
        current=current,
        pickup=pickup,
        dropoff=dropoff,
        route=route,
        legs=(to_pickup, to_dropoff),
        events=events,
        clocks=clocks_before_each_event(events, request.cycle_used_min, policy),
        logs=logs,
        start_at=start.replace(tzinfo=timezone(timedelta(minutes=offset_min))),
        time_zone=tz_name,
        header=request.header,
        places=_name_places(events, logs, route, (current, pickup, dropoff), providers.towns),
        warnings=_warnings(route),
        policy=policy,
    )
    clock.lap("compute")  # time zone, engine, clocks, logs, stop names
    return result


def _name_places(
    events: list[Event],
    logs: list[DailyLog],
    route: Route,
    endpoints: tuple[Place, Place, Place],
    towns: ReverseGeocoder,
) -> dict[float, PlacePoint]:
    """Every stop, remark, bracket and sheet edge, located on the route and named (D18).

    The start, pickup and drop-off are where the user said; other places are named
    after the nearest town. Names are looked up once per tenth of a mile.
    """
    legs = (route.to_pickup, route.to_dropoff)
    path = RoutePath([(leg.distance_miles, leg.points) for leg in legs])
    current, pickup, dropoff = endpoints
    to_pickup = legs[0].distance_miles
    names: dict[float, str | None] = {
        round(mile, 1): _town_of(place, towns)
        for mile, place in (
            (0.0, current),
            (to_pickup, pickup),
            (to_pickup + legs[1].distance_miles, dropoff),
        )
    }
    miles = [event.start_mile for event in events if event.activity is not Activity.DRIVING]
    for log in logs:
        miles += [log.start_mile, log.end_mile]
        miles += [remark.mile for remark in log.remarks]
        miles += [bracket.mile for bracket in log.brackets]
    places: dict[float, PlacePoint] = {}
    for mile in miles:
        if mile in places:
            continue
        lat, lon = path.locate(mile)
        key = round(mile, 1)
        if key not in names:
            names[key] = towns.city_state(lat, lon)
        places[mile] = PlacePoint(lat, lon, names[key])
    return places


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


REGION_CODE = re.compile(r"[A-Z]{2,3}")  # "TX", "QC", "NLE"


def _town_of(place: Place, towns: ReverseGeocoder) -> str | None:
    """ "City, ST" for a place the user named: "Saint Louis, MO" for "Washington
    University in St. Louis, Saint Louis, MO". The nearest town when the label has none."""
    parts = [part.strip() for part in place.label.split(",") if part.strip()]
    if parts and parts[-1] in COUNTRIES.values():
        parts.pop()  # "Montreal, QC, Canada" is "Montreal, QC" on a log
    if len(parts) >= 2 and REGION_CODE.fullmatch(parts[-1]):
        return ", ".join(parts[-2:])
    return towns.city_state(place.lat, place.lon)


def _warnings(route: Route) -> list[str]:
    ferry_miles = route.to_pickup.ferry_miles + route.to_dropoff.ferry_miles
    if ferry_miles < 0.5:
        return []
    return [
        f"The route crosses {ferry_miles:,.0f} miles by ferry, planned as driving: "
        "stops near the crossing may differ."
    ]
