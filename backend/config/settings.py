"""Django settings for the HOS Trip Planner API.

The API is stateless: there is no database, no auth and no sessions. Plans are
recomputed from their inputs on every request. Configuration comes from
environment variables so the same settings run locally and on Vercel.
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env_list(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


# Off unless asked for. manage.py turns it on for local runs (runserver); the tests
# use config/test_settings.py; Vercel serves config/wsgi.py, where it stays off.
DEBUG = os.environ.get("DJANGO_DEBUG") == "1"

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set when DEBUG is off.")
    SECRET_KEY = "dev-only-insecure-key"

# Any *.vercel.app name: Vercel routes a request to this project only by one of its own
# deployment names, and preview deployments get generated ones.
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,.vercel.app")

INSTALLED_APPS = [
    "rest_framework",
    "planner",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# Nothing is persisted, so there is no database.
DATABASES = {}

TEMPLATES = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "UNAUTHENTICATED_USER": None,
    "EXCEPTION_HANDLER": "planner.api.errors.exception_handler",
    # Per client IP. On Vercel each instance counts on its own, so this is best effort.
    "DEFAULT_THROTTLE_RATES": {"plan": "20/min", "places": "120/min"},
    # The client is the address the one proxy in front (Vercel's edge) put last in
    # X-Forwarded-For, never one the client wrote there itself.
    "NUM_PROXIES": 1,
}

# Routes have no trailing slash; never redirect a POST to add one.
APPEND_SLASH = False

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"planner": {"handlers": ["console"], "level": "INFO"}},
}
