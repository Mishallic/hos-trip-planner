"""Place search and reverse geocoding with Photon (komoot), limited to the US, CA and MX."""

import time
from collections.abc import Callable

import httpx

from . import http
from .base import Place, UpstreamUnavailable
from .regions import COUNTRIES, is_supported, region_code

DEFAULT_URL = "https://photon.komoot.io"
SERVICE = "Photon"
# West, south, east, north: North America, so "Texas" never means Queensland.
NORTH_AMERICA_BBOX = "-170,14,-50,72"
CITY_TYPES = {"city", "town", "village", "hamlet", "locality", "district"}


class PhotonGeocoder:
    def __init__(
        self,
        client: httpx.Client,
        base_url: str = DEFAULT_URL,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.client = client
        self.base_url = base_url.rstrip("/")
        self.sleep = sleep

    def search(self, query: str, limit: int = 5) -> list[Place]:
        params = {"q": query, "limit": limit * 2, "lang": "en", "bbox": NORTH_AMERICA_BBOX}
        features = self._features("/api/", params)
        places = [_place(f) for f in features if is_supported(_props(f).get("countrycode"))]
        return places[:limit]

    def city_state(self, lat: float, lon: float) -> str | None:
        features = self._features("/reverse", {"lat": lat, "lon": lon, "lang": "en"})
        for feature in features:
            props = _props(feature)
            if is_supported(props.get("countrycode")):
                return city_state(props)
        return None

    def _features(self, path: str, params: dict) -> list[dict]:
        response = http.get(self.client, f"{self.base_url}{path}", params, SERVICE, self.sleep)
        if response.status_code != 200:
            raise UpstreamUnavailable(f"Photon returned HTTP {response.status_code}", SERVICE)
        try:
            return response.json().get("features", [])
        except ValueError as exc:
            raise UpstreamUnavailable("Photon sent a response that is not JSON", SERVICE) from exc


def _props(feature: dict) -> dict:
    return feature.get("properties", {})


def _place(feature: dict) -> Place:
    props = _props(feature)
    lon, lat = feature["geometry"]["coordinates"]
    return Place(label=_label(props), lat=lat, lon=lon, country_code=props.get("countrycode"))


def _label(props: dict) -> str:
    """ "Dallas, TX", "Dallas County, IA", "Monterrey, NLE, Mexico"."""
    country = (props.get("countrycode") or "").upper()
    name = props.get("name")
    if not name and props.get("street"):  # a street address: "4100 Main Street"
        name = " ".join(p for p in (props.get("housenumber"), props.get("street")) if p)
    name = name or props.get("city") or ""
    if props.get("type") == "county" and "county" not in name.lower():
        name = f"{name} County"
    parts = [name]
    city = props.get("city")
    if city and city not in parts:
        parts.append(city)
    state = region_code(props.get("state"), country)
    if state and state not in parts:
        parts.append(state)
    if country != "US" and country in COUNTRIES:
        parts.append(COUNTRIES[country])
    return ", ".join(p for p in parts if p)


def city_state(props: dict) -> str | None:
    """ "Joliet, IL" from Photon or Nominatim address parts, as written in remarks."""
    country = (props.get("countrycode") or props.get("country_code") or "").upper()
    city = next(
        (
            props.get(key)
            for key in ("city", "town", "village", "hamlet", "locality")
            if props.get(key)
        ),
        None,
    )
    if not city and props.get("type") in CITY_TYPES:
        city = props.get("name")
    if not city and props.get("county"):
        county = props["county"]
        city = county if "county" in county.lower() else f"{county} County"
    state = region_code(props.get("state"), country)
    if not city:
        return state
    return f"{city}, {state}" if state else city
