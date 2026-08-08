"""Who may see and move trade between depots and pharmacies.

These viewsets scope by organization, which stops one pharmacy reading another's
orders. It does not stop *everyone inside* a pharmacy reading them — a cashier
had the depot's price offers, tender contracts and rep performance.

Reading needs a stake in the goods: stock visibility, or being the person who
receives them (a driver needs their deliveries). Changing needs the competence to
place or approve an order.
"""

from __future__ import annotations

from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.iam.models import User

READ_CODES = ("inventory.view", "order.receive", "order.create", "order.approve")
WRITE_CODES = ("order.create", "order.approve", "inventory.intake")


class DistributionAccess(BasePermission):
    """A stake in the goods to read; authority over an order to change."""

    message = "You do not have access to distribution records."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user.is_authenticated or not isinstance(user, User):
            return False
        codes = READ_CODES if request.method in SAFE_METHODS else WRITE_CODES
        return any(user.has_permission(code) for code in codes)
