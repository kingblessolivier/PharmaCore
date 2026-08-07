"""Exchange rates and the record of each revaluation.

A pharmacy that imports carries balances it does not control the value of. Owe a
supplier USD 10,000 at 1,300 RWF/USD and the books say 13,000,000. If the rate
moves to 1,350 before you pay, you owe 13,500,000 — half a million francs of loss
that no transaction created and nothing in the ledger will notice on its own.

IAS 21 splits this cleanly:

* **monetary** items — cash, receivables, payables — are a fixed number of foreign
  currency units, so they are restated at the closing rate and the difference
  goes to profit or loss;
* **non-monetary** items — inventory, fixed assets — stay at the rate on the day
  they were acquired, however the currency moves afterwards.

That is why `Account.is_monetary` exists rather than the revaluation guessing
from an account code.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import models


class ExchangeRate(models.Model):
    """One published rate for one currency on one day.

    Rates are effective-dated rather than overwritten: a revaluation done last
    month must keep producing last month's answer, and an invoice booked in March
    keeps the March rate however far the currency moves afterwards.
    """

    class Source(models.TextChoices):
        BNR = "BNR", "National Bank of Rwanda"
        BANK = "BANK", "Commercial bank"
        MANUAL = "MANUAL", "Entered by hand"

    currency = models.CharField(max_length=3)
    rate_date = models.DateField()
    # How many base-currency units one unit of `currency` buys.
    rate_to_base = models.DecimalField(max_digits=14, decimal_places=6)
    source = models.CharField(max_length=8, choices=Source.choices, default=Source.BNR)
    note = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-rate_date", "currency"]
        constraints = [
            models.UniqueConstraint(
                fields=["currency", "rate_date"], name="uniq_exchange_rate_per_day"
            )
        ]
        indexes = [models.Index(fields=["currency", "rate_date"])]

    def __str__(self) -> str:
        return f"1 {self.currency} = {self.rate_to_base} on {self.rate_date}"


class FxRevaluation(models.Model):
    """What a period-end revaluation restated, and by how much.

    Kept as a record rather than only a journal because the interesting question
    afterwards is never "what was the entry" but "which balances moved, at what
    rate, and was that a real exposure or a stale rate table".
    """

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="fx_revaluations"
    )
    as_of = models.DateField()
    # Net gain (positive) or loss (negative) taken to profit or loss.
    net_gain = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    detail = models.JSONField(default=list, blank=True)
    journal_entry = models.ForeignKey(
        "finance.JournalEntry",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    run_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-as_of"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "as_of"], name="uniq_fx_revaluation_per_date"
            )
        ]

    def __str__(self) -> str:
        return f"FX revaluation {self.organization_id} @ {self.as_of}: {self.net_gain}"
