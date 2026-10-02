"""Search with a fallback, and city names for many route points at once."""

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor

from .base import Cache, Geocoder, Place, ProviderError, ReverseGeocoder, UpstreamUnavailable

CITY_CACHE_SECONDS = 30 * 24 * 3600


class FallbackGeocoder:
    """Ask the primary service; ask the fallback if it fails or finds nothing."""

    def __init__(self, primary: Geocoder, fallback: Geocoder) -> None:
        self.primary = primary
        self.fallback = fallback

    def search(self, query: str, limit: int = 5) -> list[Place]:
        try:
            places = self.primary.search(query, limit)
        except UpstreamUnavailable:
            return self.fallback.search(query, limit)
        return places or self.fallback.search(query, limit)


class CityLookup:
    """ "City, ST" for each point of a plan, cheaply and within a time budget.

    Points are rounded so nearby stops share one lookup and one cache entry,
    duplicates are looked up once, at most `max_lookups` uncached points are sent
    per call (the rest get None, shown as a mile position), and only
    `max_workers` requests run at a time. A failed lookup gives None, not an
    error: a missing city name never stops a plan.
    """

    def __init__(
        self,
        reverse: ReverseGeocoder,
        cache: Cache,
        max_lookups: int = 30,
        max_workers: int = 4,
        precision: int = 2,  # 0.01 degrees, about 1 km
    ) -> None:
        self.reverse = reverse
        self.cache = cache
        self.max_lookups = max_lookups
        self.max_workers = max_workers
        self.precision = precision

    def cities(self, points: Sequence[tuple[float, float]]) -> list[str | None]:
        keys = [(round(lat, self.precision), round(lon, self.precision)) for lat, lon in points]
        found: dict[tuple[float, float], str | None] = {}
        missing = []
        for key in dict.fromkeys(keys):
            cached = self.cache.get(self._cache_key(key))
            if cached is not None:
                found[key] = cached or None  # "" caches a point with no city
            else:
                missing.append(key)

        to_lookup = missing[: self.max_lookups]
        if to_lookup:
            with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
                results = list(pool.map(self._lookup, to_lookup))
            for key, (ok, city) in zip(to_lookup, results, strict=True):
                found[key] = city
                if ok:
                    self.cache.set(self._cache_key(key), city or "", CITY_CACHE_SECONDS)
        return [found.get(key) for key in keys]

    def _lookup(self, key: tuple[float, float]) -> tuple[bool, str | None]:
        try:
            return True, self.reverse.city_state(*key)
        except ProviderError:
            return False, None  # not cached, so the next plan tries again

    def _cache_key(self, key: tuple[float, float]) -> str:
        return f"city:{key[0]:.{self.precision}f}:{key[1]:.{self.precision}f}"
