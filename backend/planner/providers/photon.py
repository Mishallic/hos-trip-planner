"""Place search with Photon (komoot), limited to the US, Canada and Mexico.

Stop names come from the offline nearest-town lookup (places.py), not from here.
"""

import time
from collections.abc import Callable

import httpx

from . import http
from .base import Place, UpstreamUnavailable, place_kind
from .regions import COUNTRIES, is_supported, region_code

DEFAULT_URL = "https://photon.komoot.io"
SERVICE = "Photon"
# West, south, east, north: North America, so "Texas" never means Queensland.
NORTH_AMERICA_BBOX = "-170,14,-50,72"


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
        # Twice the limit: some answers fall outside the US, Canada and Mexico.
        params = {"q": query, "limit": limit * 2, "lang": "en", "bbox": NORTH_AMERICA_BBOX}
        features = self._features("/api/", params)
        places = [_place(f) for f in features if is_supported(_props(f).get("countrycode"))]
        return places[:limit]

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
    return Place(
        label=_label(props),
        lat=lat,
        lon=lon,
        country_code=props.get("countrycode"),
        kind=place_kind(props.get("osm_key"), props.get("osm_value")),
        address=_joined(props.get(k) for k in ("housenumber", "street", "postcode", "city")),
        region=_region(props),
    )


def _region(props: dict) -> str:
    country = (props.get("countrycode") or "").upper()
    state = props.get("state")
    names = (props.get("county"), state, region_code(state, country), props.get("country"))
    return _joined((*names, country, COUNTRIES.get(country)))


def _joined(names) -> str:
    return " ".join(name for name in names if name)


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
