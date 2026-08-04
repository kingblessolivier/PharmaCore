"""Inventory service functions — the write-path that keeps batches and the
immutable movement ledger consistent (one DB transaction each)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db import transaction

from apps.catalog.models import Product
from apps.iam.models import Organization, User
from apps.inventory.models import InventoryBatch, PharmacyProduct, StockMovement


@transaction.atomic
def receive_intake(
    *,
    organization: Organization,
    product: Product,
    batch_number: str,
    expiry_date: date,
    quantity: int,
    manufacture_date: date | None = None,
    wholesale_cost: Decimal | None = None,
    storage_location: str = "",
    user: User | None = None,
    movement_type: str = StockMovement.Type.INTAKE,
    reference_type: str = "intake",
    reference_id: str = "",
) -> InventoryBatch:
    """Receive stock into an org: create/find the batch, add quantity, and append a
    movement (INTAKE by default; TRANSFER_IN for a GRN). One transaction."""
    batch, created = InventoryBatch.objects.select_for_update().get_or_create(
        organization=organization,
        product=product,
        batch_number=batch_number,
        defaults={
            "expiry_date": expiry_date,
            "manufacture_date": manufacture_date,
            "wholesale_cost": wholesale_cost,
            "storage_location": storage_location,
        },
    )
    batch.quantity_available += quantity
    if wholesale_cost is not None:
        batch.wholesale_cost = wholesale_cost
    batch.save(update_fields=["quantity_available", "wholesale_cost", "updated_at"])

    # Any stock received into an org lists the product in that org's catalog (prices
    # left blank for staff to set). This is why a retail pharmacy never re-adds
    # transferred stock — it appears in their catalog ready to price.
    PharmacyProduct.objects.get_or_create(
        organization=organization, product=product, defaults={"is_active": True}
    )

    StockMovement.objects.create(
        organization=organization,
        product=product,
        batch=batch,
        batch_number=batch_number,
        movement_type=movement_type,
        quantity_delta=quantity,
        reference_type=reference_type,
        reference_id=reference_id,
        created_by=user,
    )
    return batch


def _movement(
    batch: InventoryBatch, mtype: str, delta: int, reason: str, user: User | None
) -> None:
    StockMovement.objects.create(
        organization=batch.organization,
        product=batch.product,
        batch=batch,
        batch_number=batch.batch_number,
        movement_type=mtype,
        quantity_delta=delta,
        reference_type=mtype.lower(),
        reason=reason,
        created_by=user,
    )


@transaction.atomic
def adjust_stock(
    *, batch: InventoryBatch, counted_quantity: int, reason: str = "", user: User | None = None
) -> InventoryBatch:
    """Correct a batch to a physically-counted quantity, logging the signed delta."""
    if counted_quantity < 0:
        raise ValueError("Counted quantity cannot be negative.")
    delta = counted_quantity - batch.quantity_available
    batch.quantity_available = counted_quantity
    batch.save(update_fields=["quantity_available", "updated_at"])
    _movement(batch, StockMovement.Type.ADJUSTMENT, delta, reason, user)
    return batch


@transaction.atomic
def log_wastage(
    *, batch: InventoryBatch, quantity: int, reason: str = "", user: User | None = None
) -> InventoryBatch:
    """Remove expired/damaged stock from a batch (never below zero)."""
    if quantity <= 0:
        raise ValueError("Wastage quantity must be positive.")
    if quantity > batch.quantity_available:
        raise ValueError("Cannot waste more than is on hand.")
    batch.quantity_available -= quantity
    batch.save(update_fields=["quantity_available", "updated_at"])
    _movement(batch, StockMovement.Type.WASTAGE, -quantity, reason, user)
    return batch
