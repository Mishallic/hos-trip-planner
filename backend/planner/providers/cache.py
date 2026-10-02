"""The Cache interface backed by Django's cache.

On Vercel each function instance has its own in-memory cache, so this only
saves repeat lookups within an instance. It is best effort, not shared.
"""

from django.core.cache import cache as django_cache


class DjangoCache:
    def get(self, key: str) -> object | None:
        return django_cache.get(key)

    def set(self, key: str, value: object, timeout: int) -> None:
        django_cache.set(key, value, timeout)
