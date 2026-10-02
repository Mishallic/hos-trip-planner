"""Route geometry: encoded polylines, and where a mile position on the route lies.

Pure Python. The engine places every stop at a mile position along the route;
this module turns that position into a point on the map.
"""

import math
from bisect import bisect_right
from collections.abc import Sequence

EARTH_RADIUS_MILES = 3958.8
LatLon = tuple[float, float]


def decode_polyline(encoded: str, precision: int = 5) -> list[LatLon]:
    """Decode Google's encoded polyline format (the one OSRM returns)."""
    points: list[LatLon] = []
    index = lat = lon = 0
    factor = 10**precision
    while index < len(encoded):
        deltas = []
        for _ in range(2):
            shift = result = 0
            while True:
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            deltas.append(~(result >> 1) if result & 1 else result >> 1)
        lat += deltas[0]
        lon += deltas[1]
        points.append((lat / factor, lon / factor))
    return points


def encode_polyline(points: Sequence[LatLon], precision: int = 5) -> str:
    """Encode points in Google's polyline format. Lean to send to the browser."""
    factor = 10**precision
    out: list[str] = []
    prev_lat = prev_lon = 0
    for lat, lon in points:
        ilat, ilon = round(lat * factor), round(lon * factor)
        for delta in (ilat - prev_lat, ilon - prev_lon):
            value = ~(delta << 1) if delta < 0 else delta << 1
            while value >= 0x20:
                out.append(chr((0x20 | (value & 0x1F)) + 63))
                value >>= 5
            out.append(chr(value + 63))
        prev_lat, prev_lon = ilat, ilon
    return "".join(out)


def haversine_miles(a: LatLon, b: LatLon) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(h))


class RoutePath:
    """Maps a mile position on the route to a point on its geometry.

    The engine measures miles with the router's leg distances; the polyline's own
    length differs slightly. So each leg is mapped separately, by the share of the
    leg driven, and the pickup always lands exactly at the end of the first leg.
    """

    def __init__(self, legs: Sequence[tuple[float, Sequence[LatLon]]]) -> None:
        """`legs`: (router distance in miles, the leg's points), in route order."""
        self._legs = []
        start_mile = 0.0
        for distance_miles, points in legs:
            if not points:
                raise ValueError("every leg needs at least one point")
            cumulative = [0.0]
            for a, b in zip(points, points[1:], strict=False):
                cumulative.append(cumulative[-1] + haversine_miles(a, b))
            self._legs.append((start_mile, distance_miles, list(points), cumulative))
            start_mile += distance_miles

    def locate(self, mile: float) -> LatLon:
        """The point `mile` miles along the route, clamped to its ends."""
        leg = self._legs[-1]
        for candidate in self._legs:
            if mile <= candidate[0] + candidate[1]:
                leg = candidate
                break
        start_mile, distance_miles, points, cumulative = leg
        share = (mile - start_mile) / distance_miles if distance_miles > 0 else 0.0
        return _along(points, cumulative, min(max(share, 0.0), 1.0) * cumulative[-1])


def _along(points: list[LatLon], cumulative: list[float], miles: float) -> LatLon:
    """Interpolate the point `miles` along a polyline with these cumulative lengths."""
    if len(points) == 1 or miles <= 0:
        return points[0]
    if miles >= cumulative[-1]:
        return points[-1]
    i = bisect_right(cumulative, miles) - 1
    span = cumulative[i + 1] - cumulative[i]
    t = (miles - cumulative[i]) / span if span else 0.0
    (lat1, lon1), (lat2, lon2) = points[i], points[i + 1]
    return (lat1 + (lat2 - lat1) * t, lon1 + (lon2 - lon1) * t)


def simplify(points: Sequence[LatLon], tolerance_deg: float) -> list[LatLon]:
    """Drop points that change the line by less than `tolerance_deg` (Douglas-Peucker).

    For drawing only: stop positions are worked out on the full geometry.
    Iterative, so a long route cannot hit the recursion limit.
    """
    if len(points) < 3:
        return list(points)
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        farthest, max_distance = None, tolerance_deg
        for i in range(first + 1, last):
            distance = _distance_to_segment(points[i], points[first], points[last])
            if distance > max_distance:
                farthest, max_distance = i, distance
        if farthest is not None:
            keep[farthest] = True
            stack.extend(((first, farthest), (farthest, last)))
    return [p for p, kept in zip(points, keep, strict=True) if kept]


def _distance_to_segment(p: LatLon, a: LatLon, b: LatLon) -> float:
    """Planar distance in degrees from p to segment ab; fine at these small scales."""
    (py, px), (ay, ax), (by, bx) = p, a, b
    dx, dy = bx - ax, by - ay
    if dx == dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))
