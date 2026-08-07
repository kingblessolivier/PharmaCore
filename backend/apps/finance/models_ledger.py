"""The ledger spine: analysis dimensions, budgets that read from the books, and
the period-close checklist.

Three things were missing from the general ledger, and each one made a screen
above it dishonest:

* **A dimension.** ``JournalLine`` carried an account and nothing else, so the
  books could not answer "what did the Kicukiro branch spend on rent". ``Budget``
  was keyed by department while the ledger had never heard of one. ``CostCentre``
  closes that gap, and every posting can now carry one.

* **Budgets with real actuals.** The old ``Budget.actual_amount`` was a stored
  decimal that nothing computed — it was typed in by hand next to the budget it
  was meant to test. Actuals are now derived from the ledger at read time and
  cannot be edited, because a variance whose actual is supplied by the person
  being measured is not a control.

* **A close that checks anything.** Closing a period froze the dates but asked
  no questions. ``PeriodTask`` makes the checklist explicit and lets a task block
  the close until it is done or explicitly waived.

See docs/development/finance-redesign-plan.md §2B.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import models


class CostCentre(models.Model):
    """A dimension every posting can be tagged with, so the ledger can be sliced
    by branch, department or function without inventing more accounts.

    The alternative — a separate expense account per branch ("6110 Rent Kicukiro",
    "6110 Rent Remera") — is how charts of accounts grow to four thousand lines
    and stop being readable. One account, many cost centres.

    Centres form a tree so a group can roll Kicukiro and Remera up into "Retail"
    without restating anything.
    """

    class Kind(models.TextChoices):
        BRANCH = "BRANCH", "Branch / site"
        DEPARTMENT = "DEPARTMENT", "Department"
        FUNCTION = "FUNCTION", "Function"
        PROJECT = "PROJECT", "Project"

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="cost_centres"
    )
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=150)
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.DEPARTMENT)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )
    # Optional links to the things a centre often *is*, so the tree can be kept in
    # step with the org chart instead of drifting from it.
    department = models.ForeignKey(
        "iam.Department", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    branch = models.ForeignKey(
        "iam.Organization", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    manager = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"], name="uniq_cost_centre_code_per_org"
            )
        ]
        indexes = [models.Index(fields=["organization", "is_active"])]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"

    @property
    def path(self) -> str:
        """`Retail / Kicukiro` — the roll-up this centre reports into."""
        names, node, seen = [], self, set()
        while node is not None and node.pk not in seen:
            seen.add(node.pk)
            names.append(node.name)
            node = node.parent  # type: ignore[assignment]
        return " / ".join(reversed(names))

    def descendant_ids(self) -> list[int]:
        """This centre and everything under it — the set a roll-up query needs."""
        ids, frontier = [self.pk], [self.pk]
        while frontier:
            frontier = list(
                CostCentre.objects.filter(parent_id__in=frontier).values_list("pk", flat=True)
            )
            ids.extend(frontier)
        return ids


class Budget(models.Model):
    """A named plan for one financial year — the header its lines hang from.

    A budget is a document with a life: drafted, approved, then locked so the
    thing being measured against cannot be moved after the fact. That is the
    whole point of a budget, and the previous model had no state at all.
    """

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        APPROVED = "APPROVED", "Approved"
        LOCKED = "LOCKED", "Locked"
        ARCHIVED = "ARCHIVED", "Archived"

    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="budget_plans"
    )
    name = models.CharField(max_length=150)
    financial_year = models.PositiveIntegerField(default=2026)
    # Month the financial year opens on — Rwandan practice is mostly January, but
    # a group reporting to a foreign parent may run July–June.
    year_starts_month = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    notes = models.TextField(blank=True, default="")
    approved_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # An explicit table: the old `Budget` model was renamed to `BudgetLine`,
        # and on a rename SQLite keeps the original index names. Reusing
        # `finance_budget` here would collide with them, so the header gets its
        # own table rather than a migration that only works on one backend.
        db_table = "finance_budget_plan"
        ordering = ["-financial_year", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "financial_year", "name"], name="uniq_budget_per_year"
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} FY{self.financial_year}"

    @property
    def is_editable(self) -> bool:
        return self.status in {self.Status.DRAFT, self.Status.APPROVED}


class BudgetLine(models.Model):
    """One account × cost centre × month of a budget.

    ``period_month`` is nullable and means *annual*: a figure for the whole year
    that a partial-period query consumes pro rata. Both shapes are legitimate —
    rent is known monthly, a training allowance is agreed annually — and forcing
    an annual figure into twelve equal months would invent precision that was
    never in the plan.

    There is deliberately no ``actual`` column. Actuals come from the ledger.
    """

    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name="lines")
    account = models.ForeignKey("finance.Account", on_delete=models.PROTECT, related_name="+")
    cost_centre = models.ForeignKey(
        CostCentre, null=True, blank=True, on_delete=models.PROTECT, related_name="budget_lines"
    )
    period_month = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="1–12, or blank for an annual figure"
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    note = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["account__code", "period_month"]
        constraints = [
            models.UniqueConstraint(
                fields=["budget", "account", "cost_centre", "period_month"],
                name="uniq_budget_line_slice",
            )
        ]
        indexes = [models.Index(fields=["budget", "account"])]

    def __str__(self) -> str:
        when = f"M{self.period_month}" if self.period_month else "annual"
        return f"{self.account.code} {when} {self.amount}"


class PeriodTask(models.Model):
    """One item on the close checklist for an accounting period.

    Blocking tasks stop the close. Waiving one is allowed — months genuinely differ
    — but it must be deliberate and it leaves a reason behind, which is the
    difference between a control and an obstacle.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        DONE = "DONE", "Done"
        WAIVED = "WAIVED", "Waived"

    period = models.ForeignKey(
        "finance.AccountingPeriod", on_delete=models.CASCADE, related_name="tasks"
    )
    code = models.CharField(max_length=40)
    title = models.CharField(max_length=200)
    description = models.CharField(max_length=400, blank=True, default="")
    sequence = models.PositiveSmallIntegerField(default=0)
    is_blocking = models.BooleanField(default=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    completed_by = models.ForeignKey(
        "iam.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["sequence", "id"]
        constraints = [
            models.UniqueConstraint(fields=["period", "code"], name="uniq_period_task_code")
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.status})"

    @property
    def is_settled(self) -> bool:
        return self.status in {self.Status.DONE, self.Status.WAIVED}
