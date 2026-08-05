from __future__ import annotations

from django.apps import AppConfig


class FinanceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.finance"

    def ready(self) -> None:
        # Registers the credit-override approval handler with the approvals engine.
        from apps.finance import services  # noqa: F401
