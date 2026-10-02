"""Time zones from coordinates, offline (timezonefinder), and UTC offsets (zoneinfo)."""

from datetime import datetime
from functools import cache
from zoneinfo import ZoneInfo

from timezonefinder import TimezoneFinder

from .base import NotFound


@cache
def _finder() -> TimezoneFinder:
    # Loading the data takes about a second, so do it once per process, on first use.
    return TimezoneFinder()


def timezone_at(lat: float, lon: float) -> str:
    """The IANA time zone at a point, e.g. "America/Chicago"."""
    name = _finder().timezone_at(lat=lat, lng=lon)
    if not name:
        raise NotFound(f"no time zone at {lat:.4f}, {lon:.4f}", "timezonefinder")
    return name


def utc_offset_min(tz_name: str, local: datetime) -> int:
    """The zone's UTC offset in minutes at a local wall-clock time (D17)."""
    offset = local.replace(tzinfo=ZoneInfo(tz_name)).utcoffset()
    assert offset is not None
    return int(offset.total_seconds() // 60)
