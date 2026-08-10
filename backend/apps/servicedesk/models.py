"""Customer service: what somebody asked us to sort out, and whether we did.

Deliberately not a quality case. A quality case asks *why did this happen and
what stops it recurring*; a ticket asks *is this customer sorted yet*. A short
delivery is both — so a ticket can raise a case — but most tickets are a
billing query or a delivery time, and running those through a CAPA lifecycle
would bury the ones that matter.

The thing a service desk lives or dies by is the clock. Every ticket has a
target derived from its priority, and the list is ordered by how close it is to
breaching rather than by when it arrived.
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class Ticket(models.Model):
    class Category(models.TextChoices):
        DELIVERY = "DELIVERY", "Delivery"
        SHORTAGE = "SHORTAGE", "Short or missing goods"
        BILLING = "BILLING", "Billing or payment"
        PRODUCT = "PRODUCT", "Product question"
        RETURN = "RETURN", "Return or refund"
        INSURANCE = "INSURANCE", "Insurance or claim"
        OTHER = "OTHER", "Other"

    class Priority(models.TextChoices):
        URGENT = "URGENT", "Urgent"
        HIGH = "HIGH", "High"
        NORMAL = "NORMAL", "Normal"
        LOW = "LOW", "Low"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        WAITING = "WAITING", "Waiting on the customer"
        RESOLVED = "RESOLVED", "Resolved"
        CLOSED = "CLOSED", "Closed"

    #: How long each priority gets before it has failed its promise. Hours, so
    #: the arithmetic is obvious to whoever changes them.
    SLA_HOURS: dict[str, int] = {
        Priority.URGENT: 4,
        Priority.HIGH: 8,
        Priority.NORMAL: 24,
        Priority.LOW: 72,
    }

    ticket_number = models.CharField(max_length=30, unique=True, blank=True, default="")
    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.PROTECT, related_name="tickets"
    )
    category = models.CharField(max_length=15, choices=Category.choices, default=Category.OTHER)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMAL)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.OPEN)

    subject = models.CharField(max_length=200)
    body = models.TextField()

    #: Who raised it. A pharmacy on the B2B side, or a walk-in customer whose
    #: only identifier is a name and a phone number.
    customer_organization = models.ForeignKey(
        "iam.Organization", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    contact_name = models.CharField(max_length=150, blank=True, default="")
    contact_phone = models.CharField(max_length=50, blank=True, default="")

    #: What it is about, when it is about something we can point at.
    order_reference = models.CharField(max_length=50, blank=True, default="")
    product = models.ForeignKey(
        "catalog.Product", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tickets_assigned",
    )
    raised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    due_at = models.DateTimeField(null=True, blank=True)
    first_response_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution = models.TextField(blank=True, default="")

    #: A ticket that turned out to be a quality matter. The ticket still closes
    #: on its own clock — the customer should not wait for a CAPA to finish.
    quality_case = models.ForeignKey(
        "quality.QualityCase",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tickets",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_at", "-created_at"]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["assigned_to", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.ticket_number or 'Ticket'} — {self.subject}"

    def save(self, *args: object, **kwargs: object) -> None:
        """Set the promise when the ticket is first raised.

        Derived rather than entered, so a priority and its deadline cannot
        disagree — and fixed at creation, so raising the priority later does
        not quietly rewrite a target that has already been missed.
        """
        if self.due_at is None:
            hours = self.SLA_HOURS.get(self.priority, 24)
            self.due_at = timezone.now() + timedelta(hours=hours)
        super().save(*args, **kwargs)  # type: ignore[arg-type]

    @property
    def is_open(self) -> bool:
        return self.status not in (self.Status.RESOLVED, self.Status.CLOSED)

    @property
    def is_breached(self) -> bool:
        """Past its promise and still not resolved."""
        if self.due_at is None or not self.is_open:
            return False
        return self.due_at < timezone.now()

    @property
    def hours_remaining(self) -> float | None:
        if self.due_at is None or not self.is_open:
            return None
        return round((self.due_at - timezone.now()).total_seconds() / 3600, 1)


class TicketNote(models.Model):
    """One exchange on a ticket.

    ``is_internal`` separates a note to a colleague from a reply to the
    customer. Without the distinction people either say nothing useful, or say
    something internal in front of the customer.
    """

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    body = models.TextField()
    is_internal = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Note on {self.ticket.ticket_number}"
