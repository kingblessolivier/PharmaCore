from __future__ import annotations

from django.apps import AppConfig


class ServiceDeskConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.servicedesk"
    label = "servicedesk"
