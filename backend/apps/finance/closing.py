"""The month-end close checklist.

Closing a period already refused to proceed on an unbalanced trial balance, which
is the right instinct but a low bar — a set of books can balance perfectly and
still be wrong, because balancing only proves the double entry was arithmetically
consistent, not that anything real was recorded.

What actually makes a pharmacy's month-end trustworthy is the list below: the
stock count happened, the bank was reconciled, expiring stock was provided for,
depreciation was charged, payroll was posted, VAT was computed. Each is a task
that can be done, or waived with a reason, and a blocking task that is neither
stops the close.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.iam.models import User

from .models import AccountingPeriod, PeriodTask


@dataclass(frozen=True)
class TaskSpec:
    code: str
    title: str
    description: str
    sequence: int
    is_blocking: bool = True


# The order is the order an accountant actually works in: get the physical facts
# in first, then the accruals that depend on them, then the statements.
DEFAULT_CLOSE_TASKS: tuple[TaskSpec, ...] = (
    TaskSpec(
        code="CUTOFF",
        title="Confirm document cut-off",
        description=(
            "Every goods receipt, sale and supplier invoice dated in the period is "
            "entered, and nothing from the next period has been posted early."
        ),
        sequence=10,
    ),
    TaskSpec(
        code="STOCK_COUNT",
        title="Stock count posted",
        description="Physical count completed and the variance posted to the ledger.",
        sequence=20,
    ),
    TaskSpec(
        code="EXPIRY_PROVISION",
        title="Expiry & slow-moving provision reviewed",
        description=(
            "Stock that will not sell before it expires is written down under IAS 2 "
            "— it is not an asset just because it is on the shelf."
        ),
        sequence=30,
    ),
    TaskSpec(
        code="BANK_REC",
        title="Bank, MoMo and cash reconciled",
        description=(
            "Every bank, mobile-money and till account agreed to its statement, with "
            "charges and interest posted."
        ),
        sequence=40,
    ),
    TaskSpec(
        code="TILL_VARIANCE",
        title="Till over/short cleared",
        description="Drawer sessions closed and any cash variance posted.",
        sequence=45,
    ),
    TaskSpec(
        code="AR_REVIEW",
        title="Receivables reviewed",
        description="Aging reviewed, credit notes raised, bad debts identified.",
        sequence=50,
    ),
    TaskSpec(
        code="AP_REVIEW",
        title="Payables & GRNI reviewed",
        description=(
            "Goods received not invoiced cleared down — a stale GRNI balance is stock "
            "you have taken in and never been billed for."
        ),
        sequence=60,
    ),
    TaskSpec(
        code="PAYROLL",
        title="Payroll posted",
        description="Payroll run posted with employer contributions and statutory deductions.",
        sequence=70,
    ),
    TaskSpec(
        code="DEPRECIATION",
        title="Depreciation charged",
        description="Monthly depreciation posted for every active fixed asset.",
        sequence=80,
    ),
    TaskSpec(
        code="ACCRUALS",
        title="Accruals & prepayments posted",
        description="Rent, insurance, utilities and anything else straddling the period end.",
        sequence=90,
    ),
    TaskSpec(
        code="VAT",
        title="VAT return prepared",
        description="Output less input VAT computed and agreed to the control accounts.",
        sequence=100,
    ),
    TaskSpec(
        code="TB_REVIEW",
        title="Trial balance reviewed",
        description="Balances scanned for anything on the wrong side or obviously stale.",
        sequence=110,
    ),
    TaskSpec(
        code="STATEMENTS",
        title="Statements reviewed",
        description="P&L, balance sheet and cash flow read and understood before signing off.",
        # Advisory: reviewing the statements is judgement, and a close should not
        # be held hostage to a checkbox that only the reviewer can tick.
        sequence=120,
        is_blocking=False,
    ),
)


@transaction.atomic
def seed_period_tasks(period: AccountingPeriod) -> list[PeriodTask]:
    """Create any missing checklist items for a period. Idempotent."""
    existing = set(period.tasks.values_list("code", flat=True))
    created = [
        PeriodTask.objects.create(
            period=period,
            code=spec.code,
            title=spec.title,
            description=spec.description,
            sequence=spec.sequence,
            is_blocking=spec.is_blocking,
        )
        for spec in DEFAULT_CLOSE_TASKS
        if spec.code not in existing
    ]
    return created


def close_readiness(period: AccountingPeriod) -> dict[str, Any]:
    """What still stands between this period and a defensible close."""
    tasks = list(period.tasks.all())
    outstanding = [t for t in tasks if not t.is_settled]
    blocking = [t for t in outstanding if t.is_blocking]
    done = len([t for t in tasks if t.status == PeriodTask.Status.DONE])
    waived = len([t for t in tasks if t.status == PeriodTask.Status.WAIVED])
    return {
        "period_id": period.pk,
        "total": len(tasks),
        "done": done,
        "waived": waived,
        "outstanding": len(outstanding),
        "blocking": [{"code": t.code, "title": t.title} for t in blocking],
        "is_ready": not blocking,
        "completion_pct": round((done + waived) / len(tasks) * 100) if tasks else 0,
    }


class CloseBlocked(Exception):
    """Raised when a blocking checklist item is still outstanding."""


def assert_period_closable(period: AccountingPeriod) -> None:
    """Refuse the close while a blocking task is outstanding.

    A period with no checklist at all is allowed through: the checklist is a
    control that was added later, and retro-blocking historical closes would be
    an obstacle rather than a safeguard.
    """
    readiness = close_readiness(period)
    if readiness["total"] == 0:
        return
    if not readiness["is_ready"]:
        titles = ", ".join(t["title"] for t in readiness["blocking"])
        raise CloseBlocked(f"Close is blocked by outstanding checklist items: {titles}.")


@transaction.atomic
def settle_task(task: PeriodTask, *, status: str, user: User | None, notes: str = "") -> PeriodTask:
    """Mark a checklist item done or waived.

    A waiver must carry a reason. "Waived" without one is indistinguishable from
    "skipped", and the whole point of allowing a waiver is that it stays visible.
    """
    if status not in {PeriodTask.Status.DONE, PeriodTask.Status.WAIVED}:
        raise ValueError("A task can only be marked DONE or WAIVED.")
    if status == PeriodTask.Status.WAIVED and not notes.strip():
        raise ValueError("Waiving a checklist item requires a reason.")
    task.status = status
    task.completed_by = user
    task.completed_at = timezone.now()
    if notes:
        task.notes = notes
    task.save(update_fields=["status", "completed_by", "completed_at", "notes"])
    return task
