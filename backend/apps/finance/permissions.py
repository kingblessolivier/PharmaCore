"""Who may read and who may change the company's books.

Every view in this app inherited the project default, ``IsAuthenticated`` — which
means "anyone with a password". A driver could read the general ledger, the trial
balance, bank accounts and customer credit limits. The side nav hid Finance from
them; a menu is not an access control.

The split is deliberately coarse and readable:

* ``finance.view`` to read — held by the accountant, the branch manager, the
  auditor and the insurance clerk, because each needs financial facts to do their
  job. **Scoping still applies on top**: a branch manager reads their own branch,
  not the group, via ``organizations_visible_to``.
* ``finance.manage`` to change anything.

Two roles that deliberately do *not* get either: ``CASHIER`` and ``DRIVER``. A
cashier's financial world is their own drawer, which lives in Retail.
"""

from __future__ import annotations

from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.iam.models import User


class FinanceAccess(BasePermission):
    """``finance.view`` to read, ``finance.manage`` to write."""

    message = "You do not have access to the company's financial records."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user.is_authenticated or not isinstance(user, User):
            return False
        if request.method in SAFE_METHODS:
            return user.has_permission("finance.view")
        return user.has_permission("finance.manage")


class FinanceManageOnly(BasePermission):
    """``finance.manage`` for both reading and writing.

    For the handful of endpoints where merely *reading* is already sensitive —
    bank account numbers and the payment runs that move money out of them. Being
    able to see the balance is not the same as being able to see the credentials.
    """

    message = "Only finance staff may access this."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user.is_authenticated or not isinstance(user, User):
            return False
        return user.has_permission("finance.manage")
