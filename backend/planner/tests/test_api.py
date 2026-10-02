"""The HTTP API, with fake map services. Every error must come back as JSON."""

import json
from datetime import datetime
from pathlib import Path

import httpx
import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework.throttling import ScopedRateThrottle

from planner.api import views
from planner.providers.base import Place, Unroutable, UpstreamUnavailable
from planner.providers.http import make_client
from planner.providers.osrm import OsrmRouter
from planner.providers.places import nearest_town
from planner.services import trip_planning
from planner.services.trip_planning import Providers

FIXTURES = Path(__file__).parent / "fixtures"
JOLIET = Place("Joliet, IL", 41.5250, -88.0817, "US")
CHICAGO = Place("Chicago, IL", 41.8781, -87.6298, "US")
GARY = Place("Gary, IN", 41.5934, -87.3464, "US")


class FakeGeocoder:
    def __init__(self, places=None, error=None):
        self.places = places or {"Joliet": JOLIET, "Chicago": CHICAGO, "Gary": GARY}
        self.error = error
        self.queries: list[str] = []

    def search(self, query, limit=5):
        self.queries.append(query)
        if self.error:
            raise self.error
        return [place for name, place in self.places.items() if name in query][:limit]


class FakeRouter:
    """Replays the recorded Joliet -> Chicago -> Gary route, or raises."""

    def __init__(self, error=None):
        self.error = error

    def route(self, current, pickup, dropoff):
        if self.error:
            raise self.error
        recorded = json.loads((FIXTURES / "osrm_route_ok.json").read_text(encoding="utf-8"))
        transport = httpx.MockTransport(lambda request: httpx.Response(200, json=recorded["body"]))
        return OsrmRouter(make_client(transport)).route(current, pickup, dropoff)


class DictCache:
    def __init__(self):
        self.data = {}

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value, timeout):
        self.data[key] = value


def providers(geocoder=None, router=None) -> Providers:
    return Providers(
        geocoder=geocoder or FakeGeocoder(),
        router=router or FakeRouter(),
        towns=nearest_town(),
        timezone_at=lambda lat, lon: "America/Chicago",
        cache=DictCache(),
        now=lambda tz: datetime(2026, 10, 5, 7, 0, tzinfo=tz),
    )


@pytest.fixture(autouse=True)
def fresh_throttles():
    cache.clear()  # throttle counters live in the cache
    yield
    cache.clear()


@pytest.fixture
def use(monkeypatch):
    def install(fake: Providers) -> Providers:
        monkeypatch.setattr(views, "get_providers", lambda: fake)
        return fake

    return install


def plan_body(**overrides):
    body = {
        "current": {"label": "Joliet, IL", "lat": JOLIET.lat, "lon": JOLIET.lon},
        "pickup": {"label": "Chicago, IL", "lat": CHICAGO.lat, "lon": CHICAGO.lon},
        "dropoff": {"label": "Gary, IN", "lat": GARY.lat, "lon": GARY.lon},
        "cycle_used_hours": 10,
        "start_time": "2026-10-05T07:00",
    }
    return body | overrides


def post_plan(client, body):
    return client.post(reverse("plan-trip"), body, content_type="application/json")


class TestHealth:
    def test_health_returns_ok(self, client):
        response = client.get(reverse("health"))

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_health_rejects_post_as_json(self, client):
        response = client.post(reverse("health"))

        assert response.status_code == 405
        assert response.json()["error"]["code"] == "method_not_allowed"


class TestPlan:
    def test_a_picked_trip_is_planned_without_geocoding(self, client, use):
        fake = use(providers())

        response = post_plan(client, plan_body())

        assert response.status_code == 200
        assert fake.geocoder.queries == []
        data = response.json()
        assert set(data) == {"summary", "stops", "timeline", "route", "logs", "log_header"}
        summary = data["summary"]
        assert summary["total_miles"] == pytest.approx(74.4, abs=0.2)
        assert summary["start"] == "2026-10-05T07:00-05:00"
        assert summary["stop_counts"]["pickup"] == summary["stop_counts"]["dropoff"] == 1
        assert summary["sheets"] == 1

    def test_stops_carry_place_reason_and_explanation(self, client, use):
        use(providers())

        stops = post_plan(client, plan_body()).json()["stops"]

        pickup = next(s for s in stops if s["kind"] == "pickup")
        assert pickup["place"] == "Chicago, IL"
        assert pickup["explanation"].startswith("Pickup: loading")
        assert pickup["start"].endswith("-05:00")

    def test_text_queries_are_geocoded(self, client, use):
        fake = use(providers())
        body = plan_body(
            current={"query": "Joliet"}, pickup={"query": "Chicago"}, dropoff={"query": "Gary"}
        )

        assert post_plan(client, body).status_code == 200
        assert sorted(fake.geocoder.queries) == ["Chicago", "Gary", "Joliet"]

    def test_home_time_zone_and_start_default_to_the_current_location_and_now(self, client, use):
        use(providers())
        body = plan_body()
        del body["start_time"]

        data = post_plan(client, body).json()

        assert data["summary"]["start"] == "2026-10-05T07:00-05:00"
        assert data["log_header"]["time_zone"] == "America/Chicago"

    def test_log_header_fields_are_echoed(self, client, use):
        use(providers())

        header = post_plan(client, plan_body(driver="J. Doe", truck="1042")).json()["log_header"]

        assert header["driver"] == "J. Doe"
        assert header["truck"] == "1042"
        assert header["utc_offset"] == "-05:00"

    def test_coordinates_are_rounded_and_the_line_stays_encoded(self, client, use):
        use(providers())

        data = post_plan(client, plan_body()).json()

        assert isinstance(data["route"]["polyline"], str)
        for stop in data["stops"]:
            assert round(stop["lat"], 5) == stop["lat"]


class TestErrors:
    def test_invalid_fields_are_400_with_each_field(self, client, use):
        use(providers())
        body = plan_body(cycle_used_hours=71, start_time="tomorrow", home_tz="Mars/Base")

        response = post_plan(client, body)

        assert response.status_code == 400
        error = response.json()["error"]
        assert error["code"] == "invalid"
        assert set(error["fields"]) == {"cycle_used_hours", "start_time", "home_tz"}

    def test_a_place_needs_coordinates_or_a_query(self, client, use):
        use(providers())

        response = post_plan(client, plan_body(pickup={"label": "Somewhere"}))

        assert response.status_code == 400
        assert "pickup" in response.json()["error"]["fields"]

    def test_unknown_place_is_422_on_its_field(self, client, use):
        use(providers())

        response = post_plan(client, plan_body(dropoff={"query": "Atlantis"}))

        assert response.status_code == 422
        assert response.json()["error"] | {"message": ""} == {
            "code": "not_found",
            "field": "dropoff",
            "message": "",
        }

    def test_no_road_route_is_422(self, client, use):
        use(providers(router=FakeRouter(Unroutable("NoRoute"))))

        response = post_plan(client, plan_body())

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "unroutable"

    def test_map_service_down_is_503(self, client, use):
        use(providers(router=FakeRouter(UpstreamUnavailable("OSRM is down", "OSRM"))))

        response = post_plan(client, plan_body())

        assert response.status_code == 503
        assert response.json()["error"]["code"] == "upstream_unavailable"
        assert response.json()["error"]["service"] == "OSRM"

    def test_engine_failure_is_a_clean_500(self, client, use, monkeypatch):
        use(providers())

        def stuck(*args, **kwargs):
            raise RuntimeError("no stop lets driving resume at minute 0")

        monkeypatch.setattr(trip_planning, "plan_trip", stuck)

        response = post_plan(client, plan_body())

        assert response.status_code == 500
        assert response["Content-Type"] == "application/json"
        assert response.json()["error"]["code"] == "internal_error"

    def test_malformed_json_is_400(self, client):
        response = client.post(reverse("plan-trip"), "not json", content_type="application/json")

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "parse_error"

    def test_unknown_url_is_json_404(self, client, settings):
        settings.DEBUG = False

        response = client.get("/api/nope")

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"


class TestPlaces:
    def test_autocomplete(self, client, use):
        use(providers())

        response = client.get(reverse("places"), {"q": "Chicago"})

        assert response.status_code == 200
        assert response.json() == {
            "places": [{"label": "Chicago, IL", "lat": 41.8781, "lon": -87.6298}]
        }

    def test_query_needs_three_characters(self, client, use):
        use(providers())

        response = client.get(reverse("places"), {"q": "Ch"})

        assert response.status_code == 400
        assert "q" in response.json()["error"]["fields"]

    def test_repeat_queries_come_from_the_cache(self, client, use):
        fake = use(providers())

        client.get(reverse("places"), {"q": "Chicago"})
        client.get(reverse("places"), {"q": "  chicago "})

        assert fake.geocoder.queries == ["Chicago"]


class TestThrottling:
    @pytest.fixture(autouse=True)
    def low_rates(self, monkeypatch):
        monkeypatch.setattr(
            ScopedRateThrottle, "THROTTLE_RATES", {"plan": "2/min", "places": "2/min"}
        )

    def test_plan_is_throttled_as_json(self, client, use):
        use(providers())

        codes = [post_plan(client, plan_body()).status_code for _ in range(3)]

        assert codes == [200, 200, 429]

    def test_places_is_throttled_with_retry_after(self, client, use):
        use(providers())
        for _ in range(2):
            client.get(reverse("places"), {"q": "Chicago"})

        response = client.get(reverse("places"), {"q": "Chicago"})

        assert response.status_code == 429
        assert response.json()["error"]["code"] == "throttled"
        assert int(response["Retry-After"]) > 0
