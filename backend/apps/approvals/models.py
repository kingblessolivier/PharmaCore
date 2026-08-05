"""The central approvals engine (cross-cutting authorisation backbone).

Any sensitive action (credit-limit override, employee termination, payroll run,
write-off, …) that must not be self-approved routes through an ``ApprovalRequest``
instead of mutating state directly. See docs/12-requirements-fields-documents-
approvals.md §4 and ROADMAP.md "A. Approvals engine":
claim-to-lock, no self-approval, SLA timers, escalation/senior oversight.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import models
from django.utils import timezone

DEFAULT_SLA_HOURS = 48


class ApprovalRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    # What the request is about — a generic reference so any subsystem can use the
    # same engine without this app knowing their models (e.g. "finance.credit_override",
    # "hr.employee_termination").
    resource_type = models.CharField(max_length=60)
    resource_id = models.CharField(max_length=64)
    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.CASCADE, related_name="approval_requests"
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="approvals_requested"
    )
    # Data the registered handler needs to apply the change once approved.
    payload = models.JSONField(default=dict, blank=True)
    reason = models.CharField(max_length=300, blank=True, default="")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)

    # Claim-to-lock: an approver claims the item before deciding it; hidden/locked
    # from others while claimed. No self-approval: requested_by can never claim or
    # decide their own request (enforced in services.py).
    claimed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approvals_claimed",
    )
    claimed_at = models.DateTimeField(null=True, blank=True)

    # SLA timer: on timeout the claim releases and the item re-enters the queue
    # (never silently stuck) — see services.refresh_sla().
    sla_hours = models.PositiveIntegerField(default=DEFAULT_SLA_HOURS)
    sla_breached = models.BooleanField(default=False)

    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approvals_decided",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(max_length=300, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["resource_type", "resource_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.resource_type}#{self.resource_id} ({self.status})"

    @property
    def sla_deadline(self) -> Any:
        return self.created_at + timedelta(hours=self.sla_hours)

    @property
    def is_overdue(self) -> bool:
        return self.status == self.Status.PENDING and timezone.now() > self.sla_deadline
