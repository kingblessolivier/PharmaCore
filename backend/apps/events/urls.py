from django.urls import path

from . import views

app_name = "events"

urlpatterns = [
    # F1 ships the OutboxEvent model + management command. A thin read-only
    # /api/events/outbox/ view (sys-admin only) lands in a follow-up PR
    # together with the admin inbox UI.
    path("health/", views.health, name="health"),
]