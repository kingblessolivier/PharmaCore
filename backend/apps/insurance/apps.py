from __future__ import annotations

from django.apps import AppConfig


class InsuranceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.insurance"
    verbose_name = "Insurance & claims"
