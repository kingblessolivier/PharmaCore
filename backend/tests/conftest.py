"""Fixtures shared across the test suite.

Anything defined here is available to every test module without an import, so
this file is deliberately thin: only the handful of objects that almost every
module needs to build anything at all.
"""

from __future__ import annotations

import pytest
from apps.iam.models import Organization


@pytest.fixture
def organization(db: None) -> Organization:
    """A generic tenant to hang test data off.

    Modules that care about the depot/retail distinction define their own; this
    is for the ones that just need *an* organization to scope a record to.
    """
    return Organization.objects.create(name="Test Organization", type="DEPOT")
