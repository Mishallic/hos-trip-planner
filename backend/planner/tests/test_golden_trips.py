"""Golden trips: four real routes planned end to end and compared to snapshots.

Map responses are replayed from fixtures/golden/<trip>.json.gz through the real
Photon and OSRM adapters, so the whole chain runs: providers, planning service,
engine, daily logs and stop names. Any change to the plan shows up as a diff
against snapshots/<trip>.json.

    HOS_UPDATE_GOLDEN=1 pytest -k golden    # accept the new output as the snapshot
    HOS_RECORD_FIXTURES=1 pytest -k golden  # re-record map responses (network)
"""

import gzip
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path

import httpx
import pytest

from planner.api.presenters import plan_json
from planner.providers.geocoding import FallbackGeocoder
from planner.providers.http import make_client
from planner.providers.nominatim import NominatimGeocoder
from planner.providers.osrm import OsrmRouter
from planner.providers.photon import PhotonGeocoder
from planner.providers.places import nearest_town
from planner.providers.timezones import timezone_at
from planner.services.trip_planning import PlaceInput, PlanRequest, Providers, plan

HERE = Path(__file__).parent
FIXTURES = HERE / "fixtures" / "golden"
SNAPSHOTS = HERE / "snapshots"
RECORD = bool(os.environ.get("HOS_RECORD_FIXTURES"))
UPDATE = bool(os.environ.get("HOS_UPDATE_GOLDEN"))

TRIPS = {
    "dallas_fort_worth_houston": ("Dallas, TX", "Fort Worth, TX", "Houston, TX", 8),
    "chicago_indianapolis_denver": ("Chicago, IL", "Indianapolis, IN", "Denver, CO", 20),
    "los_angeles_phoenix_atlanta": ("Los Angeles, CA", "Phoenix, AZ", "Atlanta, GA", 52),
    "new_york_newark_seattle": ("New York, NY", "Newark, NJ", "Seattle, WA", 68),
}
START = datetime(2026, 10, 5, 7, 0)


def request_key(request: httpx.Request) -> str:
    params = "&".join(f"{k}={v}" for k, v in sorted(request.url.params.multi_items()))
    return f"{request.url.host}{request.url.path}?{params}"


class Recorder(httpx.BaseTransport):
    """Passes requests to the network and keeps every response."""

    def __init__(self) -> None:
        self.inner = httpx.HTTPTransport()
        self.recorded: dict[str, dict] = {}

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        response = self.inner.handle_request(request)
        response.read()
        self.recorded[request_key(request)] = {
            "status": response.status_code,
            "body": _trimmed(response.json()),
        }
        return response


def _trimmed(body):
    """Drop OSRM's per-step intersections: about half the size, and never read."""
    for route in body.get("routes", []) if isinstance(body, dict) else []:
        for leg in route.get("legs", []):
            for step in leg.get("steps", []):
                step.pop("intersections", None)
    return body


class Replayer(httpx.BaseTransport):
    """Answers from the recording; an unrecorded request fails the test loudly."""

    def __init__(self, recorded: dict[str, dict]) -> None:
        self.recorded = recorded

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        key = request_key(request)
        if key not in self.recorded:
            raise AssertionError(f"no recorded response for {key}")
        answer = self.recorded[key]
        return httpx.Response(answer["status"], json=answer["body"])


class NoCache:
    def get(self, key):
        return None

    def set(self, key, value, timeout):
        pass


def providers_for(transport: httpx.BaseTransport) -> Providers:
    client = make_client(transport)
    return Providers(
        geocoder=FallbackGeocoder(PhotonGeocoder(client), NominatimGeocoder(client)),
        router=OsrmRouter(client),
        towns=nearest_town(),
        timezone_at=timezone_at,
        cache=NoCache(),
    )


def snapshot_of(response: dict) -> dict:
    """The parts of a plan that matter, small enough to read in a diff, and a hash of
    the whole response, so a refactor that changes nothing provably changes nothing."""
    summary = response["summary"]
    whole = json.dumps(response, sort_keys=True, separators=(",", ":")).encode()
    return {
        "response_sha256": hashlib.sha256(whole).hexdigest(),
        "summary": {
            key: summary[key]
            for key in (
                "from",
                "pickup",
                "dropoff",
                "total_miles",
                "driving",
                "elapsed",
                "pickup_arrival",
                "dropoff_arrival",
                "stop_counts",
                "restart_needed",
                "sheets",
            )
        },
        "stops": [
            f"{s['start'][:16]}  {s['kind']:<8} mile {s['mile']:>7.1f}  "
            f"{s['place'] or '-'}{'  [' + s['reason'] + ']' if s['reason'] else ''}"
            for s in response["stops"]
        ],
        "sheets": [
            f"{log['date']}  off {log['totals_hm']['off_duty']:>5}  sb "
            f"{log['totals_hm']['sleeper_berth']:>5}  dr {log['totals_hm']['driving']:>5}  on "
            f"{log['totals_hm']['on_duty']:>5}  {log['miles_today']:>6.1f} mi  "
            f"recap A {log['recap']['cycle_used_min'] / 60:.2f} h"
            for log in response["logs"]
        ],
    }


@pytest.mark.parametrize("trip", sorted(TRIPS))
def test_golden_trip(trip):
    current, pickup, dropoff, cycle_h = TRIPS[trip]
    fixture_file = FIXTURES / f"{trip}.json.gz"
    snapshot_file = SNAPSHOTS / f"{trip}.json"

    if RECORD:
        transport: httpx.BaseTransport = Recorder()
    else:
        transport = Replayer(json.loads(gzip.decompress(fixture_file.read_bytes())))

    request = PlanRequest(
        current=PlaceInput(query=current),
        pickup=PlaceInput(query=pickup),
        dropoff=PlaceInput(query=dropoff),
        cycle_used_min=cycle_h * 60,
        start_time=START,
    )
    result = snapshot_of(plan_json(plan(request, providers_for(transport))))

    if RECORD:
        FIXTURES.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(transport.recorded, separators=(",", ":"), sort_keys=True).encode()
        fixture_file.write_bytes(gzip.compress(raw, compresslevel=9, mtime=0))
    if RECORD or UPDATE:
        SNAPSHOTS.mkdir(parents=True, exist_ok=True)
        snapshot_file.write_bytes((json.dumps(result, indent=2) + "\n").encode())  # LF only

    expected = json.loads(snapshot_file.read_text(encoding="utf-8"))
    assert result == expected
