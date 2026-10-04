"""Place search with Nominatim (OpenStreetMap), used when Photon fails or finds nothing.

Nominatim's usage policy allows about one request per second, so it is only a
fallback for search and is never used for the many reverse lookups of a plan.
"""

import time
from collections.abc import Callable

import httpx

from . import http
from .base import TOWN_KINDS, Place, UpstreamUnavailable, place_kind
from .regions import COUNTRIES, is_supported, region_code

DEFAULT_URL = "https://nominatim.openstreetmap.org"
SERVICE = "Nominatim"
ADDRESS_KEYS = ("house_number", "road", "postcode", "city", "town", "village", "hamlet")


class NominatimGeocoder:
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
        params = {
            "q": query,
            "format": "jsonv2",
            "addressdetails": 1,
            "countrycodes": ",".join(c.lower() for c in COUNTRIES),
            "limit": limit,
        }
        response = http.get(self.client, f"{self.base_url}/search", params, SERVICE, self.sleep)
        if response.status_code != 200:
            raise UpstreamUnavailable(f"Nominatim returned HTTP {response.status_code}", SERVICE)
        try:
            results = response.json()
        except ValueError as exc:
            raise UpstreamUnavailable(
                "Nominatim sent a response that is not JSON", SERVICE
            ) from exc
        places = []
        for result in results:
            address = result.get("address", {})
            country = (address.get("country_code") or "").upper()
            if is_supported(country):
                places.append(_place(result, address, country))
        return places[:limit]


def _place(result: dict, address: dict, country: str) -> Place:
    state = address.get("state")
    region = (address.get("county"), state, region_code(state, country), address.get("country"))
    return Place(
        label=_label(result.get("name") or "", address, country),
        lat=float(result["lat"]),
        lon=float(result["lon"]),
        country_code=country,
        kind=_kind(result),
        address=_joined(address.get(key) for key in ADDRESS_KEYS),
        region=_joined((*region, country, COUNTRIES[country])),
    )


def _kind(result: dict) -> str:
    """Cities are often boundary=administrative here; addresstype says "city"."""
    if result.get("addresstype") in TOWN_KINDS:
        return "town"
    return place_kind(result.get("category"), result.get("type"))


def _joined(names) -> str:
    return " ".join(name for name in names if name)


def _label(name: str, address: dict, country: str) -> str:
    parts = [name or address.get("city") or address.get("town") or ""]
    state = region_code(address.get("state"), country)
    if state:
        parts.append(state)
    if country != "US":
        parts.append(COUNTRIES[country])
    return ", ".join(p for p in parts if p)
