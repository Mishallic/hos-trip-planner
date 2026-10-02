"""WSGI entrypoint. Vercel resolves it through WSGI_APPLICATION in settings."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()
