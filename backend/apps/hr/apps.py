from __future__ import annotations

from django.apps import AppConfig


class HrConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.hr"
    label = "hr"

    def ready(self) -> None:
        # Registers the employee-termination and payroll-run approval handlers.
        from apps.hr import (
            payroll_run,  # noqa: F401
            services,  # noqa: F401
        )
