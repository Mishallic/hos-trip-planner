"""What the planner needs from map services, as small interfaces.

The planning service depends on these protocols, not on OSRM or Photon, so
tests can swap in fakes and a provider can be replaced without touching the rest.
"""

from dataclasses import dataclass
from typing import Protocol


class ProviderError(Exception):
    """A map service could not answer. `code` is what the API reports."""

    code = "provider_error"

    def __init__(self, message: str, service: str = "") -> None:
        super().__init__(message)
        self.service = service


class NotFound(ProviderError):
    code = "not_found"


class Unroutable(ProviderError):
    code = "unroutable"


class UpstreamUnavailable(ProviderError):
    code = "upstream_unavailable"


@dataclass(frozen=True, slots=True)
class Place:
    label: str  # e.g. "Dallas, TX" or "Monterrey, NLE, Mexico"
    lat: float
    lon: float
    country_code: str | None = None
    kind: str = "other"  # "town" (city, town, village), "area" (county, state, ...) or "other"
    address: str = ""  # house number, street, postcode and city, beyond the label
    region: str = ""  # county, state and country, with their codes


TOWN_KINDS = frozenset({"city", "town", "village", "hamlet", "municipality"})


def place_kind(category: str | None, value: str | None) -> str:
    """ "town", "area" or "other", from an OpenStreetMap key and value (place=city, ...)."""
    if category == "place" and value in TOWN_KINDS:
        return "town"
    return "area" if category in ("place", "boundary") else "other"


@dataclass(frozen=True, slots=True)
class RouteStep:
    """One turn-by-turn instruction."""

    instruction: str  # e.g. "Turn right onto Richards Street"
    distance_miles: float  # driven after this maneuver, until the next one
    duration_min: float  # router estimate for that distance
    lat: float  # where the maneuver happens
    lon: float


@dataclass(frozen=True, slots=True)
class RouteLeg:
    distance_miles: float
    duration_min: float  # router estimate; the planner caps the speed (D8)
    points: tuple[tuple[float, float], ...]  # this leg's geometry, (lat, lon), decoded once
    steps: tuple[RouteStep, ...]


@dataclass(frozen=True, slots=True)
class Route:
    """Current location -> pickup -> drop-off."""

    to_pickup: RouteLeg
    to_dropoff: RouteLeg
    polyline: str  # the whole route, encoded (precision 5), for the map


class Router(Protocol):
    def route(self, current: Place, pickup: Place, dropoff: Place) -> Route: ...


class Geocoder(Protocol):
    def search(self, query: str, limit: int = 5) -> list[Place]:
        """Places in the US, Canada or Mexico, best match first. Empty if none."""
        ...


class ReverseGeocoder(Protocol):
    def city_state(self, lat: float, lon: float) -> str | None:
        """ "Joliet, IL" or "near Colorado City, TX" for a point, or None if no
        place is within reach."""
        ...


class Cache(Protocol):
    def get(self, key: str) -> object | None: ...

    def set(self, key: str, value: object, timeout: int) -> None: ...
