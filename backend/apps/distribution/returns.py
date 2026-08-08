"""Customer returns: inspect, restock, credit.

A return is three separate facts that were previously collapsed into one typed
number. Goods came back; some of them were fit to resell; the buyer is owed money
for those. This module keeps them separate, because the common failure is to
credit a retailer for stock that was never fit to put back on the shelf.

Rejected units are recorded and never restocked — expired, damaged or
cold-chain-broken goods that re-enter saleable stock are a patient-safety problem,
not an inventory discrepancy.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.db import transaction
from django.utils import timezone

from apps.distribution.models import CustomerReturn, CustomerReturnLine
from apps.documents.models import DocType, Document
from apps.documents.services import generate_document
from apps.inventory.models import StockMovement
from apps.inventory.services import receive_intake

if TYPE_CHECKING:  # pragma: no cover - typing only
    from apps.iam.models import User

ZERO = Decimal("0.00")


class ReturnError(Exception):
    """Raised when a return cannot be processed as asked."""


def _product_label(product: object) -> str:
    return f"{product.generic_name} {product.strength}".strip()  # type: ignore[attr-defined]


@dataclass
class ReturnOutcome:
    """What actually happened when a return was approved."""

    return_request: CustomerReturn
    restocked_units: int
    rejected_units: int
    credit_amount: Decimal
    credit_note: Document | None


@transaction.atomic
def start_inspection(*, return_request: CustomerReturn, user: User | None = None) -> CustomerReturn:
    """Move a requested return into inspection at the depot."""
    if return_request.status != CustomerReturn.Status.REQUESTED:
        raise ReturnError(
            f"Only a requested return can be inspected (this one is "
            f"{return_request.get_status_display().lower()})."
        )
    if not return_request.lines.exists():
        raise ReturnError("A return must list what is being sent back before it can be inspected.")
    return_request.status = CustomerReturn.Status.INSPECTING
    return_request.save(update_fields=["status"])
    return return_request


@transaction.atomic
def record_inspection(
    *,
    line: CustomerReturnLine,
    quantity_accepted: int,
    quantity_rejected: int,
    note: str = "",
) -> CustomerReturnLine:
    """Record the depot's verdict on one returned line.

    Accepted plus rejected must equal what came back. Anything else means units
    are unaccounted for, and an unaccounted-for unit of medicine is exactly what
    an inspection exists to prevent.
    """
    if quantity_accepted < 0 or quantity_rejected < 0:
        raise ReturnError("Inspected quantities cannot be negative.")
    total = quantity_accepted + quantity_rejected
    if total != line.quantity_returned:
        raise ReturnError(
            f"{line.quantity_returned} unit(s) came back but {total} were accounted for "
            f"({quantity_accepted} accepted, {quantity_rejected} rejected)."
        )
    line.quantity_accepted = quantity_accepted
    line.quantity_rejected = quantity_rejected
    line.inspection_note = note[:255]
    line.save(update_fields=["quantity_accepted", "quantity_rejected", "inspection_note"])
    return line


@transaction.atomic
def approve_return(*, return_request: CustomerReturn, user: User | None = None) -> ReturnOutcome:
    """Restock what was accepted, credit it, and issue the credit note.

    Idempotent per line: a line that already carries ``restocked_batch`` is not
    restocked again, so a second approval cannot duplicate stock.
    """
    if return_request.status == CustomerReturn.Status.APPROVED:
        raise ReturnError("This return has already been approved.")
    if return_request.status == CustomerReturn.Status.REJECTED:
        raise ReturnError("A rejected return cannot be approved.")

    lines = list(return_request.lines.select_related("product"))
    if not lines:
        raise ReturnError("There is nothing to approve — this return has no lines.")

    inspected = [ln for ln in lines if ln.quantity_accepted or ln.quantity_rejected]
    if len(inspected) != len(lines):
        raise ReturnError(
            "Every line must be inspected before the return is approved — "
            f"{len(lines) - len(inspected)} still outstanding."
        )

    restocked = 0
    rejected = 0
    credit = ZERO
    today = timezone.localdate()

    for line in lines:
        rejected += line.quantity_rejected
        credit += line.credit_amount

        if line.quantity_accepted <= 0 or line.restocked_batch_id is not None:
            continue

        # Goods with no usable expiry cannot go back into a FEFO pool — there is
        # no correct place to put them.
        if line.expiry_date is None:
            raise ReturnError(f"'{line.product}' cannot be restocked without an expiry date.")
        if line.expiry_date < today:
            raise ReturnError(
                f"'{line.product}' expired on {line.expiry_date} and cannot be restocked. "
                "Reject the line instead."
            )

        batch = receive_intake(
            organization=return_request.depot,
            product=line.product,
            batch_number=line.batch_number or f"RET-{return_request.return_number}",
            expiry_date=line.expiry_date,
            quantity=line.quantity_accepted,
            user=user,
            movement_type=StockMovement.Type.RETURN,
            reference_type="customer_return",
            reference_id=str(return_request.pk),
            source_org=return_request.retail,
        )
        line.restocked_batch = batch
        line.save(update_fields=["restocked_batch"])
        restocked += line.quantity_accepted

    return_request.credit_note_amount = credit
    return_request.status = CustomerReturn.Status.APPROVED
    return_request.save(update_fields=["credit_note_amount", "status"])

    note = _issue_credit_note(return_request=return_request, lines=lines, user=user)

    return ReturnOutcome(
        return_request=return_request,
        restocked_units=restocked,
        rejected_units=rejected,
        credit_amount=credit,
        credit_note=note,
    )


def _issue_credit_note(
    *, return_request: CustomerReturn, lines: list[CustomerReturnLine], user: User | None
) -> Document | None:
    """Issue the depot's credit note for the accepted units.

    Reused rather than reissued: the credit note *is* the record of this return, so
    approving twice must not burn a second number out of a gapless sequence.
    """
    credited = [ln for ln in lines if ln.quantity_accepted > 0]
    if not credited:
        return None
    return generate_document(
        organization=return_request.depot,
        doc_type=DocType.CREDIT_NOTE,
        context={
            "seller_name": return_request.depot.name,
            "buyer_name": return_request.retail.name,
            "reference": return_request.return_number,
            "reason": return_request.reason,
            "total": float(return_request.credit_note_amount),
            "lines": [
                {
                    "name": _product_label(ln.product),
                    "batch": ln.batch_number,
                    "qty": ln.quantity_accepted,
                    "price": ln.unit_price,
                    "amount": float(ln.credit_amount),
                }
                for ln in credited
            ],
        },
        reference_type="customer_return",
        reference_id=str(return_request.pk),
        user=user,
        reuse_existing=True,
    )


@transaction.atomic
def reject_return(
    *, return_request: CustomerReturn, reason: str, user: User | None = None
) -> CustomerReturn:
    """Refuse the whole return. Nothing is restocked and nothing is credited."""
    if return_request.status == CustomerReturn.Status.APPROVED:
        raise ReturnError("An approved return cannot be rejected — raise a debit note instead.")
    if not reason.strip():
        raise ReturnError("A rejection must say why.")
    return_request.status = CustomerReturn.Status.REJECTED
    return_request.credit_note_amount = ZERO
    return_request.reason = (
        f"{return_request.reason}\nRejected: {reason}".strip()
        if return_request.reason
        else f"Rejected: {reason}"
    )
    return_request.save(update_fields=["status", "credit_note_amount", "reason"])
    return return_request


def summary(*, depot: Any) -> dict[str, object]:
    """Returns activity for the distribution overview."""
    depot_id = depot if isinstance(depot, int) else int(depot.pk)
    qs = CustomerReturn.objects.filter(depot_id=depot_id)
    awaiting = qs.filter(
        status__in=[CustomerReturn.Status.REQUESTED, CustomerReturn.Status.INSPECTING]
    ).count()
    approved = qs.filter(status=CustomerReturn.Status.APPROVED)
    credited = sum((r.credit_note_amount for r in approved), ZERO)
    return {
        "awaiting_inspection": awaiting,
        "approved": approved.count(),
        "rejected": qs.filter(status=CustomerReturn.Status.REJECTED).count(),
        "credited_amount": float(credited),
    }
