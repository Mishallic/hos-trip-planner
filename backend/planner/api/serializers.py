"""Request validation. Anything wrong here is a 400 with the field names."""

from datetime import datetime
from functools import cache
from zoneinfo import available_timezones

from rest_framework import serializers

from planner.services.trip_planning import PlaceInput, PlanRequest

HEADER_FIELDS = (
    "driver",
    "carrier",
    "truck",
    "trailer",
    "shipper",
    "commodity",
    "load_id",
    "home_terminal",
)
START_TIME_FORMAT = "%Y-%m-%dT%H:%M"


@cache
def _time_zones() -> frozenset[str]:
    return frozenset(available_timezones())


class PlaceSerializer(serializers.Serializer):
    """A picked place {label, lat, lon}, or {query} to look up."""

    label = serializers.CharField(required=False, max_length=200)
    lat = serializers.FloatField(required=False, min_value=-90, max_value=90)
    lon = serializers.FloatField(required=False, min_value=-180, max_value=180)
    query = serializers.CharField(required=False, min_length=3, max_length=200)

    def validate(self, data):
        picked = "lat" in data and "lon" in data
        if picked == ("query" in data) or ("lat" in data) != ("lon" in data):
            raise serializers.ValidationError(
                "Send either a picked place (label, lat, lon) or a query, not both."
            )
        return data


class PlanRequestSerializer(serializers.Serializer):
    current = PlaceSerializer()
    pickup = PlaceSerializer()
    dropoff = PlaceSerializer()
    cycle_used_hours = serializers.DecimalField(
        max_digits=4, decimal_places=2, min_value=0, max_value=70
    )
    start_time = serializers.CharField(required=False)
    home_tz = serializers.CharField(required=False, max_length=64)
    driver = serializers.CharField(required=False, allow_blank=True, max_length=100)
    carrier = serializers.CharField(required=False, allow_blank=True, max_length=100)
    truck = serializers.CharField(required=False, allow_blank=True, max_length=100)
    trailer = serializers.CharField(required=False, allow_blank=True, max_length=100)
    shipper = serializers.CharField(required=False, allow_blank=True, max_length=100)
    commodity = serializers.CharField(required=False, allow_blank=True, max_length=100)
    load_id = serializers.CharField(required=False, allow_blank=True, max_length=100)
    home_terminal = serializers.CharField(required=False, allow_blank=True, max_length=200)

    def validate_start_time(self, value: str) -> datetime:
        try:
            return datetime.strptime(value, START_TIME_FORMAT)
        except ValueError as exc:
            raise serializers.ValidationError("Use local time as YYYY-MM-DDTHH:MM.") from exc

    def validate_home_tz(self, value: str) -> str:
        if value not in _time_zones():
            raise serializers.ValidationError("Use an IANA time zone, e.g. America/Chicago.")
        return value

    def to_plan_request(self) -> PlanRequest:
        data = self.validated_data
        return PlanRequest(
            current=PlaceInput(**data["current"]),
            pickup=PlaceInput(**data["pickup"]),
            dropoff=PlaceInput(**data["dropoff"]),
            cycle_used_min=round(data["cycle_used_hours"] * 60),
            start_time=data.get("start_time"),
            home_tz=data.get("home_tz"),
            header={key: data[key].strip() for key in HEADER_FIELDS if data.get(key)},
        )


class PlaceQuerySerializer(serializers.Serializer):
    q = serializers.CharField(min_length=3, max_length=200)
