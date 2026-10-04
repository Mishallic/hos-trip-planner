"""The real settings, with a throwaway secret key, for the test suite."""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-key")

from .settings import *  # noqa: E402, F403
