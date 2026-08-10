"""The rules a quality case has to obey.

The point of putting these here rather than in a view is that a case can be
raised from four places — the counter, a temperature excursion, a goods
receipt, an inspection — and every one of them must produce a case that closes
the same way.

Two rules do the real work:

* **a case cannot be closed with actions outstanding.** Otherwise "closed"
  means "somebody stopped looking", which is what an inspector reading a
  closed case a year later is checking for.
* **a critical or serious case needs a preventive action, not just a
  corrective one.** Fixing the occurrence and calling it done is how the same
  deviation appears three times in a year.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.core.sequences import next_number
from apps.iam.audit import record_audit
from apps.iam.models import User
from apps.quality.models import (
    AdverseEventDetail,
    CapaAction,
    CaseStatus,
    QualityCase,
    Severity,
)


class QualityError(ValueError):
    """A quality rule was violated — surfaced as 400, never a 500."""


#: Kinds that must reach the regulator when they are serious. Set as a default
#: on the case; a person can still overrule it, because "is this reportable" is
#: a judgement and the system should not pretend otherwise.
_ALWAYS_CONSIDER_REPORTABLE = (
    QualityCase.Kind.ADVERSE_EVENT,
    QualityCase.Kind.COMPLAINT,
)


def _number_for(kind: str, organization: Any) -> str:
    """CMP-2026-00042. Gapless per organisation and year, like every other
    document number in the system — a quality case is cited in correspondence
    with a regulator and cannot have holes in its sequence."""
    prefixes: dict[str, str] = {
        QualityCase.Kind.COMPLAINT: "CMP",
        QualityCase.Kind.DEVIATION: "DEV",
        QualityCase.Kind.ADVERSE_EVENT: "AE",
    }
    prefix = prefixes.get(kind, "QC")
    year = timezone.localdate().year
    seq = next_number(organization=organization, domain="quality", kind=prefix, year=year)
    return f"{prefix}-{year}-{seq:05d}"


@transaction.atomic
def open_case(
    *,
    organization: Any,
    kind: str,
    title: str,
    description: str,
    severity: str = Severity.MINOR,
    source: str = QualityCase.Source.INTERNAL,
    user: User | None = None,
    adverse_event: dict[str, Any] | None = None,
    **fields: Any,
) -> QualityCase:
    """Raise a case. The only way one is created.

    Numbering happens here so a case has an identifier the moment it exists —
    somebody on a phone to a patient needs to be able to say "your reference is
    CMP-2026-00042" before the conversation ends.
    """
    if not title.strip():
        raise QualityError("A case needs a title — it is what everybody will search for.")
    if not description.strip():
        raise QualityError("A case needs a description of what actually happened.")

    case = QualityCase.objects.create(
        organization=organization,
        kind=kind,
        title=title.strip(),
        description=description.strip(),
        severity=severity,
        source=source,
        reported_by=user,
        # Adverse events and product complaints start life as candidates for
        # reporting; a deviation about a shelf label does not.
        is_reportable=(
            kind in _ALWAYS_CONSIDER_REPORTABLE and severity in (Severity.CRITICAL, Severity.MAJOR)
        ),
        **fields,
    )
    case.case_number = _number_for(kind, organization)
    case.save(update_fields=["case_number"])

    if adverse_event is not None:
        if kind != QualityCase.Kind.ADVERSE_EVENT:
            raise QualityError("Only an adverse event case carries patient details.")
        AdverseEventDetail.objects.create(case=case, **adverse_event)

    record_audit(
        action="QUALITY_CASE_OPENED",
        user=user,
        organization=organization,
        entity_type="quality_case",
        entity_id=str(case.pk),
        changes={"kind": kind, "severity": severity, "title": case.title},
    )
    return case


@transaction.atomic
def record_investigation(
    *, case: QualityCase, investigation: str, root_cause: str, user: User | None = None
) -> QualityCase:
    """What was found, and why it happened.

    A root cause is required to leave the investigation stage. "Operator error"
    is a description of an event, not a cause — but the system cannot judge
    that, so it insists only that something was written and leaves the quality
    review to catch the rest.
    """
    if case.status in (CaseStatus.CLOSED, CaseStatus.REJECTED):
        raise QualityError(f"{case.case_number} is already {case.get_status_display().lower()}.")
    if not root_cause.strip():
        raise QualityError("An investigation has to end in a root cause.")

    case.investigation = investigation.strip()
    case.root_cause = root_cause.strip()
    case.status = CaseStatus.ACTIONS_PENDING
    case.save(update_fields=["investigation", "root_cause", "status", "updated_at"])

    record_audit(
        action="QUALITY_INVESTIGATED",
        user=user,
        organization=case.organization,
        entity_type="quality_case",
        entity_id=str(case.pk),
        changes={"root_cause": case.root_cause[:200]},
    )
    return case


@transaction.atomic
def add_action(
    *,
    case: QualityCase,
    description: str,
    kind: str = CapaAction.Kind.CORRECTIVE,
    owner: User | None = None,
    due_date: Any = None,
    user: User | None = None,
) -> CapaAction:
    """Add one thing somebody must do."""
    if not case.is_open:
        raise QualityError(f"{case.case_number} is closed. Reopen it before adding actions.")
    if not description.strip():
        raise QualityError("An action has to say what will be done.")

    action = CapaAction.objects.create(
        case=case,
        kind=kind,
        description=description.strip(),
        owner=owner,
        due_date=due_date,
    )
    if case.status == CaseStatus.OPEN:
        case.status = CaseStatus.INVESTIGATING
        case.save(update_fields=["status", "updated_at"])

    record_audit(
        action="QUALITY_ACTION_ADDED",
        user=user,
        organization=case.organization,
        entity_type="quality_case",
        entity_id=str(case.pk),
        changes={"kind": kind, "description": action.description[:200]},
    )
    return action


@transaction.atomic
def complete_action(*, action: CapaAction, note: str = "", user: User | None = None) -> CapaAction:
    """The owner says it is done. It is not yet verified."""
    if action.status == CapaAction.Status.VERIFIED:
        raise QualityError("That action has already been verified.")
    action.status = CapaAction.Status.DONE
    action.completed_at = timezone.now()
    action.completion_note = note.strip()
    action.save(update_fields=["status", "completed_at", "completion_note"])
    return action


@transaction.atomic
def verify_action(
    *, action: CapaAction, effective: bool, note: str = "", user: User | None = None
) -> CapaAction:
    """Quality checks whether it worked.

    Deliberately not the owner's call, and deliberately able to say *no*. An
    effectiveness check that can only conclude "yes" is a signature, not a
    check — and a CAPA system where nothing is ever found ineffective is one
    nobody is really running.
    """
    if action.status == CapaAction.Status.OPEN:
        raise QualityError("That action has not been completed yet.")
    if user is not None and action.owner_id == user.pk:
        raise QualityError(
            "The person who carried out an action cannot verify their own. "
            "Effectiveness needs a second pair of eyes."
        )

    action.status = CapaAction.Status.VERIFIED if effective else CapaAction.Status.INEFFECTIVE
    action.verified_at = timezone.now()
    action.verified_by = user
    action.effectiveness_note = note.strip()
    action.save(update_fields=["status", "verified_at", "verified_by", "effectiveness_note"])

    case = action.case
    if not effective:
        # An ineffective action reopens the thinking, not just the task.
        case.status = CaseStatus.ACTIONS_PENDING
        case.save(update_fields=["status", "updated_at"])
    elif case.outstanding_actions == 0 and case.status == CaseStatus.ACTIONS_PENDING:
        case.status = CaseStatus.VERIFYING
        case.save(update_fields=["status", "updated_at"])

    record_audit(
        action="QUALITY_ACTION_VERIFIED" if effective else "QUALITY_ACTION_INEFFECTIVE",
        user=user,
        organization=case.organization,
        entity_type="quality_case",
        entity_id=str(case.pk),
        changes={"action": action.description[:200], "effective": effective},
    )
    return action


@transaction.atomic
def close_case(*, case: QualityCase, note: str = "", user: User | None = None) -> QualityCase:
    """Close it, if it is actually finished.

    Two refusals here, and both are the point of the module:

    * outstanding actions mean the case is not closed, it is abandoned;
    * a critical or major case closed with no *preventive* action has fixed
      this occurrence and left the cause in place.
    """
    if not case.is_open:
        raise QualityError(f"{case.case_number} is already {case.get_status_display().lower()}.")
    if not case.root_cause.strip():
        raise QualityError("A case cannot be closed without a root cause.")

    outstanding = case.outstanding_actions
    if outstanding:
        raise QualityError(
            f"{outstanding} action(s) on {case.case_number} are not verified effective yet."
        )

    if case.severity in (Severity.CRITICAL, Severity.MAJOR):
        preventive = case.actions.filter(kind=CapaAction.Kind.PREVENTIVE).exists()
        if not preventive:
            raise QualityError(
                f"A {case.get_severity_display().split(' —')[0].lower()} case needs at least one "
                "preventive action. Corrective actions alone fix this occurrence and leave the "
                "cause in place."
            )

    case.status = CaseStatus.CLOSED
    case.closed_at = timezone.now()
    case.closed_by = user
    case.closure_note = note.strip()
    case.save(update_fields=["status", "closed_at", "closed_by", "closure_note", "updated_at"])

    record_audit(
        action="QUALITY_CASE_CLOSED",
        user=user,
        organization=case.organization,
        entity_type="quality_case",
        entity_id=str(case.pk),
        changes={"case": case.case_number, "note": case.closure_note[:200]},
    )
    return case


def open_workload(*, organization: Any) -> dict[str, Any]:
    """What quality has on its plate, for a dashboard that means something."""
    cases = QualityCase.objects.filter(organization=organization).exclude(
        status__in=[CaseStatus.CLOSED, CaseStatus.REJECTED]
    )
    actions = CapaAction.objects.filter(case__organization=organization).exclude(
        status=CapaAction.Status.VERIFIED
    )
    today = timezone.localdate()
    return {
        "open_cases": cases.count(),
        "by_kind": {kind: cases.filter(kind=kind).count() for kind, _ in QualityCase.Kind.choices},
        "critical": cases.filter(severity=Severity.CRITICAL).count(),
        "overdue_cases": cases.filter(due_date__lt=today).count(),
        "open_actions": actions.count(),
        "overdue_actions": actions.filter(due_date__lt=today).count(),
        "awaiting_regulator_report": cases.filter(
            is_reportable=True, reported_to_regulator_at__isnull=True
        ).count(),
    }
