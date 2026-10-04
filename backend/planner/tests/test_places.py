"""Stop names from the offline nearest-town lookup (GeoNames, US/CA/MX)."""

import random
import time

import pytest

from planner.domain.geometry import haversine_miles
from planner.providers.places import NearestTown, nearest_town


@pytest.fixture(scope="module")
def towns() -> NearestTown:
    return nearest_town()


def test_the_place_list_covers_three_countries(towns):
    assert len(towns) > 25_000


@pytest.mark.parametrize(
    ("point", "label"),
    [
        ((41.5252, -88.0834), "Joliet, IL"),  # in town: no "near"
        ((32.3906, -100.8640), "Colorado City, TX"),
        ((52.1324, -106.6689), "Saskatoon, SK"),  # Canada
        ((25.6843, -100.3172), "Monterrey, NLE"),  # Mexico
        ((41.1340, -101.7180), "Ogallala, NE"),
        # Downtown names the city, not a neighbourhood such as "Chicago Loop".
        ((41.8819, -87.6278), "Chicago, IL"),
        ((43.6532, -79.3832), "Toronto, ON"),
        ((19.4326, -99.1332), "Mexico City, CMX"),
    ],
)
def test_points_in_town_get_the_town(towns, point, label):
    assert towns.city_state(*point) == label


def test_the_rural_rest_stop_is_near_colorado_city(towns):
    # The rest stop that Photon named "Mitchell County, TX": 8.4 miles from town.
    assert towns.city_state(32.43, -101.0) == "near Colorado City, TX"


def test_near_starts_beyond_five_miles(towns):
    label, miles = towns.nearest(32.43, -101.0)

    assert miles == pytest.approx(8.4, abs=0.1)
    assert NearestTown(near_miles=10).city_state(32.43, -101.0) == label


def test_open_ocean_has_no_name(towns):
    assert towns.city_state(30.0, -140.0) is None


def test_grid_finds_the_same_town_as_a_full_scan(towns):
    # Random points across the three countries: the grid search must never miss a
    # closer place, including near cell edges.
    rng = random.Random(7)
    points = [(rng.uniform(15, 60), rng.uniform(-130, -60)) for _ in range(60)]

    for lat, lon in points:
        found = towns.nearest(lat, lon)
        best = min(haversine_miles((lat, lon), p) for p in towns._points)
        if found is None:
            assert best > 150
        else:
            assert found[1] == pytest.approx(best)


def test_a_whole_plan_takes_a_few_milliseconds(towns):
    rng = random.Random(1)
    stops = [(rng.uniform(25, 49), rng.uniform(-124, -67)) for _ in range(40)]

    start = time.perf_counter()
    for lat, lon in stops:
        towns.city_state(lat, lon)
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert elapsed_ms < 50, f"{elapsed_ms:.1f} ms for 40 stops"


def test_loaded_once_per_process():
    assert nearest_town() is nearest_town()


@pytest.mark.parametrize(
    ("typed", "town"),
    [("Pheonix", "Phoenix"), ("Albequerque", "Albuquerque"), ("Cincinatti", "Cincinnati")],
)
def test_a_misspelt_town_is_found_by_spelling(towns, typed, town):
    assert towns.spelled_like(typed) == town


def test_text_spelled_like_no_town_finds_none(towns):
    assert towns.spelled_like("asdfgh") is None
