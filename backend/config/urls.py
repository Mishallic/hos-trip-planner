from django.urls import include, path

urlpatterns = [
    path("api/", include("planner.api.urls")),
]

# JSON, never Django's HTML error pages.
handler404 = "planner.api.errors.not_found"
handler500 = "planner.api.errors.server_error"
