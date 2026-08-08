"""Who may read a patient's record and the narcotics register.

The audit named the controlled-substances register (D2) and I fixed the finance
half of that finding and not this one. A re-check found it still open — and two
things the original audit had not looked at:

* ``/api/retail/dispensing/`` — who was given what, by name;
* ``/api/retail/prescriptions/`` — the prescriber, the patient and the medicine.

Both were readable by a driver and a warehouse clerk. Neither has any business
with a patient record, and the controlled register is the document a Rwanda FDA
inspector asks for.

The split follows who is accountable for the record rather than who happens to be
in the building:

``PatientRecordAccess``   dispensing history and prescriptions — the people who
                          fill them (``sale.create``) and the people who audit
                          them (``audit.view``).
``ControlledRegister``    narcotics and psychotropics — a pharmacist
                          (``sale.dispense``) or an auditor. Writing it needs the
                          licence, always: a cashier may sell a prescription item
                          at the till, but the register entry is the pharmacist's
                          signature.
"""

from __future__ import annotations

from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.iam.models import User


def _holds(request: Request, *codes: str) -> bool:
    user = request.user
    if not user.is_authenticated or not isinstance(user, User):
        return False
    return any(user.has_permission(code) for code in codes)


class PatientRecordAccess(BasePermission):
    """Fill them or audit them. A driver does neither."""

    message = "Patient records are limited to dispensing staff and auditors."

    def has_permission(self, request: Request, view: APIView) -> bool:
        if request.method in SAFE_METHODS:
            return _holds(request, "sale.create", "sale.dispense", "audit.view")
        return _holds(request, "sale.create", "sale.dispense")


class ControlledRegisterAccess(BasePermission):
    """The document an inspector asks for. Read by a pharmacist or an auditor."""

    message = "The controlled substances register is limited to pharmacists and auditors."

    def has_permission(self, request: Request, view: APIView) -> bool:
        if request.method in SAFE_METHODS:
            return _holds(request, "sale.dispense", "audit.view")
        # Writing the register is the pharmacist's signature — never a cashier's,
        # even though a cashier may ring the item up at the till.
        return _holds(request, "sale.dispense")
