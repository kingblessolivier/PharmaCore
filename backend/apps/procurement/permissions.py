"""Who may do what on the buy side.

Deny-by-default, layered on the shared permission matrix (`resource.action`):

* ``procurement.view``    — see requisitions, orders, receipts, invoices
* ``procurement.manage``  — raise/edit requisitions, RFQs, orders, notes
* ``procurement.receive`` — book goods in against a purchase order
* ``procurement.invoice`` — register supplier invoices and run the 3-way match

Approving anything (requisition, PO, invoice) is *not* a procurement permission —
it belongs to the approvals engine (``approval.decide``), which is what enforces
claim-to-lock and no-self-approval.
"""

from __future__ import annotations

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.iam.models import User

SAFE_METHODS = ("GET", "HEAD", "OPTIONS")


def _is_admin(user: User) -> bool:
    return bool(user.is_superuser or user.has_role("SYS_ADMIN") or user.has_role("ORG_ADMIN"))


class _ProcurementPermission(BasePermission):
    """Base: authenticated + (admin or holds ``required``). Reads need only view."""

    required: str = "procurement.manage"

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user.is_authenticated or not isinstance(user, User):
            return False
        if _is_admin(user):
            return True
        if request.method in SAFE_METHODS:
            return user.has_permission("procurement.view")
        return user.has_permission(self.required)


class CanViewProcurement(_ProcurementPermission):
    required = "procurement.view"


class CanManageProcurement(_ProcurementPermission):
    required = "procurement.manage"


class CanReceiveGoods(_ProcurementPermission):
    required = "procurement.receive"


class CanHandleInvoices(_ProcurementPermission):
    required = "procurement.invoice"
