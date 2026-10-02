"""Polyline encoding and mapping mile positions to points on the route."""

import pytest

from planner.domain.geometry import (
    RoutePath,
    decode_polyline,
    encode_polyline,
    haversine_miles,
    simplify,
)

# The worked example from Google's polyline format documentation.
GOOGLE_EXAMPLE = "_p~iF~ps|U_ulLnnqC_mqNvxq`@"
GOOGLE_POINTS = [(38.5, -120.2), (40.7, -120.95), (43.252, -126.453)]


def test_decodes_googles_example():
    assert decode_polyline(GOOGLE_EXAMPLE) == pytest.approx(GOOGLE_POINTS)


def test_encodes_googles_example():
    assert encode_polyline(GOOGLE_POINTS) == GOOGLE_EXAMPLE


def test_round_trip_keeps_five_decimals():
    points = [(41.87811, -87.62980), (41.52500, -88.08170), (-33.86882, 151.20929)]

    assert decode_polyline(encode_polyline(points)) == pytest.approx(points, abs=1e-5)


def test_empty_polyline():
    assert decode_polyline("") == []
    assert encode_polyline([]) == ""


def test_haversine_chicago_to_indianapolis():
    assert haversine_miles((41.8781, -87.6298), (39.7684, -86.1581)) == pytest.approx(165, abs=2)


class TestRoutePath:
    # Two straight legs along the equator: 1 degree of longitude is ~69.1 miles.
    LEG1 = [(0.0, 0.0), (0.0, 1.0)]
    LEG2 = [(0.0, 1.0), (0.0, 2.0), (0.0, 3.0)]

    def path(self):
        # Router distances differ a little from the geometry's own length.
        return RoutePath([(70.0, self.LEG1), (140.0, self.LEG2)])

    def test_start_and_end(self):
        assert self.path().locate(0) == (0.0, 0.0)
        assert self.path().locate(210) == (0.0, 3.0)

    def test_pickup_is_exactly_the_end_of_leg_one(self):
        assert self.path().locate(70) == (0.0, 1.0)

    def test_halfway_through_each_leg(self):
        assert self.path().locate(35) == pytest.approx((0.0, 0.5))
        assert self.path().locate(70 + 70) == pytest.approx((0.0, 2.0))

    def test_positions_outside_the_route_are_clamped(self):
        assert self.path().locate(-5) == (0.0, 0.0)
        assert self.path().locate(999) == (0.0, 3.0)

    def test_zero_mile_leg_stays_put(self):
        path = RoutePath([(0.0, [(5.0, 5.0)]), (69.1, [(5.0, 5.0), (5.0, 6.0)])])

        assert path.locate(0) == (5.0, 5.0)

    def test_leg_without_points_is_rejected(self):
        with pytest.raises(ValueError):
            RoutePath([(10.0, [])])


class TestSimplify:
    def test_straight_line_keeps_only_its_ends(self):
        line = [(0.0, x / 10) for x in range(11)]

        assert simplify(line, 0.0001) == [(0.0, 0.0), (0.0, 1.0)]

    def test_corners_are_kept(self):
        line = [(0.0, 0.0), (0.0, 0.5), (0.0, 1.0), (0.5, 1.0), (1.0, 1.0)]

        assert simplify(line, 0.0001) == [(0.0, 0.0), (0.0, 1.0), (1.0, 1.0)]

    def test_wiggles_below_the_tolerance_are_dropped(self):
        line = [(0.0, 0.0), (0.00005, 0.5), (0.0, 1.0)]

        assert simplify(line, 0.0001) == [(0.0, 0.0), (0.0, 1.0)]
        assert simplify(line, 0.00001) == line

    def test_short_lines_are_unchanged(self):
        assert simplify([(1.0, 2.0)], 0.1) == [(1.0, 2.0)]

    def test_a_line_deeper_than_the_recursion_limit_works(self):
        # Every point of a zigzag must be kept: the worst case, deeper than Python's
        # default recursion limit of 1,000. Kept small, since this case is quadratic.
        zigzag = [(0.001 * (i % 2), i * 0.001) for i in range(1_200)]

        assert len(simplify(zigzag, 0.0001)) == 1_200
