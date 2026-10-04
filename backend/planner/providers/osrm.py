"""Routing with OSRM: one request for current location -> pickup -> drop-off."""

import time
from collections.abc import Callable

import httpx

from planner.domain.geometry import decode_polyline

from . import http
from .base import Place, Route, RouteLeg, RouteStep, Unroutable, UpstreamUnavailable

DEFAULT_URL = "https://router.project-osrm.org"
METERS_PER_MILE = 1609.344
SERVICE = "OSRM"

COMPASS = ["north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest"]


class OsrmRouter:
    def __init__(
        self,
        client: httpx.Client,
        base_url: str = DEFAULT_URL,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.client = client
        self.base_url = base_url.rstrip("/")
        self.sleep = sleep

    def route(self, current: Place, pickup: Place, dropoff: Place) -> Route:
        coords = ";".join(f"{p.lon:.6f},{p.lat:.6f}" for p in (current, pickup, dropoff))
        response = http.get(
            self.client,
            f"{self.base_url}/route/v1/driving/{coords}",
            {"overview": "full", "geometries": "polyline", "steps": "true"},
            SERVICE,
            self.sleep,
        )
        try:
            body = response.json()
        except ValueError as exc:
            raise UpstreamUnavailable("OSRM sent a response that is not JSON", SERVICE) from exc

        code = body.get("code")
        if code in ("NoRoute", "NoSegment"):
            raise Unroutable(body.get("message") or "no road route between these places", SERVICE)
        if code != "Ok" or not body.get("routes"):
            raise UpstreamUnavailable(f"OSRM answered {code or response.status_code}", SERVICE)

        route = body["routes"][0]
        to_pickup, to_dropoff = (
            _leg(leg, destination)
            for leg, destination in zip(route["legs"], ("pickup", "drop-off"), strict=True)
        )
        return Route(to_pickup=to_pickup, to_dropoff=to_dropoff, polyline=route["geometry"])


def _leg(leg: dict, destination: str) -> RouteLeg:
    points: list[tuple[float, float]] = []
    for step in leg["steps"]:
        step_points = decode_polyline(step.get("geometry", ""))
        if points and step_points and step_points[0] == points[-1]:
            step_points = step_points[1:]  # steps share their joining point
        points.extend(step_points)
    ferry_meters = sum(step["distance"] for step in leg["steps"] if step.get("mode") == "ferry")
    return RouteLeg(
        distance_miles=leg["distance"] / METERS_PER_MILE,
        duration_min=leg["duration"] / 60,
        points=tuple(points),
        steps=tuple(_step(step, destination) for step in leg["steps"]),
        ferry_miles=ferry_meters / METERS_PER_MILE,
    )


def _step(step: dict, destination: str) -> RouteStep:
    lon, lat = step["maneuver"]["location"]
    return RouteStep(
        instruction=instruction(step, destination),
        distance_miles=step["distance"] / METERS_PER_MILE,
        duration_min=step["duration"] / 60,
        lat=lat,
        lon=lon,
    )


def instruction(step: dict, destination: str = "destination") -> str:
    """Readable text for an OSRM maneuver; OSRM itself returns only codes."""
    maneuver = step["maneuver"]
    kind = maneuver.get("type", "")
    modifier = maneuver.get("modifier", "")
    road = road_name(step)
    onto = f" onto {road}" if road else ""

    match kind:
        case "depart":
            heading = _compass(maneuver.get("bearing_after"))
            return f"Head {heading}{' on ' + road if road else ''}".strip()
        case "arrive":
            return f"Arrive at the {destination}"
        case "turn" | "end of road":
            if modifier in ("straight", ""):
                return f"Continue straight{onto}"
            if modifier == "uturn":
                return f"Make a U-turn{onto}"
            return f"Turn {modifier}{onto}"
        case "new name" | "continue" | "notification":
            return f"Continue{onto}" if road else "Continue"
        case "merge":
            return f"Merge {modifier}{onto}".replace("  ", " ")
        case "on ramp":
            return f"Take the ramp{onto}"
        case "off ramp":
            exits = step.get("exits")
            toward = step.get("destinations")
            text = f"Take exit {exits}" if exits else "Take the exit"
            return f"{text} toward {toward}" if toward else f"{text}{onto}"
        case "fork":
            side = modifier.replace("slight ", "") or "straight"
            return f"Keep {side}{onto}"
        case "roundabout" | "rotary" | "roundabout turn" | "exit roundabout" | "exit rotary":
            exit_number = maneuver.get("exit")
            exit_text = f", take exit {exit_number}" if exit_number else ""
            return f"At the roundabout{exit_text}{onto}"
        case _:
            return f"Continue{onto}" if road else "Continue"


def road_name(step: dict) -> str:
    """ "West Jefferson Street (US 30)", "I 80", or "" when OSRM has neither."""
    name = (step.get("name") or "").strip()
    ref = (step.get("ref") or "").replace(";", ",").strip()
    if name and ref:
        return f"{name} ({ref})"
    return name or ref


def _compass(bearing: float | None) -> str:
    if bearing is None:
        return ""
    return COMPASS[round(bearing / 45) % 8]
