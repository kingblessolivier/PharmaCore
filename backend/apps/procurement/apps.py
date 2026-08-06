from __future__ import annotations

from django.apps import AppConfig


class ProcurementConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.procurement"
    label = "procurement"
    verbose_name = "Procurement & imports"

    def ready(self) -> None:
        # Registers the requisition / purchase-order / supplier-invoice approval
        # handlers with the central approvals engine.
        from apps.procurement import services  # noqa: F401
