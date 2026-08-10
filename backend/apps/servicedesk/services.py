"""Ticket rules.

Two of them carry the weight:

* **a ticket cannot be resolved without saying how.** "Resolved" with an empty
  resolution is a queue being cleared, not a customer being helped, and it is
  invisible in every metric until somebody rings back.
* **the promise is set once, at creation.** Raising the priority later must not
  quietly rewrite a target that has already been missed — that is how a service
  desk reports 100% SLA compliance while customers wait.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.core.sequences import next_number
from apps.iam.audit import record_audit
from apps.iam.models import User
from apps.servicedesk.models import Ticket, TicketNote


class TicketError(ValueError):
    """A service-desk rule was violated — surfaced as 400, never a 500."""


@transaction.atomic
def raise_ticket(
    *,
    organization: Any,
    subject: str,
    body: str,
    user: User | None = None,
    **fields: Any,
) -> Ticket:
    if not subject.strip():
        raise TicketError("A ticket needs a subject — it is what the queue is read by.")
    ticket = Ticket.objects.create(
        organization=organization,
        subject=subject.strip(),
        body=body.strip(),
        raised_by=user,
        **fields,
    )
    year = timezone.localdate().year
    seq = next_number(organization=organization, domain="servicedesk", kind="TKT", year=year)
    ticket.ticket_number = f"TKT-{year}-{seq:05d}"
    ticket.save(update_fields=["ticket_number"])

    record_audit(
        action="TICKET_RAISED",
        user=user,
        organization=organization,
        entity_type="ticket",
        entity_id=str(ticket.pk),
        changes={"subject": ticket.subject, "priority": ticket.priority},
    )
    return ticket


@transaction.atomic
def add_note(
    *, ticket: Ticket, body: str, internal: bool = False, user: User | None = None
) -> TicketNote:
    """Record an exchange, and stamp the first response.

    First response is stamped from the first note *to the customer* — an
    internal note saying "who owns this?" is not a reply, and counting it as
    one is how a desk reports fast responses nobody received.
    """
    if not body.strip():
        raise TicketError("A note needs something in it.")
    note = TicketNote.objects.create(
        ticket=ticket, body=body.strip(), is_internal=internal, author=user
    )
    if not internal and ticket.first_response_at is None:
        ticket.first_response_at = timezone.now()
        ticket.save(update_fields=["first_response_at", "updated_at"])
    if ticket.status == Ticket.Status.OPEN and not internal:
        ticket.status = Ticket.Status.IN_PROGRESS
        ticket.save(update_fields=["status", "updated_at"])
    return note


@transaction.atomic
def resolve_ticket(*, ticket: Ticket, resolution: str, user: User | None = None) -> Ticket:
    if not ticket.is_open:
        raise TicketError(
            f"{ticket.ticket_number} is already {ticket.get_status_display().lower()}."
        )
    if not resolution.strip():
        raise TicketError(
            "Say how it was resolved. A ticket closed with an empty resolution is a queue "
            "being cleared, not a customer being helped."
        )
    resolved_at = timezone.now()
    breached = ticket.due_at is not None and ticket.due_at < resolved_at
    ticket.status = Ticket.Status.RESOLVED
    ticket.resolution = resolution.strip()
    ticket.resolved_at = resolved_at
    ticket.save(update_fields=["status", "resolution", "resolved_at", "updated_at"])

    record_audit(
        action="TICKET_RESOLVED",
        user=user,
        organization=ticket.organization,
        entity_type="ticket",
        entity_id=str(ticket.pk),
        changes={"ticket": ticket.ticket_number, "breached": breached},
    )
    return ticket


@transaction.atomic
def escalate_to_quality(*, ticket: Ticket, user: User | None = None) -> Ticket:
    """This turned out to be a quality matter, not just a customer one.

    The ticket keeps its own clock. A customer waiting on a short delivery
    should not wait for a CAPA to finish before somebody talks to them.
    """
    from apps.quality import services as quality
    from apps.quality.models import QualityCase, Severity

    if ticket.quality_case_id:
        raise TicketError(f"{ticket.ticket_number} already has a quality case.")

    ticket.quality_case = quality.open_case(
        organization=ticket.organization,
        kind=QualityCase.Kind.COMPLAINT,
        source=(
            QualityCase.Source.PHARMACY
            if ticket.customer_organization_id
            else QualityCase.Source.PATIENT
        ),
        severity=Severity.MAJOR if ticket.priority == Ticket.Priority.URGENT else Severity.MINOR,
        title=ticket.subject,
        description=f"Raised from ticket {ticket.ticket_number}.\n\n{ticket.body}",
        product=ticket.product,
        user=user,
    )
    ticket.save(update_fields=["quality_case", "updated_at"])
    return ticket


def queue_summary(*, organization: Any) -> dict[str, Any]:
    """What the desk is carrying, ordered by what is about to fail."""
    tickets = Ticket.objects.filter(organization=organization).exclude(
        status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED]
    )
    now = timezone.now()
    return {
        "open": tickets.count(),
        "breached": tickets.filter(due_at__lt=now).count(),
        "unassigned": tickets.filter(assigned_to__isnull=True).count(),
        "awaiting_first_response": tickets.filter(first_response_at__isnull=True).count(),
        "by_priority": {p: tickets.filter(priority=p).count() for p, _ in Ticket.Priority.choices},
    }
