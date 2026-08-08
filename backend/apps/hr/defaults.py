"""Callable field defaults, in a module that imports no models.

A migration freezes a field default by *reference* — ``default=<function>`` — so
the module holding that function is imported by the migration loader, which runs
before the app registry has settled. Pointing it at a models module creates a
cycle: ``apps/hr/models.py`` imports ``models_people`` at its foot, the migration
imports ``models_people`` from outside, and on an autoreload the second import
finds the module present but only partly executed:

    AttributeError: module 'apps.hr.models_people' has no attribute
                    'current_cpd_year'

Nothing here may import from ``.models`` or ``.models_people``, and nothing model
-shaped belongs here. That single constraint is what keeps the cycle impossible
rather than merely unlikely.
"""

from __future__ import annotations

from django.utils import timezone


def current_cpd_year() -> int:
    """The CPD year to stamp on a new record, resolved when the record is made.

    A callable, not a value: ``default=date.today().year`` is evaluated once when
    the module is imported, so a long-running process stamps every record with
    the year the server last restarted — which in January is silently wrong for
    everything logged afterwards.
    """
    return timezone.localdate().year
