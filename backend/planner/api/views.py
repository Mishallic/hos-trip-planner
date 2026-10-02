import platform
from time import perf_counter

from rest_framework.decorators import api_view, throttle_classes
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from planner.services import trip_planning

from .serializers import PlaceQuerySerializer, PlanRequestSerializer


def get_providers() -> trip_planning.Providers:
    """The map services. Tests replace this with fakes."""
    return trip_planning.default_providers()


@api_view(["GET"])
def health(request: Request) -> Response:
    return Response({"status": "ok", "python": platform.python_version()})


@api_view(["POST"])
@throttle_classes([ScopedRateThrottle])
def plan_trip(request: Request) -> Response:
    started = perf_counter()
    serializer = PlanRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    timings: dict[str, float] = {}
    plan = trip_planning.plan(serializer.to_plan_request(), get_providers(), timings=timings)
    timings["total"] = (perf_counter() - started) * 1000
    response = Response(plan)
    # Shows in the browser's network panel: where a slow plan spends its time.
    response["Server-Timing"] = ", ".join(f"{name};dur={ms:.1f}" for name, ms in timings.items())
    return response


@api_view(["GET"])
@throttle_classes([ScopedRateThrottle])
def places(request: Request) -> Response:
    serializer = PlaceQuerySerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    found = trip_planning.search_places(serializer.validated_data["q"], get_providers())
    return Response({"places": found})


plan_trip.cls.throttle_scope = "plan"
places.cls.throttle_scope = "places"
