"""Raise operational alert notifications — run on a schedule (e.g. daily).

Summarises, per organization: overdue payables, stock expiring within 30 days,
expired stock still on hand, and products below their minimum level. One
notification per alert type per org (deduped against unread) so it never spams.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.utils import timezone

from apps.distribution.models import StockOrder
from apps.iam.models import Organization
from apps.inventory.models import InventoryBatch, PharmacyProduct
from apps.workspace.notify import notify_org_admins


class Command(BaseCommand):
    help = "Raise operational alerts (overdue payables, expiry, low stock) as notifications."

    def handle(self, *args: Any, **options: Any) -> None:
        today = timezone.now().date()
        soon = today + timedelta(days=30)
        made = 0

        # Overdue payables — per buying org.
        overdue: dict[int, int] = {}
        for o in (
            StockOrder.objects.filter(payment_due_date__lt=today)
            .exclude(payment_status=StockOrder.PaymentStatus.PAID)
            .prefetch_related("items")
        ):
            if o.amount_due > 0:
                overdue[o.retail_id] = overdue.get(o.retail_id, 0) + 1
        for org_id, count in overdue.items():
            org = Organization.objects.get(pk=org_id)
            made += notify_org_admins(
                organization=org,
                title=f"{count} supplier payment(s) overdue",
                body="Settle to keep good standing with your wholesalers.",
                link_entity_type="orders",
                dedupe=True,
            )

        # Stock alerts — per organization.
        for org in Organization.objects.filter(is_active=True):
            expiring = InventoryBatch.objects.filter(
                organization=org,
                status=InventoryBatch.Status.ACTIVE,
                expiry_date__gte=today,
                expiry_date__lte=soon,
                quantity_available__gt=0,
            ).count()
            if expiring:
                made += notify_org_admins(
                    organization=org,
                    title=f"{expiring} batch(es) expiring within 30 days",
                    body="Review and prioritise or write off.",
                    link_entity_type="dashboard",
                    dedupe=True,
                )
            expired = InventoryBatch.objects.filter(
                organization=org, expiry_date__lt=today, quantity_available__gt=0
            ).count()
            if expired:
                made += notify_org_admins(
                    organization=org,
                    title=f"{expired} expired batch(es) still on hand",
                    body="Quarantine and write off — they cannot be sold.",
                    link_entity_type="dashboard",
                    dedupe=True,
                )
            # Low stock: sellable on-hand below the listing minimum.
            low = 0
            on_hand = {
                r["product_id"]: r["q"]
                for r in InventoryBatch.objects.filter(
                    organization=org,
                    status=InventoryBatch.Status.ACTIVE,
                    expiry_date__gte=today,
                )
                .values("product_id")
                .annotate(q=Sum("quantity_available"))
            }
            for pp in PharmacyProduct.objects.filter(
                organization=org, is_active=True, min_stock_level__gt=0
            ):
                if on_hand.get(pp.product_id, 0) < pp.min_stock_level:
                    low += 1
            if low:
                made += notify_org_admins(
                    organization=org,
                    title=f"{low} product(s) below minimum — reorder",
                    link_entity_type="dashboard",
                    dedupe=True,
                )

        self.stdout.write(self.style.SUCCESS(f"notify_alerts: {made} notification(s) created"))
