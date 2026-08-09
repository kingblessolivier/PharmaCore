"""Quality control: the decision that turns quarantined goods into sellable stock.

Under GDP, inbound goods sit in quarantine and become saleable only when a
competent person releases them. Two properties make that a control rather than a
formality, and neither survived being written inline in a view:

* **It is a state machine.** A failed check cannot be quietly re-passed, and a
  rejection has to say why. Otherwise "released" means only that somebody clicked
  the button last.
* **The person who received the goods must not be the person who releases them.**
  A single pair of eyes on both steps is exactly the failure mode the quarantine
  exists to catch — the receiver has already formed a view that the delivery was
  fine.

Release is also the only route out of quarantine for received stock, so it lives
here rather than being reachable by assigning ``batch.status`` from anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.db import transaction
from django.utils import timezone

from apps.iam.audit import record_audit
from apps.inventory.models import (
    InventoryBatch,
    QualityCheck,
    missing_batch_documents,  # noqa: F401
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from apps.iam.models import User


class QualityError(ValueError):
    """A quality-control rule was violated — surfaced as 400, never a 500."""


#: Batch states from which a QC decision can still be made. A batch that has been
#: recalled or has expired is out of QC's hands entirely.
_DECIDABLE = (InventoryBatch.Status.QUARANTINE, InventoryBatch.Status.ACTIVE)


@dataclass
class QualityOutcome:
    """What a QC decision did."""

    check: QualityCheck
    batch: InventoryBatch
    released_units: Decimal
    previous_status: str


def _assert_decidable(check: QualityCheck) -> None:
    if check.status != QualityCheck.Status.PENDING_REVIEW:
        raise QualityError(
            f"This check was already {check.get_status_display().lower()} on "
            f"{check.inspection_date:%Y-%m-%d}. Raise a new check rather than "
            "overwriting the original decision."
        )
    if check.batch.status not in _DECIDABLE:
        raise QualityError(
            f"Batch {check.batch.batch_number} is "
            f"{check.batch.get_status_display().lower()} — that is not a state QC decides."
        )


def _assert_second_pair_of_eyes(check: QualityCheck, user: User | None) -> None:
    """The inspector who raised the check may not also sign it off.

    Enforced on identity, not on role: a supervisor inspecting their own delivery
    is the same single pair of eyes as anyone else.
    """
    if user is not None and check.inspector_id == user.pk:
        raise QualityError(
            "The person who raised this check cannot also decide it. "
            "Quarantine release needs a second pair of eyes."
        )


@transaction.atomic
def release(*, check: QualityCheck, user: User | None = None, notes: str = "") -> QualityOutcome:
    """Pass QC and move the batch into saleable stock."""
    check = QualityCheck.objects.select_for_update().select_related("batch").get(pk=check.pk)
    _assert_decidable(check)
    _assert_second_pair_of_eyes(check, user)

    batch = check.batch
    previous = batch.status

    # Releasing a lot to sale is the moment its paperwork ought to exist: a
    # Certificate of Analysis is issued for a specific batch, and "we hold a GMP
    # certificate for the manufacturer" is not an answer to "show me the CoA for
    # this one" at an inspection.
    #
    # Whether a missing CoA *blocks* the release is the pharmacy's decision,
    # not ours — turning enforcement on before it has loaded any CoAs would
    # stop it releasing stock at all on its first day. So the default records
    # the gap, visibly and auditably, and `require_coa_before_release` on the
    # organization escalates that to a refusal once the paperwork has caught up.
    missing = missing_batch_documents(batch)
    if missing:
        shortfall = ", ".join(missing)
        if batch.organization.require_coa_before_release:
            raise QualityError(
                f"This lot cannot be released: {shortfall} not on file and verified. "
                "Attach the paperwork, or ask an administrator to relax the rule."
            )
        notes = (
            f"{notes} (released without: {shortfall})".strip()
            if notes
            else (f"Released without: {shortfall}")
        )

    check.status = QualityCheck.Status.PASSED
    if notes:
        check.inspection_notes = f"{check.inspection_notes}\nReleased: {notes}".strip()
    check.save(update_fields=["status", "inspection_notes"])

    batch.status = InventoryBatch.Status.ACTIVE
    batch.save(update_fields=["status", "updated_at"])

    record_audit(
        action="QC_RELEASED",
        user=user,
        organization=batch.organization,
        entity_type="quality_check",
        entity_id=str(check.pk),
        changes={
            "batch": batch.batch_number,
            "product": str(batch.product),
            "units": batch.quantity_available,
            "from_status": previous,
        },
    )
    return QualityOutcome(
        check=check,
        batch=batch,
        released_units=batch.quantity_available,
        previous_status=previous,
    )


@transaction.atomic
def reject(*, check: QualityCheck, reason: str, user: User | None = None) -> QualityOutcome:
    """Fail QC and hold the batch in quarantine.

    Rejected stock stays quarantined rather than being destroyed here — disposal
    is a separate, witnessed act with its own record.
    """
    if not reason.strip():
        raise QualityError("A rejection must say why — that reason is the audit trail.")

    check = QualityCheck.objects.select_for_update().select_related("batch").get(pk=check.pk)
    _assert_decidable(check)
    _assert_second_pair_of_eyes(check, user)

    batch = check.batch
    previous = batch.status

    check.status = QualityCheck.Status.FAILED
    check.inspection_notes = f"{check.inspection_notes}\nRejected: {reason}".strip()
    check.save(update_fields=["status", "inspection_notes"])

    batch.status = InventoryBatch.Status.QUARANTINE
    batch.save(update_fields=["status", "updated_at"])

    record_audit(
        action="QC_REJECTED",
        user=user,
        organization=batch.organization,
        entity_type="quality_check",
        entity_id=str(check.pk),
        changes={"batch": batch.batch_number, "reason": reason, "from_status": previous},
    )
    return QualityOutcome(
        check=check, batch=batch, released_units=Decimal(0), previous_status=previous
    )


def quarantine_queue(*, organization: Any) -> list[dict[str, Any]]:
    """Everything waiting on a QC decision, oldest first.

    Stock in quarantine is capital that cannot be sold and medicine that cannot be
    dispensed, so the age of the queue is the number that matters — not its size.
    """
    org_id = getattr(organization, "pk", organization)
    today = timezone.localdate()
    rows: list[dict[str, Any]] = []
    checks = (
        QualityCheck.objects.filter(
            batch__organization_id=org_id, status=QualityCheck.Status.PENDING_REVIEW
        )
        .select_related("batch", "batch__product", "inspector")
        .order_by("inspection_date")
    )
    for check in checks:
        batch = check.batch
        rows.append(
            {
                "check": check.pk,
                "batch": batch.pk,
                "batch_number": batch.batch_number,
                "product": batch.product_id,
                "product_name": str(batch.product),
                "quantity": batch.quantity_available,
                "expiry_date": batch.expiry_date,
                "days_to_expiry": (batch.expiry_date - today).days,
                "waiting_days": (timezone.now() - check.inspection_date).days,
                "raised_by": check.inspector.get_full_name() or check.inspector.username,
                "visual_integrity_ok": check.visual_integrity_ok,
                "temp_indicator_ok": check.temp_indicator_ok,
            }
        )
    return rows


def summary(*, organization: Any) -> dict[str, Any]:
    """Headline QC figures for the inventory overview."""
    queue = quarantine_queue(organization=organization)
    org_id = getattr(organization, "pk", organization)
    return {
        "pending": len(queue),
        "units_held": sum(int(r["quantity"]) for r in queue),
        "oldest_days": max((int(r["waiting_days"]) for r in queue), default=0),
        # Stock that will expire while still waiting for a decision is the worst
        # outcome available: paid for, never sellable.
        "expiring_in_quarantine": sum(1 for r in queue if int(r["days_to_expiry"]) <= 90),
        "quarantined_batches": InventoryBatch.objects.filter(
            organization_id=org_id, status=InventoryBatch.Status.QUARANTINE
        ).count(),
    }
