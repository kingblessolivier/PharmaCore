"""Bank reconciliation: what the bank says, against what the books say.

The previous design had `JournalLine.is_reconciled` — a boolean an operator could
tick, with a free-text reference beside it. Nothing modelled the bank's own
records, so "reconciling" meant agreeing the ledger with itself. That always
succeeds and proves nothing.

Reconciliation exists to catch the cases where the two sides *disagree*:

* money that left the account and never reached the ledger (a standing order, a
  direct debit, a card chargeback),
* **bank charges and interest**, which no internal document ever produces, so
  they can only enter the books from the statement,
* a payment posted twice, or posted for the wrong amount,
* a cheque written and posted but never presented — a real timing difference,
  not an error, which is why the reconciliation statement lists it rather than
  hiding it.

None of those are visible unless the bank's lines are stored as first-class rows
and matched against the ledger's. That is what these three models are for.

Sign convention: ``BankStatementLine.amount`` is **signed from our point of
view** — positive increases our cash, negative reduces it. Bank exports vary
(some use separate debit/credit columns, some invert the sign because the
account is the bank's liability), so the importer normalises once, here, rather
than leaving every reader to guess.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import models


class BankStatement(models.Model):
    """One statement period for one bank, MoMo or cash account.

    The opening and closing balances are the bank's, not ours. The whole point of
    the exercise is that they start out different from the ledger's, and the
    reconciliation explains why.
    """

    class Status(models.TextChoices):
        IMPORTED = "IMPORTED", "Imported"
        RECONCILING = "RECONCILING", "Reconciling"
        RECONCILED = "RECONCILED", "Reconciled"

    bank_account = models.ForeignKey(
        "finance.BankAccount", on_delete=models.CASCADE, related_name="statements"
    )
    reference = models.CharField(max_length=100, blank=True, default="")
    start_date = models.DateField()
    end_date = models.DateField()
    opening_balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    closing_balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.IMPORTED)
    source_filename = models.CharField(max_length=255, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    imported_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    imported_at = models.DateTimeField(auto_now_add=True)
    reconciled_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    reconciled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-end_date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["bank_account", "start_date", "end_date"],
                name="uniq_bank_statement_period",
            )
        ]
        indexes = [models.Index(fields=["bank_account", "status"])]

    def __str__(self) -> str:
        return f"{self.bank_account.name} {self.start_date}–{self.end_date}"

    @property
    def movement(self) -> Decimal:
        """What the bank says happened over the period, per its own two balances."""
        return self.closing_balance - self.opening_balance


class BankStatementLine(models.Model):
    """One line the bank reported.

    ``external_id`` is the bank's own identifier where the export supplies one. It
    is what makes a re-import idempotent: statements get downloaded twice, periods
    overlap, and an operator who imports March twice should not end up with every
    transaction duplicated.
    """

    class Status(models.TextChoices):
        UNMATCHED = "UNMATCHED", "Unmatched"
        MATCHED = "MATCHED", "Matched to the ledger"
        EXPLAINED = "EXPLAINED", "Posted from the statement"
        IGNORED = "IGNORED", "Ignored"

    statement = models.ForeignKey(BankStatement, on_delete=models.CASCADE, related_name="lines")
    line_date = models.DateField()
    description = models.CharField(max_length=255, blank=True, default="")
    reference = models.CharField(max_length=120, blank=True, default="")
    # Signed from our point of view: positive increases our cash.
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    # The bank's running balance after this line, when the export provides it.
    balance = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    external_id = models.CharField(max_length=120, blank=True, default="")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.UNMATCHED)
    note = models.CharField(max_length=255, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        ordering = ["line_date", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["statement", "external_id"],
                condition=models.Q(external_id__gt=""),
                name="uniq_statement_line_external_id",
            )
        ]
        indexes = [models.Index(fields=["statement", "status"])]

    def __str__(self) -> str:
        return f"{self.line_date} {self.amount} {self.description[:40]}"

    @property
    def is_settled(self) -> bool:
        return self.status in {self.Status.MATCHED, self.Status.EXPLAINED, self.Status.IGNORED}

    @property
    def matched_total(self) -> Decimal:
        """Signed total of the ledger lines matched to this bank line."""
        from .models import JournalLine

        total = Decimal("0.00")
        for match in self.matches.select_related("journal_line").all():
            line = match.journal_line
            total += line.amount if line.side == JournalLine.Side.DEBIT else -line.amount
        return total


class ReconciliationMatch(models.Model):
    """A link between one bank line and one ledger line.

    Many-to-many on purpose. A payment run leaves the bank as a single debit but
    settles a dozen supplier bills in the ledger, and a bank that batches card
    settlements does the reverse. Forcing one-to-one would make the common cases
    unmatchable and push operators back to ticking boxes.

    A ledger line may only be claimed once, though — matching the same payment
    against two bank lines would hide a genuine duplicate.
    """

    class Method(models.TextChoices):
        AUTO = "AUTO", "Matched automatically"
        MANUAL = "MANUAL", "Matched by hand"

    statement_line = models.ForeignKey(
        BankStatementLine, on_delete=models.CASCADE, related_name="matches"
    )
    journal_line = models.ForeignKey(
        "finance.JournalLine", on_delete=models.CASCADE, related_name="reconciliation_matches"
    )
    method = models.CharField(max_length=8, choices=Method.choices, default=Method.MANUAL)
    # 0–100. Only ever set by the auto-matcher, so a reviewer can sort the
    # doubtful ones to the top instead of re-checking everything.
    confidence = models.PositiveSmallIntegerField(default=100)
    matched_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    matched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["journal_line"], name="uniq_reconciliation_per_journal_line"
            )
        ]

    def __str__(self) -> str:
        return f"{self.statement_line_id} ↔ {self.journal_line_id}"
