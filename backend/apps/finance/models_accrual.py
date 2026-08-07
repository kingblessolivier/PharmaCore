"""Accruals and prepayments — spreading a cost over the months it belongs to.

Without these, a monthly P&L is lumpy and wrong in both directions. Insurance
paid annually in January makes January look terrible and the other eleven months
look better than they are. Rent invoiced quarterly in arrears makes two months
look free and the third look ruinous. Neither picture is true, and a branch
manager judged on either is being judged on the billing calendar rather than on
the business.

Two shapes, mirror images of each other:

* **Prepayment** — cash has gone out, the benefit has not been consumed yet. The
  unconsumed part is an asset (``1600 Prepayments``) released to the P&L monthly.
* **Accrual** — the benefit has been consumed, the invoice has not arrived. The
  obligation is a liability (``2170 Accruals``) charged to the P&L monthly.

Accruals post as **reversing** entries by default: the charge goes in on the last
day of the month and comes straight back out on the first of the next. When the
real invoice finally arrives it is posted normally, and the cost is counted once
rather than twice. Non-reversing accruals have to be released by hand, which is a
reliable source of costs that get counted twice.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import models


class RecurringSchedule(models.Model):
    """A cost spread across a defined number of months."""

    class Kind(models.TextChoices):
        PREPAYMENT = "PREPAYMENT", "Prepayment (paid in advance)"
        ACCRUAL = "ACCRUAL", "Accrual (incurred, not yet billed)"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="recurring_schedules"
    )
    name = models.CharField(max_length=150)
    kind = models.CharField(max_length=12, choices=Kind.choices)
    # The P&L account the monthly charge lands in.
    expense_account = models.ForeignKey(
        "finance.Account", on_delete=models.PROTECT, related_name="+"
    )
    cost_centre = models.ForeignKey(
        "finance.CostCentre", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    total_amount = models.DecimalField(max_digits=14, decimal_places=2)
    periods = models.PositiveSmallIntegerField(help_text="How many months to spread across")
    # First month the charge applies to, stored as the first of that month.
    start_month = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    # An accrual normally reverses itself the next day so the real invoice can be
    # posted without double-counting. Prepayments never reverse — the asset is
    # genuinely being consumed.
    auto_reverse = models.BooleanField(default=True)
    source_reference = models.CharField(max_length=120, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_month", "name"]
        indexes = [models.Index(fields=["organization", "status"])]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_kind_display()})"

    @property
    def amount_per_period(self) -> Decimal:
        """The monthly charge. The final period absorbs any rounding remainder."""
        if not self.periods:
            return Decimal("0.00")
        return (self.total_amount / self.periods).quantize(Decimal("0.01"))

    @property
    def balance_account_code(self) -> str:
        """Prepayments sit in an asset; accruals sit in a liability."""
        return "1600" if self.kind == self.Kind.PREPAYMENT else "2170"

    @property
    def posted_total(self) -> Decimal:
        return sum((run.amount for run in self.runs.all()), Decimal("0.00"))

    @property
    def remaining(self) -> Decimal:
        return self.total_amount - self.posted_total


class ScheduleRun(models.Model):
    """One month of a schedule, posted once.

    The unique constraint on ``(schedule, period_month)`` is what makes the
    monthly run idempotent: a re-run, a retry, or two people clicking at once
    cannot charge the same month twice.
    """

    schedule = models.ForeignKey(RecurringSchedule, on_delete=models.CASCADE, related_name="runs")
    # The first of the month this charge belongs to.
    period_month = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    journal_entry = models.ForeignKey(
        "finance.JournalEntry", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    reversal_entry = models.ForeignKey(
        "finance.JournalEntry", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    posted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["period_month"]
        constraints = [
            models.UniqueConstraint(
                fields=["schedule", "period_month"], name="uniq_schedule_run_per_month"
            )
        ]

    def __str__(self) -> str:
        return f"{self.schedule.name} {self.period_month:%b %Y} {self.amount}"
