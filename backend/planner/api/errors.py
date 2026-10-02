"""Every error the API returns is JSON: {"error": {"code", "message", ...}}.

400 invalid input (with the fields), 422 a place or route problem {field, code},
429 throttled, 503 a map service is down, 500 anything else. Never an HTML page.
"""

import logging

from django.http import JsonResponse
from rest_framework import exceptions, status
from rest_framework.response import Response

from planner.providers.base import ProviderError, UpstreamUnavailable
from planner.services.trip_planning import FieldError

logger = logging.getLogger("planner")


def error_body(code: str, message: str, **extra) -> dict:
    return {"error": {"code": code, "message": message, **extra}}


def exception_handler(exc, context):
    """DRF's EXCEPTION_HANDLER: map every exception a view can raise to JSON."""
    if isinstance(exc, exceptions.ValidationError):
        return Response(
            error_body("invalid", "Some fields are invalid.", fields=exc.detail),
            status=status.HTTP_400_BAD_REQUEST,
        )
    if isinstance(exc, exceptions.Throttled):
        response = Response(
            error_body("throttled", "Too many requests. Try again shortly.", retry_after=exc.wait),
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
        if exc.wait:
            response["Retry-After"] = str(int(exc.wait))
        return response
    if isinstance(exc, exceptions.APIException):
        return Response(error_body(exc.default_code, str(exc.detail)), status=exc.status_code)
    if isinstance(exc, FieldError):
        return Response(
            error_body(exc.code, str(exc), field=exc.field),
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    if isinstance(exc, UpstreamUnavailable):
        logger.warning("map service unavailable: %s", exc)
        return Response(
            error_body(
                exc.code,
                "A map service is not responding. Try again in a minute.",
                service=exc.service,
            ),
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    if isinstance(exc, ProviderError):
        logger.warning("map service error: %s", exc)
        return Response(error_body(exc.code, str(exc)), status=status.HTTP_503_SERVICE_UNAVAILABLE)

    # Includes the engine's RuntimeError when no stop lets driving resume.
    logger.exception("unhandled error planning a trip", exc_info=exc)
    return Response(
        error_body("internal_error", "Something went wrong planning this trip."),
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def not_found(request, exception=None):
    """Django's handler404: JSON, not the HTML page."""
    return JsonResponse(error_body("not_found", "No such endpoint."), status=404)


def server_error(request):
    """Django's handler500, for errors outside DRF views."""
    return JsonResponse(error_body("internal_error", "Something went wrong."), status=500)
