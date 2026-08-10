"""Quality: what went wrong, why, and what was done about it.

Three records that look separate and are not:

* a **complaint** is what somebody outside the system noticed;
* a **deviation** is a departure from a procedure or a specification;
* an **adverse event** is harm, or suspected harm, to a patient.

All three end in the same place — an investigation, a root cause, and actions
with owners and dates that somebody later has to prove worked. That shared
ending is why they are one app. Building them separately produces three
half-implementations of CAPA and no single answer to "what is open".

Quality is deliberately independent of the warehouse and of procurement. A
department that both creates deviations and closes them is not a control, and
the whole point of GDP's quality chapter is that somebody outside the process
signs off that the process was fixed.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class Severity(models.TextChoices):
    """How bad this is, in the language regulators use.

    Critical is not "urgent" — it is "a patient could be harmed, or the licence
    is at risk". Keeping the word for that case is what makes it useful.
    """

    CRITICAL = "CRITICAL", "Critical — patient safety or licence at risk"
    MAJOR = "MAJOR", "Major — product quality or compliance affected"
    MINOR = "MINOR", "Minor — no product or patient impact"


class CaseStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    INVESTIGATING = "INVESTIGATING", "Under investigation"
    ACTIONS_PENDING = "ACTIONS_PENDING", "Actions pending"
    VERIFYING = "VERIFYING", "Verifying effectiveness"
    CLOSED = "CLOSED", "Closed"
    REJECTED = "REJECTED", "Rejected — not a quality issue"


class QualityCase(models.Model):
    """The common shape. Complaints, deviations and adverse events all have it.

    A single table with a ``kind`` rather than three parallel ones, because the
    questions people ask cut across the kinds — "what is open on this batch",
    "what is overdue", "what did we tell the regulator" — and three tables make
    every one of those a union.
    """

    class Kind(models.TextChoices):
        COMPLAINT = "COMPLAINT", "Complaint"
        DEVIATION = "DEVIATION", "Deviation"
        ADVERSE_EVENT = "ADVERSE_EVENT", "Adverse event"

    class Source(models.TextChoices):
        PATIENT = "PATIENT", "Patient or customer"
        PHARMACY = "PHARMACY", "Pharmacy or customer organisation"
        INTERNAL = "INTERNAL", "Staff"
        SUPPLIER = "SUPPLIER", "Supplier"
        INSPECTION = "INSPECTION", "Inspection or audit"
        EXCURSION = "EXCURSION", "Temperature excursion"
        RECALL = "RECALL", "Recall"

    case_number = models.CharField(max_length=30, unique=True, blank=True, default="")
    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.PROTECT, related_name="quality_cases"
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.INTERNAL)
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.MINOR)
    status = models.CharField(max_length=20, choices=CaseStatus.choices, default=CaseStatus.OPEN)

    title = models.CharField(max_length=200)
    description = models.TextField()

    #: What it is about. All optional — a complaint about a delivery has no
    #: batch, and a deviation about a procedure has no product.
    product = models.ForeignKey(
        "catalog.Product", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    batch = models.ForeignKey(
        "inventory.InventoryBatch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="quality_cases",
    )
    #: Free text so a case can name a lot this pharmacy never held — a patient
    #: complaining about a pack bought elsewhere still needs recording.
    batch_number = models.CharField(max_length=100, blank=True, default="")

    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    reporter_name = models.CharField(max_length=150, blank=True, default="")
    reporter_contact = models.CharField(max_length=150, blank=True, default="")

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="quality_cases_owned",
    )
    due_date = models.DateField(null=True, blank=True)

    #: Filled during the investigation. Kept on the case rather than in a
    #: separate table: there is exactly one root cause per case, and splitting
    #: it out only adds a join to every question anyone asks.
    investigation = models.TextField(blank=True, default="")
    root_cause = models.TextField(blank=True, default="")

    #: Whether the regulator has to be told. Rwanda FDA expects adverse
    #: reactions, quality defects and recalls to be reported; the flag is set
    #: by a person, because "is this reportable" is a judgement.
    is_reportable = models.BooleanField(default=False)
    reported_to_regulator_at = models.DateTimeField(null=True, blank=True)
    regulator_reference = models.CharField(max_length=100, blank=True, default="")

    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    closure_note = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["kind", "status"]),
            models.Index(fields=["batch"]),
        ]

    def __str__(self) -> str:
        return f"{self.case_number or 'Case'} — {self.title}"

    @property
    def is_open(self) -> bool:
        return self.status not in (CaseStatus.CLOSED, CaseStatus.REJECTED)

    @property
    def outstanding_actions(self) -> int:
        return self.actions.exclude(status=CapaAction.Status.VERIFIED).count()


class AdverseEventDetail(models.Model):
    """The extra a pharmacovigilance case carries.

    Split out rather than added to every case, because these fields describe a
    patient and most cases have no patient. Keeping them on the main table
    would put clinical data on every delivery complaint.
    """

    class Seriousness(models.TextChoices):
        NON_SERIOUS = "NON_SERIOUS", "Non-serious"
        SERIOUS = "SERIOUS", "Serious — hospitalisation, disability or worse"
        FATAL = "FATAL", "Fatal"

    class Outcome(models.TextChoices):
        RECOVERED = "RECOVERED", "Recovered"
        RECOVERING = "RECOVERING", "Recovering"
        NOT_RECOVERED = "NOT_RECOVERED", "Not recovered"
        FATAL = "FATAL", "Fatal"
        UNKNOWN = "UNKNOWN", "Unknown"

    class Causality(models.TextChoices):
        CERTAIN = "CERTAIN", "Certain"
        PROBABLE = "PROBABLE", "Probable"
        POSSIBLE = "POSSIBLE", "Possible"
        UNLIKELY = "UNLIKELY", "Unlikely"
        UNASSESSED = "UNASSESSED", "Not yet assessed"

    case = models.OneToOneField(QualityCase, on_delete=models.CASCADE, related_name="adverse_event")
    #: Deliberately minimal. A pharmacy needs enough to identify a report and
    #: to spot a pattern; it is not a clinical record, and holding more patient
    #: data than the report needs is a liability rather than a feature.
    patient_initials = models.CharField(max_length=10, blank=True, default="")
    patient_age = models.PositiveSmallIntegerField(null=True, blank=True)
    patient_sex = models.CharField(max_length=10, blank=True, default="")

    reaction = models.TextField(help_text="What happened, in the reporter's words.")
    onset_date = models.DateField(null=True, blank=True)
    seriousness = models.CharField(
        max_length=15, choices=Seriousness.choices, default=Seriousness.NON_SERIOUS
    )
    outcome = models.CharField(max_length=15, choices=Outcome.choices, default=Outcome.UNKNOWN)
    causality = models.CharField(
        max_length=12, choices=Causality.choices, default=Causality.UNASSESSED
    )
    concomitant_medicines = models.TextField(blank=True, default="")
    dechallenge = models.BooleanField(
        null=True,
        blank=True,
        help_text="Did the reaction settle when the medicine was stopped?",
    )
    rechallenge = models.BooleanField(
        null=True,
        blank=True,
        help_text="Did it return when the medicine was restarted?",
    )

    def __str__(self) -> str:
        return f"Adverse event on {self.case.case_number}"


class CapaAction(models.Model):
    """One thing somebody has to do, and the proof they did it.

    Corrective fixes this occurrence; preventive stops the next one. The
    distinction is not bureaucratic — a case closed with only corrective
    actions has fixed a symptom, and an inspector reading a year of those will
    say so.

    An action is not closed by its owner. It is closed by quality, after an
    effectiveness check, because "I did it" and "it worked" are different
    claims.
    """

    class Kind(models.TextChoices):
        CORRECTIVE = "CORRECTIVE", "Corrective — fix this occurrence"
        PREVENTIVE = "PREVENTIVE", "Preventive — stop it happening again"
        IMMEDIATE = "IMMEDIATE", "Immediate containment"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        DONE = "DONE", "Done — awaiting verification"
        VERIFIED = "VERIFIED", "Verified effective"
        INEFFECTIVE = "INEFFECTIVE", "Verified ineffective"

    case = models.ForeignKey(QualityCase, on_delete=models.CASCADE, related_name="actions")
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.CORRECTIVE)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    description = models.TextField()
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    due_date = models.DateField(null=True, blank=True)

    completed_at = models.DateTimeField(null=True, blank=True)
    completion_note = models.TextField(blank=True, default="")

    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    effectiveness_note = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["due_date", "id"]
        indexes = [models.Index(fields=["case", "status"])]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} — {self.description[:40]}"

    @property
    def is_overdue(self) -> bool:
        from django.utils import timezone

        if self.due_date is None or self.status == self.Status.VERIFIED:
            return False
        return self.due_date < timezone.localdate()


class AuditEngagement(models.Model):
    """A planned look at whether a part of the business does what it says.

    Internal audit is not the audit *log*. The log records what happened; this
    records somebody deliberately going to check — a branch's stock accuracy, a
    supplier's paperwork, whether the cold chain SOP is actually followed.

    It lives beside CAPA because that is where a finding has to end up. An
    audit that produces a report and no owned, dated action is an audit nobody
    acts on, which is the usual failure.
    """

    class Kind(models.TextChoices):
        SELF_INSPECTION = "SELF_INSPECTION", "Self-inspection"
        BRANCH = "BRANCH", "Branch audit"
        SUPPLIER = "SUPPLIER", "Supplier audit"
        PROCESS = "PROCESS", "Process audit"
        REGULATORY = "REGULATORY", "Regulatory inspection"

    class Status(models.TextChoices):
        PLANNED = "PLANNED", "Planned"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        REPORTING = "REPORTING", "Reporting"
        CLOSED = "CLOSED", "Closed"

    reference = models.CharField(max_length=30, unique=True, blank=True, default="")
    organization = models.ForeignKey(
        "iam.Organization", on_delete=models.PROTECT, related_name="audit_engagements"
    )
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.SELF_INSPECTION)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PLANNED)
    title = models.CharField(max_length=200)
    scope = models.TextField(help_text="What is being examined, and what is deliberately not.")

    #: What is being audited. A branch audit names an organisation; a supplier
    #: audit names a supplier; a process audit names neither.
    subject_organization = models.ForeignKey(
        "iam.Organization", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    subject_supplier = models.ForeignKey(
        "catalog.Supplier", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    lead_auditor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    planned_for = models.DateField(null=True, blank=True)
    started_at = models.DateField(null=True, blank=True)
    completed_at = models.DateField(null=True, blank=True)

    summary = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-planned_for", "-created_at"]
        indexes = [models.Index(fields=["organization", "status"])]

    def __str__(self) -> str:
        return f"{self.reference or 'Audit'} — {self.title}"

    @property
    def open_findings(self) -> int:
        return self.findings.exclude(status=AuditFinding.Status.CLOSED).count()


class AuditFinding(models.Model):
    """One thing the audit found, and what was said about it.

    A finding carries a **management response** as well as an observation,
    because an audit where the audited party never answered is half a
    conversation. Where the finding is serious it raises a quality case, so the
    corrective and preventive work runs through the same CAPA lifecycle as
    everything else rather than in an audit-shaped silo.
    """

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        RESPONDED = "RESPONDED", "Management responded"
        ACTIONS_RAISED = "ACTIONS_RAISED", "Actions raised"
        CLOSED = "CLOSED", "Closed"

    engagement = models.ForeignKey(
        AuditEngagement, on_delete=models.CASCADE, related_name="findings"
    )
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.MINOR)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.OPEN)
    observation = models.TextField(help_text="What was seen, with the evidence for it.")
    requirement = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="The SOP, licence condition or regulation this departs from.",
    )
    management_response = models.TextField(blank=True, default="")
    responded_at = models.DateTimeField(null=True, blank=True)

    #: Serious findings become quality cases so their actions are verified for
    #: effectiveness like any other CAPA, rather than closed on assertion.
    case = models.OneToOneField(
        QualityCase, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_finding"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-severity", "id"]

    def __str__(self) -> str:
        return f"{self.get_severity_display().split(' —')[0]} — {self.observation[:50]}"
