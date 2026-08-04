from __future__ import annotations

from django.apps import AppConfig


class RetailConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.retail"
    verbose_name = "Retail POS"
