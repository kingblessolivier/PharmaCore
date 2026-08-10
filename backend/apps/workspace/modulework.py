"""What needs doing inside one app, so a module home is a queue and not a menu.

The audit measured one ordinary job — buy a drug from your own depot — crossing
seven screens in five nav groups, with no link from any step to the next (D14).
The dashboard now answers "what needs doing" for the whole business; this answers
it per app, so arriving at Inventory tells you *there are four batches in
quarantine waiting on you* rather than offering fourteen tables to browse.

Every entry is a **real count with a real link**. Nothing is inferred, ranked by a
heuristic, or invented to fill the space — a home screen that guesses teaches
people to stop reading it.

Entries are filtered by permission, so the queue only ever names work the person
can actually do. A cashier does not get told about quarantine releases.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any

from django.db.models import Q
from django.utils import timezone


def _entry(label: str, count: int, to: str, tone: str = "info") -> dict[str, Any] | None:
    """A queue line, or nothing at all when there is nothing to do."""
    if not count:
        return None
    return {"label": label, "count": count, "to": to, "tone": tone}


def _retail(user: Any, org_ids: list[int]) -> list[dict[str, Any] | None]:
    from apps.retail.models import DrawerSession, Prescription

    today = timezone.localdate()
    return [
        _entry(
            "till drawers still open",
            DrawerSession.objects.filter(
                organization_id__in=org_ids, status=DrawerSession.Status.OPEN
            ).count(),
            "/retail",
            "warning",
        ),
        _entry(
            "prescriptions still to collect",
            Prescription.objects.filter(
                organization_id__in=org_ids, status=Prescription.Status.ACTIVE
            ).count(),
            "/retail/prescriptions",
        ),
        _entry(
            "prescriptions expiring this week",
            Prescription.objects.filter(
                organization_id__in=org_ids,
                status=Prescription.Status.ACTIVE,
                expiry_date__lte=today + timedelta(days=7),
                expiry_date__gte=today,
            ).count(),
            "/retail/prescriptions",
            "warning",
        ),
    ]


def _inventory(user: Any, org_ids: list[int]) -> list[dict[str, Any] | None]:
    from apps.inventory.models import InventoryBatch, PickWave, QualityCheck, StockCount

    today = timezone.localdate()
    return [
        _entry(
            "batches in quarantine awaiting a decision",
            InventoryBatch.objects.filter(
                organization_id__in=org_ids, status=InventoryBatch.Status.QUARANTINE
            ).count(),
            "/inventory/qc",
            "warning",
        ),
        _entry(
            "expired batches still on the shelf",
            InventoryBatch.objects.filter(
                organization_id__in=org_ids, expiry_date__lt=today, quantity_available__gt=0
            ).count(),
            "/inventory/disposal",
            "danger",
        ),
        _entry(
            "quality checks awaiting review",
            # QualityCheck carries no organization of its own — it hangs off the batch.
            QualityCheck.objects.filter(
                batch__organization_id__in=org_ids, status=QualityCheck.Status.PENDING_REVIEW
            ).count(),
            "/inventory/qc",
            "warning",
        ),
        _entry(
            "stock counts submitted for approval",
            StockCount.objects.filter(
                organization_id__in=org_ids, status=StockCount.Status.SUBMITTED
            ).count(),
            "/inventory/counts",
        ),
        _entry(
            "pick waves released and not yet picked",
            PickWave.objects.filter(
                organization_id__in=org_ids,
                status__in=[PickWave.Status.RELEASED, PickWave.Status.PICKING],
            ).count(),
            "/inventory/picking",
        ),
    ]


def _distribution(user: Any, org_ids: list[int]) -> list[dict[str, Any] | None]:
    from apps.distribution.models import BackorderLine, CustomerReturn, StockOrder

    return [
        # Counted as orders, so it links to orders. It used to point at
        # /approvals — the central inbox, which lists ApprovalRequest records.
        # A B2B stock order awaiting its depot is not one of those, so the tile
        # said "1 order waiting" and the screen it opened showed a different
        # queue entirely, of a different length.
        _entry(
            "orders waiting for your approval",
            StockOrder.objects.filter(
                depot_id__in=org_ids, status=StockOrder.Status.PENDING
            ).count(),
            "/distribution/orders?status=PENDING",
            "warning",
        ),
        # Also orders, for the same reason. /distribution/in-transit lists the
        # batches physically on the lorry (InTransitStock); an order can be in
        # transit while that table is empty, which is how "1 delivery on the
        # road" opened a page showing none.
        _entry(
            "deliveries on the road to you",
            StockOrder.objects.filter(
                retail_id__in=org_ids, status=StockOrder.Status.IN_TRANSIT
            ).count(),
            "/distribution/orders?status=IN_TRANSIT",
        ),
        _entry(
            "unmet demand you could source",
            BackorderLine.objects.filter(
                Q(depot_id__in=org_ids) | Q(retail_id__in=org_ids),
                status=BackorderLine.Status.OPEN,
            ).count(),
            "/distribution/demand",
            "warning",
        ),
        _entry(
            "customer returns awaiting inspection",
            CustomerReturn.objects.filter(
                depot_id__in=org_ids,
                status__in=[CustomerReturn.Status.REQUESTED, CustomerReturn.Status.INSPECTING],
            ).count(),
            "/distribution/returns",
        ),
    ]


def _procurement(user: Any, org_ids: list[int]) -> list[dict[str, Any] | None]:
    from apps.procurement.models import (
        GoodsReceipt,
        PurchaseOrder,
        PurchaseRequisition,
        SupplierInvoice,
    )

    return [
        _entry(
            "requisitions submitted for approval",
            PurchaseRequisition.objects.filter(
                organization_id__in=org_ids, status=PurchaseRequisition.Status.SUBMITTED
            ).count(),
            "/procurement/requisitions",
            "warning",
        ),
        _entry(
            "purchase orders awaiting approval",
            PurchaseOrder.objects.filter(
                organization_id__in=org_ids, status=PurchaseOrder.Status.PENDING_APPROVAL
            ).count(),
            "/procurement/orders",
            "warning",
        ),
        _entry(
            "goods receipts still in draft",
            GoodsReceipt.objects.filter(
                organization_id__in=org_ids, status=GoodsReceipt.Status.DRAFT
            ).count(),
            "/procurement/receipts",
        ),
        _entry(
            "supplier invoices with a price or quantity variance",
            SupplierInvoice.objects.filter(
                organization_id__in=org_ids, status=SupplierInvoice.Status.VARIANCE
            ).count(),
            "/procurement/invoices",
            "danger",
        ),
    ]


def _insurance(user: Any, org_ids: list[int]) -> list[dict[str, Any] | None]:
    from apps.insurance.models import Claim, RemittanceAdvice

    return [
        _entry(
            "claims still in draft",
            Claim.objects.filter(organization_id__in=org_ids, status=Claim.Status.DRAFT).count(),
            "/insurance/claims",
            "warning",
        ),
        _entry(
            "claims rejected and not yet reworked",
            Claim.objects.filter(organization_id__in=org_ids, status=Claim.Status.REJECTED).count(),
            "/insurance/claims",
            "danger",
        ),
        _entry(
            "remittances to post",
            RemittanceAdvice.objects.filter(
                organization_id__in=org_ids, status=RemittanceAdvice.Status.DRAFT
            ).count(),
            "/insurance/remittances",
        ),
    ]


def _finance(user: Any, org_ids: list[int]) -> list[dict[str, Any] | None]:
    from apps.finance.models import AccountingPeriod, CustomerInvoice, SupplierBill

    today = timezone.localdate()
    return [
        _entry(
            "customer invoices past due",
            CustomerInvoice.objects.filter(
                organization_id__in=org_ids,
                status__in=[CustomerInvoice.Status.OPEN, CustomerInvoice.Status.PARTIAL],
                due_date__lt=today,
            ).count(),
            "/finance/aging",
            "danger",
        ),
        _entry(
            "supplier bills due",
            SupplierBill.objects.filter(
                organization_id__in=org_ids,
                status__in=[SupplierBill.Status.UNPAID, SupplierBill.Status.PARTIAL],
                due_date__lte=today,
            ).count(),
            "/finance/payables",
            "warning",
        ),
        _entry(
            "periods still open past their end date",
            AccountingPeriod.objects.filter(
                organization_id__in=org_ids,
                status=AccountingPeriod.Status.OPEN,
                end_date__lt=today,
            ).count(),
            "/finance/statements",
            "warning",
        ),
    ]


def _people(user: Any, org_ids: list[int]) -> list[dict[str, Any] | None]:
    from apps.hr.models import LeaveRequest

    return [
        _entry(
            "leave requests awaiting a decision",
            # LeaveRequest carries no organization — it hangs off the employee.
            LeaveRequest.objects.filter(
                employee__organization_id__in=org_ids, status=LeaveRequest.Status.PENDING
            ).count(),
            "/people/leave",
            "warning",
        ),
    ]


def _admin(user: Any, org_ids: list[int]) -> list[dict[str, Any] | None]:
    from apps.iam.models import License

    today = timezone.localdate()
    return [
        _entry(
            "licences expiring within 60 days",
            License.objects.filter(
                organization_id__in=org_ids,
                expiry_date__isnull=False,
                expiry_date__gte=today,
                expiry_date__lte=today + timedelta(days=60),
            ).count(),
            "/companies",
            "warning",
        ),
        _entry(
            "licences already expired",
            License.objects.filter(organization_id__in=org_ids, expiry_date__lt=today).count(),
            "/companies",
            "danger",
        ),
    ]


#: module -> (permission that makes this queue relevant, builder)
_MODULES: dict[str, tuple[str, Callable[[Any, list[int]], list[dict[str, Any] | None]]]] = {
    "retail": ("sale.create", _retail),
    "inventory": ("inventory.view", _inventory),
    "distribution": ("distribution.view", _distribution),
    "procurement": ("procurement.view", _procurement),
    "insurance": ("insurance.view", _insurance),
    "finance": ("finance.view", _finance),
    "people": ("employee.view", _people),
    "admin": ("organization.manage", _admin),
}


def queues_for(user: Any, module: str | None = None) -> dict[str, list[dict[str, Any]]]:
    """Work queues, keyed by module, filtered to what this person may act on."""
    from apps.iam.scoping import organizations_visible_to

    org_ids = list(organizations_visible_to(user).values_list("id", flat=True))
    wanted = [module] if module else list(_MODULES)
    out: dict[str, list[dict[str, Any]]] = {}
    for name in wanted:
        entry = _MODULES.get(name)
        if entry is None:
            continue
        permission, build = entry
        if not user.has_permission(permission):
            continue
        out[name] = [row for row in build(user, org_ids) if row is not None]
    return out
