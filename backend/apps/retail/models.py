"""Retail POS models: over-the-counter sales at a pharmacy.

A sale is built as an OPEN cart (prices snapshotted from the pharmacy's listing),
then COMPLETED when paid — which FEFO-consumes stock and writes the immutable
`SALE` ledger movements. A COMPLETED sale can be VOIDED, which reverses the stock.

Prices are VAT-inclusive (Rwanda retail / EBM convention): the tax portion of a
line is ``line_total * rate / (100 + rate)``. See docs/06-workflows-state-machines.md.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import models

# VAT rate (%) per catalog tax class. B = standard 18% VAT; A/C/D carry no VAT
# at the counter (exempt / zero-rated / special-handling).
TAX_RATES: dict[str, Decimal] = {
    "A": Decimal("0"),
    "B": Decimal("18"),
    "C": Decimal("0"),
    "D": Decimal("0"),
}

_CENTS = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


class Sale(models.Model):
    """One over-the-counter transaction at a retail pharmacy."""

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"  # a held/parked cart
        COMPLETED = "COMPLETED", "Completed"
        VOIDED = "VOIDED", "Voided"

    sale_number = models.CharField(max_length=30, unique=True, blank=True, default="")
    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.PROTECT, related_name="sales"
    )
    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    # Snapshotted at completion so the receipt stays reproducible.
    amount_tendered = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    change_due = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    void_reason = models.CharField(max_length=255, blank=True, default="")
    completed_at = models.DateTimeField(null=True, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["organization", "status"])]

    def __str__(self) -> str:
        return self.sale_number or f"SALE#{self.pk}"

    @property
    def total(self) -> Decimal:
        """VAT-inclusive grand total the customer pays."""
        return _money(sum((i.line_total for i in self.items.all()), Decimal("0")))

    @property
    def tax_total(self) -> Decimal:
        return _money(sum((i.line_tax for i in self.items.all()), Decimal("0")))

    @property
    def subtotal(self) -> Decimal:
        """Net of VAT (total − tax)."""
        return _money(self.total - self.tax_total)


class SaleItem(models.Model):
    """A cart line — product, quantity, and the price/tax snapshotted at add time."""

    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)  # VAT-inclusive snapshot
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # e.g. 18.00

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.product} ×{self.quantity}"

    @property
    def line_total(self) -> Decimal:
        return _money(self.unit_price * self.quantity)

    @property
    def line_tax(self) -> Decimal:
        rate = self.tax_rate
        if rate <= 0:
            return Decimal("0.00")
        return _money(self.line_total * rate / (Decimal("100") + rate))

    @property
    def line_net(self) -> Decimal:
        return _money(self.line_total - self.line_tax)


class SaleBatchAllocation(models.Model):
    """Which physical batch(es) a sale line was drawn from (FEFO). One SALE ledger
    movement is written per allocation; a void reverses each one."""

    sale_item = models.ForeignKey(SaleItem, on_delete=models.CASCADE, related_name="allocations")
    batch = models.ForeignKey(
        "inventory.InventoryBatch", on_delete=models.PROTECT, related_name="sale_allocations"
    )
    quantity = models.PositiveIntegerField()

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.quantity} of {self.batch}"


class Dispensing(models.Model):
    """Regulatory dispensing log for a sale containing prescription-only or
    controlled items — who the pharmacist was, the patient, and the prescriber.
    Required before such a sale can complete."""

    sale = models.OneToOneField(Sale, on_delete=models.CASCADE, related_name="dispensing")
    dispensed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    patient_name = models.CharField(max_length=150)
    patient_id_number = models.CharField(max_length=50, blank=True, default="")  # national ID
    prescriber_name = models.CharField(max_length=150)
    prescriber_license = models.CharField(max_length=100, blank=True, default="")
    prescription_reference = models.CharField(max_length=100, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Dispensing for {self.sale} → {self.patient_name}"


class Payment(models.Model):
    """A tender against a sale. Split payments = several rows (cash + momo + card)."""

    class Method(models.TextChoices):
        CASH = "CASH", "Cash"
        MOBILE_MONEY = "MOBILE_MONEY", "Mobile money"
        CARD = "CARD", "Card"

    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="payments")
    method = models.CharField(max_length=20, choices=Method.choices)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.method} {self.amount}"
