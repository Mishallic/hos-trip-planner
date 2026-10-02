"""One HTTP client for all map services: identifying User-Agent, timeouts, one retry."""

import time
from collections.abc import Callable

import httpx

from .base import UpstreamUnavailable

USER_AGENT = "hos-trip-planner/0.1 (+https://github.com/Mishallic/hos-trip-planner)"
TIMEOUT = httpx.Timeout(8.0, connect=3.0)
RETRY_DELAY_S = 0.5
MAX_RETRY_AFTER_S = 2.0


def make_client(transport: httpx.BaseTransport | None = None) -> httpx.Client:
    """A shared client. Tests pass a MockTransport that replays recorded responses."""
    return httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT,
        transport=transport,
        follow_redirects=True,
    )


def get(
    client: httpx.Client,
    url: str,
    params: dict,
    service: str,
    sleep: Callable[[float], None] = time.sleep,
) -> httpx.Response:
    """GET with one retry on a timeout, a dropped connection, 429 or 5xx.

    Other 4xx responses are returned as they are: some services (OSRM) explain
    a bad request in the body, and the caller turns that into a typed error.
    """
    for attempt in (1, 2):
        try:
            response = client.get(url, params=params)
        except httpx.TransportError as exc:
            if attempt == 2:
                raise UpstreamUnavailable(f"{service} did not respond: {exc}", service) from exc
            sleep(RETRY_DELAY_S)
            continue
        if response.status_code == 429 or response.status_code >= 500:
            if attempt == 2:
                raise UpstreamUnavailable(
                    f"{service} returned HTTP {response.status_code}", service
                )
            sleep(_retry_delay(response))
            continue
        return response
    raise AssertionError("unreachable")


def _retry_delay(response: httpx.Response) -> float:
    try:
        return min(float(response.headers.get("Retry-After", RETRY_DELAY_S)), MAX_RETRY_AFTER_S)
    except ValueError:
        return RETRY_DELAY_S
