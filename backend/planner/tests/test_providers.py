"""Map service adapters, tested against responses recorded from the real services.

No test here touches the network. TestLiveServices runs only when the
HOS_LIVE_PROVIDERS environment variable is set, and never in CI.
"""

import json
import os
from datetime import datetime
from pathlib import Path

import httpx
import pytest

from planner.domain.geometry import RoutePath, decode_polyline, haversine_miles
from planner.providers.base import NotFound, Place, Unroutable, UpstreamUnavailable
from planner.providers.geocoding import FallbackGeocoder
from planner.providers.http import USER_AGENT, make_client
from planner.providers.nominatim import NominatimGeocoder
from planner.providers.osrm import OsrmRouter, instruction
from planner.providers.photon import PhotonGeocoder
from planner.providers.places import nearest_town
from planner.providers.regions import region_code
from planner.providers.timezones import timezone_at, utc_offset_min

FIXTURES = Path(__file__).parent / "fixtures"

JOLIET = Place("Joliet, IL", 41.5250, -88.0817)
CHICAGO = Place("Chicago, IL", 41.8781, -87.6298)
GARY = Place("Gary, IN", 41.5934, -87.3464)
HONOLULU = Place("Honolulu, HI", 21.3069, -157.8583)


def fixture(name: str) -> httpx.Response:
    recorded = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    return httpx.Response(recorded["status"], json=recorded["body"])


class Replay:
    """A fake network: answers each request with the next response (or raises it)."""

    def __init__(self, *responses: httpx.Response | Exception) -> None:
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def client(self) -> httpx.Client:
        return make_client(httpx.MockTransport(self))


def no_sleep(_seconds: float) -> None:
    pass


def router(*responses) -> tuple[OsrmRouter, Replay]:
    replay = Replay(*responses)
    return OsrmRouter(replay.client(), sleep=no_sleep), replay


class TestOsrmRoute:
    def test_one_request_for_all_three_points(self):
        osrm, replay = router(fixture("osrm_route_ok"))

        osrm.route(JOLIET, CHICAGO, GARY)

        [request] = replay.requests
        assert "-88.081700,41.525000;-87.629800,41.878100;-87.346400,41.593400" in request.url.path
        assert request.url.params["steps"] == "true"
        assert request.url.params["geometries"] == "polyline"
        assert request.headers["User-Agent"] == USER_AGENT

    def test_legs_in_miles_and_minutes(self):
        osrm, _ = router(fixture("osrm_route_ok"))

        route = osrm.route(JOLIET, CHICAGO, GARY)

        assert route.to_pickup.distance_miles == pytest.approx(44.5, abs=0.1)
        assert route.to_pickup.duration_min == pytest.approx(62.2, abs=0.1)
        assert route.to_dropoff.distance_miles == pytest.approx(29.9, abs=0.1)
        assert route.to_dropoff.duration_min == pytest.approx(45.6, abs=0.1)

    def test_turn_by_turn_steps(self):
        osrm, _ = router(fixture("osrm_route_ok"))

        route = osrm.route(JOLIET, CHICAGO, GARY)

        first_leg = [s.instruction for s in route.to_pickup.steps]
        assert len(first_leg) == 18
        assert first_leg[0].startswith("Head ")
        assert "on West Jefferson Street (US 30)" in first_leg[0]
        assert "Turn right onto Richards Street" in first_leg
        assert first_leg[-1] == "Arrive at the pickup"
        assert route.to_dropoff.steps[-1].instruction == "Arrive at the drop-off"
        legs = (route.to_pickup, route.to_dropoff)
        assert sum(s.distance_miles for leg in legs for s in leg.steps) == pytest.approx(
            route.to_pickup.distance_miles + route.to_dropoff.distance_miles, rel=1e-3
        )

    def test_geometry_is_kept_encoded_and_legs_meet_at_the_pickup(self):
        osrm, _ = router(fixture("osrm_route_ok"))

        route = osrm.route(JOLIET, CHICAGO, GARY)

        whole = decode_polyline(route.polyline)
        leg1 = decode_polyline(route.to_pickup.polyline)
        leg2 = decode_polyline(route.to_dropoff.polyline)
        assert haversine_miles(whole[0], (JOLIET.lat, JOLIET.lon)) < 1
        assert haversine_miles(whole[-1], (GARY.lat, GARY.lon)) < 1
        assert haversine_miles(leg1[-1], leg2[0]) < 0.01
        assert haversine_miles(leg1[-1], (CHICAGO.lat, CHICAGO.lon)) < 1

    def test_route_path_puts_the_pickup_mile_at_the_pickup(self):
        osrm, _ = router(fixture("osrm_route_ok"))
        route = osrm.route(JOLIET, CHICAGO, GARY)
        path = RoutePath(
            [
                (leg.distance_miles, decode_polyline(leg.polyline))
                for leg in (route.to_pickup, route.to_dropoff)
            ]
        )

        pickup = path.locate(route.to_pickup.distance_miles)

        assert haversine_miles(pickup, (CHICAGO.lat, CHICAGO.lon)) < 1

    def test_no_road_between_the_places_is_unroutable(self):
        osrm, _ = router(fixture("osrm_route_noroute"))

        with pytest.raises(Unroutable) as error:
            osrm.route(HONOLULU, CHICAGO, GARY)
        assert error.value.code == "unroutable"

    def test_one_retry_after_a_server_error(self):
        osrm, replay = router(httpx.Response(503), fixture("osrm_route_ok"))

        assert osrm.route(JOLIET, CHICAGO, GARY).to_pickup.steps
        assert len(replay.requests) == 2

    def test_two_server_errors_mean_upstream_unavailable(self):
        osrm, replay = router(httpx.Response(502), httpx.Response(503))

        with pytest.raises(UpstreamUnavailable) as error:
            osrm.route(JOLIET, CHICAGO, GARY)
        assert error.value.code == "upstream_unavailable"
        assert len(replay.requests) == 2

    def test_rate_limit_waits_for_retry_after_but_never_long(self):
        waits = []
        replay = Replay(
            httpx.Response(429, headers={"Retry-After": "30"}), fixture("osrm_route_ok")
        )
        osrm = OsrmRouter(replay.client(), sleep=waits.append)

        osrm.route(JOLIET, CHICAGO, GARY)

        assert waits == [2.0]

    def test_timeouts_are_retried_once(self):
        timeout = httpx.ReadTimeout("slow")
        osrm, replay = router(timeout, timeout)

        with pytest.raises(UpstreamUnavailable):
            osrm.route(JOLIET, CHICAGO, GARY)
        assert len(replay.requests) == 2

    def test_a_response_that_is_not_json(self):
        osrm, _ = router(httpx.Response(200, text="<html>maintenance</html>"))

        with pytest.raises(UpstreamUnavailable):
            osrm.route(JOLIET, CHICAGO, GARY)


def step(kind: str, modifier: str = "", maneuver: dict | None = None, **fields) -> dict:
    """An OSRM step with just the fields an instruction reads."""
    return {"maneuver": {"type": kind, "modifier": modifier, **(maneuver or {})}, **fields}


class TestInstructions:
    @pytest.mark.parametrize(
        ("osrm_step", "text"),
        [
            (step("turn", "left", name="Main St"), "Turn left onto Main St"),
            (step("turn", "uturn", name=""), "Make a U-turn"),
            (step("new name", ref="I 80"), "Continue onto I 80"),
            (step("merge", "slight right", ref="I 94"), "Merge slight right onto I 94"),
            (step("on ramp", "right", ref="I 55"), "Take the ramp onto I 55"),
            (step("off ramp", exits="143", destinations="Joliet"), "Take exit 143 toward Joliet"),
            (step("fork", "slight left", name="US 30"), "Keep left onto US 30"),
            (
                step("roundabout", maneuver={"exit": 2}, name="Oak Ave"),
                "At the roundabout, take exit 2 onto Oak Ave",
            ),
            (step("depart", maneuver={"bearing_after": 92}, name="Elm St"), "Head east on Elm St"),
            (step("arrive"), "Arrive at the pickup"),
            (step("something new"), "Continue"),
        ],
    )
    def test_text_for_each_maneuver(self, osrm_step, text):
        assert instruction(osrm_step, "pickup") == text


def photon(*responses) -> tuple[PhotonGeocoder, Replay]:
    replay = Replay(*responses)
    return PhotonGeocoder(replay.client(), sleep=no_sleep), replay


class TestPhotonSearch:
    def test_search_is_limited_to_north_america(self):
        geocoder, replay = photon(fixture("photon_search_texas_bbox"))

        geocoder.search("Texas")

        assert replay.requests[0].url.params["bbox"] == "-170,14,-50,72"

    def test_results_outside_us_ca_mx_are_dropped(self):
        # Recorded without the bounding box: it includes Texas, Queensland, Australia.
        geocoder, _ = photon(fixture("photon_search_texas"))

        places = geocoder.search("Texas")

        assert [p.country_code for p in places] == ["US", "US", "US", "US"]
        assert [p.label for p in places][:3] == [
            "Texas",
            "Texas County, MO",
            "Texas County, OK",
        ]

    def test_city_label_and_coordinates(self):
        geocoder, _ = photon(fixture("photon_search_dallas"))

        dallas = geocoder.search("Dallas")[0]

        assert dallas.label == "Dallas, TX"
        assert (dallas.lat, dallas.lon) == pytest.approx((32.78, -96.80), abs=0.05)

    def test_nothing_found_is_an_empty_list(self):
        geocoder, _ = photon(fixture("photon_search_empty"))

        assert geocoder.search("qxzvqxzvqq") == []

    def test_server_errors_mean_upstream_unavailable(self):
        geocoder, _ = photon(httpx.Response(500), httpx.Response(500))

        with pytest.raises(UpstreamUnavailable):
            geocoder.search("Dallas")


class TestNominatim:
    def test_search_asks_for_us_ca_mx_only(self):
        replay = Replay(fixture("nominatim_search_dallas"))
        geocoder = NominatimGeocoder(replay.client(), sleep=no_sleep)

        places = geocoder.search("Dallas")

        assert replay.requests[0].url.params["countrycodes"] == "us,ca,mx"
        assert places[0].label == "Dallas, TX"
        assert places[1].label == "Dallas County, TX"


class FakeGeocoder:
    def __init__(self, result: list[Place] | Exception) -> None:
        self.result = result
        self.calls = 0

    def search(self, query: str, limit: int = 5) -> list[Place]:
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class TestFallbackGeocoder:
    DALLAS = [Place("Dallas, TX", 32.78, -96.8, "US")]

    def test_primary_answer_is_used(self):
        primary, fallback = FakeGeocoder(self.DALLAS), FakeGeocoder([])

        assert FallbackGeocoder(primary, fallback).search("Dallas") == self.DALLAS
        assert fallback.calls == 0

    def test_fallback_when_the_primary_is_down(self):
        primary = FakeGeocoder(UpstreamUnavailable("down"))
        fallback = FakeGeocoder(self.DALLAS)

        assert FallbackGeocoder(primary, fallback).search("Dallas") == self.DALLAS

    def test_fallback_when_the_primary_finds_nothing(self):
        primary, fallback = FakeGeocoder([]), FakeGeocoder(self.DALLAS)

        assert FallbackGeocoder(primary, fallback).search("Dallas") == self.DALLAS


class TestRegions:
    @pytest.mark.parametrize(
        ("state", "country", "code"),
        [
            ("Illinois", "US", "IL"),
            ("ontario", "CA", "ON"),
            ("Nuevo León", "MX", "NLE"),
            ("Nuevo Leon", "mx", "NLE"),
            ("Atlantis", "US", "Atlantis"),
            (None, "US", None),
        ],
    )
    def test_codes(self, state, country, code):
        assert region_code(state, country) == code


class TestTimezones:
    def test_time_zone_at_a_point(self):
        assert timezone_at(41.88, -87.63) == "America/Chicago"
        assert timezone_at(19.43, -99.13) == "America/Mexico_City"

    def test_offset_follows_daylight_saving(self):
        assert utc_offset_min("America/Chicago", datetime(2026, 3, 7, 12, 0)) == -360
        assert utc_offset_min("America/Chicago", datetime(2026, 3, 9, 12, 0)) == -300


def test_missing_time_zone_is_not_found(monkeypatch):
    class NoZone:
        def timezone_at(self, lat, lng):
            return None

    monkeypatch.setattr("planner.providers.timezones._finder", NoZone)

    with pytest.raises(NotFound):
        timezone_at(0, 0)


@pytest.mark.skipif(not os.environ.get("HOS_LIVE_PROVIDERS"), reason="set HOS_LIVE_PROVIDERS=1")
class TestLiveServices:
    """Calls the real services. Run by hand: HOS_LIVE_PROVIDERS=1 pytest -k Live."""

    def test_route_search_and_reverse(self):
        client = make_client()

        route = OsrmRouter(client).route(JOLIET, CHICAGO, GARY)
        dallas = PhotonGeocoder(client).search("Dallas")[0]
        city = nearest_town().city_state(JOLIET.lat, JOLIET.lon)  # offline

        assert route.to_pickup.distance_miles > 30
        assert dallas.label == "Dallas, TX"
        assert city == "Joliet, IL"
