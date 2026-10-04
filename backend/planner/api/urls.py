from django.urls import path

from . import views

urlpatterns = [
    path("health", views.Health.as_view(), name="health"),
    path("trips/plan", views.PlanTrip.as_view(), name="plan-trip"),
    path("places", views.Places.as_view(), name="places"),
]
