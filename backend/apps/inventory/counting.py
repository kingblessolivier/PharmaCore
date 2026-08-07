"""Physical stock counts: reconciling what the books say with what is on the shelf.

Approving a count does two irreversible things at once — it moves stock and it
posts to the ledger. Both were reachable twice. There was no guard on the count's
status, so a double-click, a retry after a timeout, or two people approving the
same submitted count would adjust the stock twice and post the variance twice,
leaving inventory and the P&L both wrong by exactly the variance.

The second control is who may approve. A count is a check on the person who
counted; letting them sign off their own is the one arrangement that guarantees
the check finds nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.db import transaction
from django.utils import timezone

from apps.iam.audit import record_audit
from apps.inventory.models import StockCount
from apps.inventory.services import adjust_stock

if TYPE_CHECKING:  # pragma: no cover - typing only
    from apps.iam.models import User


class CountError(ValueError):
    """A stock count cannot be approved as asked."""


@dataclass
class CountOutcome:
    """What approving a count changed."""

    count: StockCount
    lines_adjusted: int
    units_gained: int
    units_lost: int
    net_value: Decimal


@transaction.atomic
def approve(*, count: StockCount, user: User | None = None) -> CountOutcome:
    """Post a count's variances to stock and to the ledger, exactly once."""
    from apps.finance.services import post_inventory_adjustment

    count = StockCount.objects.select_for_update().get(pk=count.pk)

    # The guard that was missing. Without it the same variance posts twice.
    if count.status == StockCount.Status.APPROVED:
        raise CountError(
            f"Count {count.reference_no} was already approved on "
            f"{count.completed_at:%Y-%m-%d}. Approving again would post its variances a "
            "second time, to both stock and the ledger."
        )

    if user is not None and count.counter_user_id == user.pk:
        raise CountError(
            "The person who counted cannot approve their own count — that is the "
            "control a count exists to provide."
        )

    items = list(count.items.select_for_update().select_related("batch", "batch__product"))
    if not items:
        raise CountError("This count has no lines to reconcile.")

    adjusted = 0
    gained = 0
    lost = 0
    net_value = Decimal("0.00")

    for item in items:
        if item.variance_qty == 0:
            continue
        adjust_stock(
            batch=item.batch,
            counted_quantity=item.counted_qty,
            reason=f"Stock count variance ({count.reference_no})",
            user=user,
        )
        post_inventory_adjustment(
            batch=item.batch,
            delta=item.variance_qty,
            unit_cost=item.batch.wholesale_cost,
            reason=f"Stock count {count.reference_no}",
            reference_type="stock_count",
            reference_id=str(count.pk),
            user=user,
        )
        unit_cost = item.batch.wholesale_cost or Decimal("0")
        net_value += (unit_cost * item.variance_qty).quantize(Decimal("0.01"))
        adjusted += 1
        if item.variance_qty > 0:
            gained += item.variance_qty
        else:
            lost += -item.variance_qty

    count.status = StockCount.Status.APPROVED
    count.approver_user = user
    count.completed_at = timezone.now()
    count.save(update_fields=["status", "approver_user", "completed_at"])

    record_audit(
        action="STOCK_COUNT_APPROVED",
        user=user,
        organization=count.organization,
        entity_type="stock_count",
        entity_id=str(count.pk),
        changes={
            "reference_no": count.reference_no,
            "lines_adjusted": adjusted,
            "units_gained": gained,
            "units_lost": lost,
            "net_value": str(net_value),
        },
    )
    return CountOutcome(
        count=count,
        lines_adjusted=adjusted,
        units_gained=gained,
        units_lost=lost,
        net_value=net_value,
    )


def variance_report(*, count: StockCount) -> dict[str, Any]:
    """What this count found, before anyone commits it.

    Shown ahead of approval because approving is irreversible: the reviewer needs
    to see the size and direction of what they are about to post.
    """
    rows: list[dict[str, Any]] = []
    gained = lost = 0
    net_value = Decimal("0.00")
    for item in count.items.select_related("batch", "batch__product"):
        unit_cost = item.batch.wholesale_cost or Decimal("0")
        value = (unit_cost * item.variance_qty).quantize(Decimal("0.01"))
        net_value += value
        if item.variance_qty > 0:
            gained += item.variance_qty
        elif item.variance_qty < 0:
            lost += -item.variance_qty
        rows.append(
            {
                "item": item.pk,
                "batch": item.batch_id,
                "batch_number": item.batch.batch_number,
                "product_name": str(item.batch.product),
                "system_qty": item.system_qty,
                "counted_qty": item.counted_qty,
                "variance_qty": item.variance_qty,
                "variance_value": str(value),
                "variance_reason": item.variance_reason,
            }
        )
    rows.sort(key=lambda r: abs(int(r["variance_qty"])), reverse=True)
    return {
        "count": count.pk,
        "reference_no": count.reference_no,
        "status": count.status,
        "lines": len(rows),
        "lines_with_variance": sum(1 for r in rows if r["variance_qty"] != 0),
        "units_gained": gained,
        "units_lost": lost,
        "net_value": str(net_value),
        "accuracy_pct": (
            round((1 - (sum(1 for r in rows if r["variance_qty"] != 0) / len(rows))) * 100, 1)
            if rows
            else 100.0
        ),
        "rows": rows,
    }
