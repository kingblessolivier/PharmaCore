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
    # The till session this sale rang up in (set when a drawer is open) — lets the
    # cash-up reconcile physical cash against what the register expects.
    drawer_session = models.ForeignKey(
        "retail.DrawerSession",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sales",
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
    returned_quantity = models.PositiveIntegerField(default=0)  # units given back by the customer
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)  # VAT-inclusive snapshot
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # e.g. 18.00

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.product} ×{self.quantity}"

    @property
    def returnable(self) -> int:
        return self.quantity - self.returned_quantity

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


class SaleReturn(models.Model):
    """A customer return against a completed sale — some or all items come back.

    Stock goes back onto the shelf (a RETURN ledger movement) and the customer is
    refunded; a credit note is issued. A sale can have several partial returns."""

    return_number = models.CharField(max_length=30, unique=True, blank=True, default="")
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="returns")
    reason = models.CharField(max_length=255, blank=True, default="")
    refund_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.return_number or f"RET#{self.pk}"


class SaleReturnItem(models.Model):
    sale_return = models.ForeignKey(SaleReturn, on_delete=models.CASCADE, related_name="items")
    sale_item = models.ForeignKey(SaleItem, on_delete=models.PROTECT, related_name="return_items")
    quantity = models.PositiveIntegerField()
    refund_amount = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.quantity}× {self.sale_item.product}"


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


class DrawerSession(models.Model):
    """A cash-drawer / till session for one cashier at one pharmacy.

    Opened with a **float** (starting cash). Sales rung up while it's open link to
    it. At **close** the cashier counts the cash; the register reconciles it against
    the **expected** cash (opening float + cash taken − change given − cash refunds)
    and records the **over/short**. At most one open drawer per cashier per org.
    """

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        CLOSED = "CLOSED", "Closed"

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.PROTECT, related_name="drawer_sessions"
    )
    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    opening_float = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    counted_cash = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    expected_cash = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    over_short = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True, default="")
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["-opened_at"]
        indexes = [models.Index(fields=["organization", "status"])]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "cashier"],
                condition=models.Q(status="OPEN"),
                name="one_open_drawer_per_cashier",
            )
        ]

    def __str__(self) -> str:
        return f"Drawer #{self.pk} · {self.get_status_display()}"


class Prescription(models.Model):
    """Prescription lifecycle & refill management. ROADMAP '6. Retail (POS)'."""

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        FULFILLED = "FULFILLED", "Fulfilled"
        EXPIRED = "EXPIRED", "Expired"
        CANCELLED = "CANCELLED", "Cancelled"

    prescription_number = models.CharField(max_length=50, unique=True)
    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="prescriptions"
    )
    patient_name = models.CharField(max_length=150)
    patient_id_number = models.CharField(max_length=50, blank=True, default="")
    patient_phone = models.CharField(max_length=20, blank=True, default="")
    prescriber_name = models.CharField(max_length=150)
    prescriber_license = models.CharField(max_length=100, blank=True, default="")
    issue_date = models.DateField()
    expiry_date = models.DateField()
    refills_allowed = models.PositiveIntegerField(default=1)
    refills_used = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Rx #{self.prescription_number} · {self.patient_name}"

    @property
    def remaining_refills(self) -> int:
        return max(0, self.refills_allowed - self.refills_used)


class ControlledSubstanceRegister(models.Model):
    """Statutory controlled drug logbook & audit trail. ROADMAP '6. Retail (POS)'."""

    class MovementType(models.TextChoices):
        RECEIPT = "RECEIPT", "Receipt from Supplier/Depot"
        DISPENSING = "DISPENSING", "Dispensing to Patient"
        DISPOSAL = "DISPOSAL", "Witnessed Disposal"

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="controlled_drug_logs"
    )
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT)
    batch_number = models.CharField(max_length=100)
    movement_type = models.CharField(max_length=20, choices=MovementType.choices)
    quantity = models.IntegerField()
    running_balance = models.PositiveIntegerField()
    patient_name = models.CharField(max_length=150, blank=True, default="")
    prescriber_name = models.CharField(max_length=150, blank=True, default="")
    witness_name = models.CharField(max_length=150, blank=True, default="")
    rx_reference = models.CharField(max_length=100, blank=True, default="")
    logged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    logged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-logged_at"]

    def __str__(self) -> str:
        return f"CD-LOG #{self.id} · {self.product.generic_name} ({self.movement_type})"


class POSPromotion(models.Model):
    """Retail promotional campaigns & coupon engine. ROADMAP '6. Retail (POS)'."""

    class PromoType(models.TextChoices):
        PERCENT_DISCOUNT = "PERCENT", "Percentage Discount (%)"
        FLAT_DISCOUNT = "FLAT", "Flat Amount Off (RWF)"
        BOGO = "BOGO", "Buy One Get One"

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=150)
    promo_type = models.CharField(max_length=20, choices=PromoType.choices, default=PromoType.PERCENT_DISCOUNT)
    discount_value = models.DecimalField(max_digits=14, decimal_places=2)
    min_spend = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    valid_from = models.DateField()
    valid_until = models.DateField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Promo {self.code} · {self.name}"


class ClinicalService(models.Model):
    """Billable pharmacy clinical services catalog. ROADMAP '6. Retail (POS)'."""

    class Category(models.TextChoices):
        VACCINATION = "VACCINATION", "Vaccination / Immunization"
        SCREENING = "SCREENING", "Point-of-Care Testing (BP, Glucose, Malaria)"
        CONSULTATION = "CONSULTATION", "Pharmacist Consultation"
        PROCEDURE = "PROCEDURE", "Minor Clinical Procedure"

    service_code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=150)
    category = models.CharField(max_length=30, choices=Category.choices, default=Category.SCREENING)
    fee_amount = models.DecimalField(max_digits=14, decimal_places=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.service_code} · {self.name} (RWF {self.fee_amount})"


class ClinicalServiceRecord(models.Model):
    """Patient clinical service encounter log. ROADMAP '6. Retail (POS)'."""

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="clinical_encounters"
    )
    service = models.ForeignKey(ClinicalService, on_delete=models.PROTECT, related_name="encounters")
    patient_name = models.CharField(max_length=150)
    patient_phone = models.CharField(max_length=20, blank=True, default="")
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    clinical_notes = models.TextField(blank=True, default="")
    fee_charged = models.DecimalField(max_digits=14, decimal_places=2)
    performed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-performed_at"]

    def __str__(self) -> str:
        return f"Service #{self.id} · {self.service.name} for {self.patient_name}"

