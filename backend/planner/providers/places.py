"""Stop names from the nearest town, offline.

Reads the bundled GeoNames place list (data/places_us_ca_mx.tsv.gz, built by
scripts/build_places.py) once per process and finds the nearest place with a
grid index. A plan's lookups take milliseconds and never touch the network.
Place data: GeoNames (https://www.geonames.org), CC BY 4.0.
"""

import gzip
import math
from functools import cache
from pathlib import Path

from planner.domain.geometry import haversine_miles

DATA_FILE = Path(__file__).parent / "data" / "places_us_ca_mx.tsv.gz"
CELL_DEG = 0.5  # grid cell size in degrees, about 35 miles north-south
MILES_PER_DEG_LAT = 69.0
MAX_SEARCH_MILES = 150.0  # beyond this, a point is not near any town worth naming


class NearestTown:
    """ "Joliet, IL" at a town, "near Colorado City, TX" when the nearest town is
    more than `near_miles` away (the guide's "nearest city, town, or village",
    p. 17)."""

    def __init__(self, data_file: Path = DATA_FILE, near_miles: float = 5.0) -> None:
        self.near_miles = near_miles
        self._labels: list[str] = []
        self._points: list[tuple[float, float]] = []
        self._grid: dict[tuple[int, int], list[int]] = {}
        text = gzip.decompress(data_file.read_bytes()).decode("utf-8")
        for line in text.splitlines():
            name, region, _country, lat, lon = line.split("\t")
            index = len(self._points)
            self._labels.append(f"{name}, {region}" if region else name)
            self._points.append((float(lat), float(lon)))
            self._grid.setdefault(_cell(float(lat), float(lon)), []).append(index)

    def __len__(self) -> int:
        return len(self._points)

    def city_state(self, lat: float, lon: float) -> str | None:
        found = self.nearest(lat, lon)
        if found is None:
            return None
        label, miles = found
        return label if miles <= self.near_miles else f"near {label}"

    def nearest(self, lat: float, lon: float) -> tuple[str, float] | None:
        """The nearest place and its distance in miles, or None if none within reach."""
        here = (lat, lon)
        best_index, best_miles = None, math.inf
        # Widen the search ring by ring until a place is found, then look at every
        # cell that could hold something closer, so the answer is exact.
        for radius_miles in _search_radii():
            for index in self._candidates(lat, lon, min(radius_miles, best_miles)):
                miles = haversine_miles(here, self._points[index])
                if miles < best_miles:
                    best_index, best_miles = index, miles
            if best_index is not None and best_miles <= radius_miles:
                break
        if best_index is None or best_miles > MAX_SEARCH_MILES:
            return None
        return self._labels[best_index], best_miles

    def _candidates(self, lat: float, lon: float, radius_miles: float):
        dlat = radius_miles / MILES_PER_DEG_LAT
        # Longitude degrees shrink toward the poles; use the widest span in the box.
        coslat = max(math.cos(math.radians(min(abs(lat) + dlat, 89.0))), 0.01)
        dlon = radius_miles / (MILES_PER_DEG_LAT * coslat)
        lat_lo, lon_lo = _cell(lat - dlat, lon - dlon)
        lat_hi, lon_hi = _cell(lat + dlat, lon + dlon)
        for i in range(lat_lo, lat_hi + 1):
            for j in range(lon_lo, lon_hi + 1):
                yield from self._grid.get((i, j), ())


def _cell(lat: float, lon: float) -> tuple[int, int]:
    return math.floor(lat / CELL_DEG), math.floor(lon / CELL_DEG)


def _search_radii():
    yield from (10.0, 25.0, 50.0, 100.0, MAX_SEARCH_MILES)


@cache
def nearest_town() -> NearestTown:
    """The shared instance, loaded on first use (about 28,000 places)."""
    return NearestTown()
