"""Place search with a fallback service."""

from .base import Geocoder, Place, UpstreamUnavailable


class FallbackGeocoder:
    """Ask the primary service; ask the fallback if it fails or finds nothing."""

    def __init__(self, primary: Geocoder, fallback: Geocoder) -> None:
        self.primary = primary
        self.fallback = fallback

    def search(self, query: str, limit: int = 5) -> list[Place]:
        try:
            places = self.primary.search(query, limit)
        except UpstreamUnavailable:
            return self.fallback.search(query, limit)
        return places or self.fallback.search(query, limit)
