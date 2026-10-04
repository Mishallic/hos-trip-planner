from time import perf_counter

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from planner.services import trip_planning

from .presenters import places_json, plan_json
from .serializers import PlaceQuerySerializer, PlanRequestSerializer


def get_providers() -> trip_planning.Providers:
    """The map services. Tests replace this with fakes."""
    return trip_planning.default_providers()


class Health(APIView):
    def get(self, request: Request) -> Response:
        return Response({"status": "ok"})


class PlanTrip(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "plan"

    def post(self, request: Request) -> Response:
        started = perf_counter()
        serializer = PlanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        timings: dict[str, float] = {}
        plan = trip_planning.plan(serializer.to_plan_request(), get_providers(), timings=timings)
        shaped = perf_counter()
        body = plan_json(plan)
        # Stop reasons and sheet notes are worked out while shaping: part of computing.
        timings["compute"] = timings.get("compute", 0) + (perf_counter() - shaped) * 1000
        timings["total"] = (perf_counter() - started) * 1000
        response = Response(body)
        # Shows in the browser's network panel: where a slow plan spends its time.
        response["Server-Timing"] = ", ".join(
            f"{name};dur={ms:.1f}" for name, ms in timings.items()
        )
        return response


class Places(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "places"

    def get(self, request: Request) -> Response:
        serializer = PlaceQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        found = trip_planning.search_places(serializer.validated_data["q"], get_providers())
        return Response({"places": places_json(found)})
