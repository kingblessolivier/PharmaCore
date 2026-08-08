"""People services — the write-path for contracts, pay, leave, time, loans and
the employee lifecycle.

Everything that changes state lives here rather than in a view, so the same rule
holds from the API, a management command or a test. The invariants worth naming:

* a salary change never edits history — it closes the current structure and opens
  a new one, with a ``SalaryRevision`` as the paper trail;
* leave is held against a balance the moment it is requested (``pending``), and
  only becomes ``taken`` on approval — so two requests cannot spend the same day;
* payroll reads a **timesheet**, never raw punches, and a run cannot be approved
  while a timesheet for its period is unapproved;
* a loan installment is settled by a payroll run, once, and skipped (not lost)
  when the employee had unpaid leave;
* an employee cannot be terminated while an open payroll run still references
  them.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.hr.models import (
    Applicant,
    AttendanceLog,
    ChecklistItem,
    CompetencyAssessment,
    Employee,
    EmploymentContract,
    FinalSettlement,
    LeaveAccrual,
    LeaveBalance,
    LeaveRequest,
    LeaveType,
    LoanAdvance,
    LoanInstallment,
    OnboardingChecklist,
    PayrollRun,
    SalaryComponent,
    SalaryRevision,
    SalaryStructure,
    ShiftRoster,
    Termination,
    Timesheet,
)
from apps.iam.audit import record_audit
from apps.iam.models import Organization, User

ZERO = Decimal("0.00")


class PeopleError(ValueError):
    """A business-rule violation — surfaced to the API as a 400, never a 500."""


def _q(value: Decimal, places: str = "0.01") -> Decimal:
    return Decimal(value).quantize(Decimal(places))


# ---------------------------------------------------------------------------
# Contracts & salary structure
# ---------------------------------------------------------------------------


@transaction.atomic
def issue_contract(
    *,
    employee: Employee,
    kind: str,
    job_title: str,
    start_date: date,
    user: User | None = None,
    **fields: Any,
) -> EmploymentContract:
    """Open a new contract and supersede whatever was current.

    Only one contract is ``is_current`` at a time (DB-enforced), so "what are
    they on today" is a single lookup rather than a date-sorted guess.
    """
    EmploymentContract.objects.filter(employee=employee, is_current=True).update(
        is_current=False, status=EmploymentContract.Status.RENEWED
    )
    probation_months = int(fields.pop("probation_months", 3) or 0)
    contract = EmploymentContract.objects.create(
        employee=employee,
        kind=kind,
        job_title=job_title,
        start_date=start_date,
        probation_months=probation_months,
        probation_end=fields.pop("probation_end", None)
        or (start_date + timedelta(days=30 * probation_months) if probation_months else None),
        status=EmploymentContract.Status.ACTIVE,
        is_current=True,
        created_by=user,
        **fields,
    )
    # Keep the denormalised fields on Employee in step — screens read them.
    employee.job_title = job_title or employee.job_title
    employee.probation_end = contract.probation_end
    employee.contract_end = contract.end_date
    employee.save(update_fields=["job_title", "probation_end", "contract_end", "updated_at"])
    record_audit(
        action="CONTRACT_ISSUED",
        user=user,
        organization=employee.organization,
        entity_type="employment_contract",
        entity_id=str(contract.pk),
        changes={"employee": str(employee), "kind": kind, "start": str(start_date)},
    )
    return contract


@transaction.atomic
def set_salary_structure(
    *,
    employee: Employee,
    effective_from: date,
    components: list[dict[str, Any]],
    reason: str = SalaryRevision.Reason.ANNUAL_REVIEW,
    note: str = "",
    user: User | None = None,
) -> SalaryStructure:
    """Open a new effective-dated pay structure and record the revision.

    The previous structure is closed the day before, never deleted — re-running
    an old payroll period must still resolve the pay that applied back then.
    """
    if not components:
        raise PeopleError("A salary structure needs at least one component.")

    previous = current_salary_structure(employee, effective_from)
    if previous and previous.effective_from == effective_from:
        raise PeopleError(f"{employee} already has a salary structure effective {effective_from}.")
    if previous:
        previous.effective_to = effective_from - timedelta(days=1)
        previous.is_active = False
        previous.save(update_fields=["effective_to", "is_active"])

    structure = SalaryStructure.objects.create(
        employee=employee,
        contract=EmploymentContract.objects.filter(employee=employee, is_current=True).first(),
        effective_from=effective_from,
        note=note,
        created_by=user,
    )
    for index, component in enumerate(components):
        SalaryComponent.objects.create(
            structure=structure,
            code=component.get("code", SalaryComponent.Code.BASIC),
            label=component.get("label", ""),
            amount=Decimal(str(component.get("amount", 0))),
            is_taxable=bool(component.get("is_taxable", True)),
            in_pension_base=bool(component.get("in_pension_base", True)),
            # Transport is pensionable but sits outside the maternity base.
            in_maternity_base=bool(
                component.get(
                    "in_maternity_base",
                    component.get("code") != SalaryComponent.Code.TRANSPORT,
                )
            ),
            is_prorated=bool(component.get("is_prorated", True)),
            sort_order=index,
        )

    SalaryRevision.objects.create(
        employee=employee,
        previous_structure=previous,
        new_structure=structure,
        effective_date=effective_from,
        reason=reason,
        previous_gross=previous.gross if previous else ZERO,
        new_gross=structure.gross,
        note=note,
        approved_by=user,
        approved_at=timezone.now(),
    )
    # `base_salary` stays the headline number the older screens and the payroll
    # engine read until they move onto components.
    employee.base_salary = structure.gross
    employee.save(update_fields=["base_salary", "updated_at"])
    record_audit(
        action="SALARY_REVISED",
        user=user,
        organization=employee.organization,
        entity_type="salary_structure",
        entity_id=str(structure.pk),
        changes={
            "employee": str(employee),
            "from": str(previous.gross if previous else 0),
            "to": str(structure.gross),
            "effective": str(effective_from),
        },
    )
    return structure


def current_salary_structure(employee: Employee, on: date | None = None) -> SalaryStructure | None:
    """The structure in force on a day — what payroll must resolve against."""
    day = on or timezone.localdate()
    for structure in employee.salary_structures.prefetch_related("components").all():
        if structure.covers(day):
            return structure
    return None


# ---------------------------------------------------------------------------
# Leave
# ---------------------------------------------------------------------------


def seed_default_leave_types(organization: Organization) -> list[LeaveType]:
    """Rwanda Labour Code defaults, created once per organization."""
    defaults = [
        # code, name, days, accrual, paid, carry-over, doc, gender
        ("ANNUAL", "Annual leave", 18, LeaveType.Accrual.MONTHLY, True, 6, False, ""),
        ("SICK", "Sick leave", 15, LeaveType.Accrual.ANNUAL, True, 0, True, ""),
        ("MATERNITY", "Maternity leave", 84, LeaveType.Accrual.NONE, True, 0, True, "F"),
        ("PATERNITY", "Paternity leave", 4, LeaveType.Accrual.NONE, True, 0, False, "M"),
        ("CIRCUMSTANTIAL", "Circumstantial leave", 6, LeaveType.Accrual.ANNUAL, True, 0, False, ""),
        ("UNPAID", "Unpaid leave", 0, LeaveType.Accrual.NONE, False, 0, False, ""),
    ]
    created: list[LeaveType] = []
    for code, name, days, accrual, paid, carry, doc, gender in defaults:
        leave_type, _ = LeaveType.objects.get_or_create(
            organization=organization,
            code=code,
            defaults={
                "name": name,
                "days_per_year": days,
                "accrual": accrual,
                "is_paid": paid,
                "carry_over_max_days": carry,
                "requires_document": doc,
                "gender_restriction": gender,
                "is_encashable": code == "ANNUAL",
            },
        )
        created.append(leave_type)
    return created


def ensure_leave_balance(
    employee: Employee, leave_type: LeaveType, year: int | None = None
) -> LeaveBalance:
    year = year or timezone.localdate().year
    balance, created = LeaveBalance.objects.get_or_create(
        employee=employee, leave_type=leave_type, year=year
    )
    if created and leave_type.accrual == LeaveType.Accrual.ANNUAL:
        balance.accrued = leave_type.days_per_year
        balance.save(update_fields=["accrued"])
        LeaveAccrual.objects.create(
            balance=balance,
            kind=LeaveAccrual.Kind.GRANT,
            days=leave_type.days_per_year,
            note=f"{year} annual entitlement",
        )
    return balance


@transaction.atomic
def accrue_monthly_leave(
    *, organization: Organization, up_to: date | None = None, user: User | None = None
) -> int:
    """Post one month's accrual for every active employee on monthly-accrual types.

    Idempotent per (balance, month): re-running the same month adds nothing.
    """
    day = up_to or timezone.localdate()
    posted = 0
    types = LeaveType.objects.filter(
        organization=organization, is_active=True, accrual=LeaveType.Accrual.MONTHLY
    )
    employees = Employee.objects.filter(
        organization=organization,
        employment_status__in=[Employee.Status.ACTIVE, Employee.Status.PROBATION],
    )
    period_note = day.strftime("%Y-%m")
    for employee in employees:
        for leave_type in types:
            balance = ensure_leave_balance(employee, leave_type, day.year)
            if balance.movements.filter(kind=LeaveAccrual.Kind.ACCRUAL, note=period_note).exists():
                continue
            monthly = _q(Decimal(leave_type.days_per_year) / Decimal("12"))
            balance.accrued = balance.accrued + monthly
            balance.save(update_fields=["accrued", "updated_at"])
            LeaveAccrual.objects.create(
                balance=balance,
                kind=LeaveAccrual.Kind.ACCRUAL,
                days=monthly,
                occurred_on=day,
                note=period_note,
                created_by=user,
            )
            posted += 1
    return posted


def working_days(start: date, end: date) -> int:
    """Mon–Sat working days, per the Rwandan 6-day working week."""
    if end < start:
        return 0
    days = 0
    cursor = start
    while cursor <= end:
        if cursor.weekday() != 6:  # Sunday
            days += 1
        cursor += timedelta(days=1)
    return days


@transaction.atomic
def request_leave(
    *,
    employee: Employee,
    leave_type: LeaveType,
    start_date: date,
    end_date: date,
    reason: str = "",
    user: User | None = None,
) -> LeaveRequest:
    """Book leave against a real balance, holding the days as ``pending``."""
    if end_date < start_date:
        raise PeopleError("Leave cannot end before it starts.")
    if (
        leave_type.gender_restriction
        and employee.gender
        and (employee.gender.upper()[:1] != leave_type.gender_restriction.upper()[:1])
    ):
        raise PeopleError(f"{leave_type.name} does not apply to this employee.")

    days = Decimal(working_days(start_date, end_date))
    if leave_type.max_consecutive_days and days > leave_type.max_consecutive_days:
        raise PeopleError(
            f"{leave_type.name} is capped at {leave_type.max_consecutive_days} consecutive days."
        )

    overlap = LeaveRequest.objects.filter(
        employee=employee,
        status__in=[LeaveRequest.Status.PENDING, LeaveRequest.Status.APPROVED],
        start_date__lte=end_date,
        end_date__gte=start_date,
    ).exists()
    if overlap:
        raise PeopleError("This employee already has leave booked over those dates.")

    balance = ensure_leave_balance(employee, leave_type, start_date.year)
    if leave_type.is_paid and days > balance.available:
        raise PeopleError(
            f"Only {balance.available} day(s) of {leave_type.name} remain — {days} requested."
        )

    # LeaveRequest still carries the legacy fixed choice list; fall back to ANNUAL
    # for org-defined types that have no legacy equivalent.
    legacy_codes = dict(LeaveRequest.LeaveType.choices)
    request = LeaveRequest.objects.create(
        employee=employee,
        leave_type=(
            leave_type.code if leave_type.code in legacy_codes else LeaveRequest.LeaveType.ANNUAL
        ),
        start_date=start_date,
        end_date=end_date,
        days_count=int(days),
        reason=reason,
    )
    balance.pending = balance.pending + days
    balance.save(update_fields=["pending", "updated_at"])
    LeaveAccrual.objects.create(
        balance=balance,
        kind=LeaveAccrual.Kind.ADJUSTMENT,
        days=ZERO,
        occurred_on=start_date,
        leave_request=request,
        note=f"Held {days} day(s) pending approval",
        created_by=user,
    )
    return request


@transaction.atomic
def decide_leave(
    *, request: LeaveRequest, approve: bool, user: User, note: str = ""
) -> LeaveRequest:
    """Approve or reject, releasing or converting the held days."""
    if request.status != LeaveRequest.Status.PENDING:
        raise PeopleError("This leave request has already been decided.")
    if request.employee.user_id == user.pk:
        raise PeopleError("You cannot decide your own leave request (no self-approval).")

    leave_type = LeaveType.objects.filter(
        organization=request.employee.organization, code=request.leave_type
    ).first()
    days = Decimal(request.days_count)
    if leave_type:
        balance = ensure_leave_balance(request.employee, leave_type, request.start_date.year)
        balance.pending = max(ZERO, balance.pending - days)
        if approve:
            balance.taken = balance.taken + days
        balance.save(update_fields=["pending", "taken", "updated_at"])
        LeaveAccrual.objects.create(
            balance=balance,
            kind=LeaveAccrual.Kind.TAKEN if approve else LeaveAccrual.Kind.ADJUSTMENT,
            days=-days if approve else ZERO,
            occurred_on=request.start_date,
            leave_request=request,
            note=note or ("Approved" if approve else "Rejected — hold released"),
            created_by=user,
        )

    request.status = LeaveRequest.Status.APPROVED if approve else LeaveRequest.Status.REJECTED
    request.approved_by = user
    request.save(update_fields=["status", "approved_by"])
    record_audit(
        action="LEAVE_APPROVED" if approve else "LEAVE_REJECTED",
        user=user,
        organization=request.employee.organization,
        entity_type="leave_request",
        entity_id=str(request.pk),
        changes={"employee": str(request.employee), "days": request.days_count},
    )
    return request


# ---------------------------------------------------------------------------
# Timesheets
# ---------------------------------------------------------------------------


@transaction.atomic
def build_timesheet(
    *,
    employee: Employee,
    period_start: date,
    period_end: date,
    user: User | None = None,
) -> Timesheet:
    """Derive the period's timesheet from attendance, roster and approved leave.

    Overtime is hours worked beyond what was rostered — computed here rather
    than typed by anyone, which is the point of clocking in.
    """
    if period_end < period_start:
        raise PeopleError("A timesheet period cannot end before it starts.")

    logs = AttendanceLog.objects.filter(
        employee=employee, date__gte=period_start, date__lte=period_end
    )
    rostered_shifts = ShiftRoster.objects.filter(
        employee=employee, date__gte=period_start, date__lte=period_end
    ).count()

    worked = absent = on_leave = ZERO
    hours = overtime = night = ZERO
    late = 0
    for log in logs:
        if log.status == AttendanceLog.Status.ABSENT:
            absent += 1
            continue
        if log.status == AttendanceLog.Status.ON_LEAVE:
            on_leave += 1
            continue
        worked += 1
        if log.status == AttendanceLog.Status.LATE:
            late += 1
        if log.clock_in and log.clock_out:
            span = Decimal((log.clock_out - log.clock_in).total_seconds()) / Decimal("3600")
            hours += _q(span)
            if log.clock_out.hour >= 22 or log.clock_out.hour < 6:
                night += _q(span)
        overtime += Decimal(log.overtime_hours or 0)

    unpaid = ZERO
    unpaid_type = LeaveType.objects.filter(
        organization=employee.organization, code="UNPAID"
    ).first()
    if unpaid_type:
        unpaid = Decimal(
            LeaveRequest.objects.filter(
                employee=employee,
                status=LeaveRequest.Status.APPROVED,
                start_date__lte=period_end,
                end_date__gte=period_start,
                leave_type=LeaveRequest.LeaveType.CASUAL,
            ).aggregate(total=Sum("days_count"))["total"]
            or 0
        )

    timesheet, _ = Timesheet.objects.update_or_create(
        employee=employee,
        period_start=period_start,
        period_end=period_end,
        defaults={
            "days_worked": worked,
            "days_absent": absent,
            "days_on_leave": on_leave,
            "unpaid_leave_days": unpaid,
            "hours_worked": _q(hours),
            "hours_rostered": _q(Decimal(rostered_shifts) * Decimal("8")),
            "overtime_hours": _q(overtime),
            "night_hours": _q(night),
            "late_count": late,
            "status": Timesheet.Status.DRAFT,
        },
    )
    return timesheet


@transaction.atomic
def decide_timesheet(
    *, timesheet: Timesheet, approve: bool, user: User, reason: str = ""
) -> Timesheet:
    if timesheet.status in {Timesheet.Status.APPROVED, Timesheet.Status.LOCKED}:
        raise PeopleError("This timesheet is already approved.")
    if timesheet.employee.user_id == user.pk:
        raise PeopleError("You cannot approve your own timesheet.")
    timesheet.status = Timesheet.Status.APPROVED if approve else Timesheet.Status.REJECTED
    timesheet.approved_by = user
    timesheet.approved_at = timezone.now()
    timesheet.rejection_reason = "" if approve else reason
    timesheet.save(
        update_fields=["status", "approved_by", "approved_at", "rejection_reason", "updated_at"]
    )
    return timesheet


def assert_timesheets_ready(run: PayrollRun) -> None:
    """ROADMAP invariant: a run cannot be approved while a timesheet is pending."""
    pending = Timesheet.objects.filter(
        employee__organization=run.organization,
        period_start__gte=run.period_start,
        period_end__lte=run.period_end,
        status__in=[Timesheet.Status.DRAFT, Timesheet.Status.SUBMITTED],
    ).count()
    if pending:
        raise PeopleError(
            f"{pending} timesheet(s) for this period are still unapproved — "
            "approve them before the payroll run."
        )


# ---------------------------------------------------------------------------
# Loans & advances
# ---------------------------------------------------------------------------


@transaction.atomic
def create_loan(
    *,
    employee: Employee,
    principal: Decimal,
    installments_count: int,
    kind: str = LoanAdvance.Kind.SALARY_ADVANCE,
    interest_rate_pct: Decimal = ZERO,
    start_date: date | None = None,
    reason: str = "",
    user: User | None = None,
) -> LoanAdvance:
    """Raise a loan and lay out its repayment schedule up front."""
    if principal <= 0:
        raise PeopleError("A loan principal must be positive.")
    if installments_count < 1:
        raise PeopleError("A loan needs at least one installment.")

    start = start_date or timezone.localdate()
    total = principal + (principal * Decimal(interest_rate_pct) / Decimal("100"))
    monthly = _q(total / Decimal(installments_count))

    loan = LoanAdvance.objects.create(
        employee=employee,
        kind=kind,
        principal=principal,
        interest_rate_pct=interest_rate_pct,
        balance=_q(total),
        monthly_installment=monthly,
        installments_count=installments_count,
        start_date=start,
        reason=reason,
        created_by=user,
    )
    running = ZERO
    for seq in range(1, installments_count + 1):
        due = start + timedelta(days=30 * (seq - 1))
        # The final installment absorbs the rounding remainder.
        amount = _q(total - running) if seq == installments_count else monthly
        running += amount
        LoanInstallment.objects.create(loan=loan, sequence=seq, due_date=due, amount=amount)
    loan.end_date = start + timedelta(days=30 * (installments_count - 1))
    loan.save(update_fields=["end_date"])
    return loan


@transaction.atomic
def approve_loan(*, loan: LoanAdvance, user: User) -> LoanAdvance:
    if loan.status not in {LoanAdvance.Status.DRAFT, LoanAdvance.Status.PENDING_APPROVAL}:
        raise PeopleError("Only a draft or pending loan can be approved.")
    if loan.employee.user_id == user.pk:
        raise PeopleError("You cannot approve your own loan (no self-approval).")
    loan.status = LoanAdvance.Status.ACTIVE
    loan.approved_by = user
    loan.approved_at = timezone.now()
    loan.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    record_audit(
        action="LOAN_APPROVED",
        user=user,
        organization=loan.employee.organization,
        entity_type="loan_advance",
        entity_id=str(loan.pk),
        changes={"employee": str(loan.employee), "principal": str(loan.principal)},
    )
    return loan


@transaction.atomic
def settle_due_installments(
    *, run: PayrollRun, skip_unpaid_leave: bool = True
) -> dict[int, Decimal]:
    """Deduct each employee's next due installment for this payroll period.

    Returns ``{employee_id: amount}`` so the payroll engine can put it on the
    payslip. An employee on unpaid leave for the period is skipped, not charged —
    the installment stays open and rolls to the next run.
    """
    deductions: dict[int, Decimal] = {}
    loans = LoanAdvance.objects.filter(
        employee__organization=run.organization, status=LoanAdvance.Status.ACTIVE
    ).select_related("employee")

    for loan in loans:
        installment = (
            loan.installments.filter(is_paid=False, due_date__lte=run.period_end)
            .order_by("sequence")
            .first()
        )
        if installment is None:
            continue
        if skip_unpaid_leave:
            timesheet = Timesheet.objects.filter(
                employee=loan.employee,
                period_start__gte=run.period_start,
                period_end__lte=run.period_end,
            ).first()
            if timesheet and timesheet.unpaid_leave_days > 0:
                installment.skipped_reason = "Unpaid leave in this period"
                installment.save(update_fields=["skipped_reason"])
                continue

        amount = min(installment.amount, loan.balance)
        installment.amount_paid = amount
        installment.is_paid = True
        installment.payroll_run = run
        installment.paid_at = timezone.now()
        installment.save(update_fields=["amount_paid", "is_paid", "payroll_run", "paid_at"])
        loan.balance = _q(loan.balance - amount)
        if loan.balance <= 0:
            loan.balance = ZERO
            loan.status = LoanAdvance.Status.SETTLED
        loan.save(update_fields=["balance", "status", "updated_at"])
        deductions[loan.employee_id] = deductions.get(loan.employee_id, ZERO) + amount

    return deductions


# ---------------------------------------------------------------------------
# Recruitment → onboarding
# ---------------------------------------------------------------------------

DEFAULT_ONBOARDING_ITEMS: list[tuple[str, str, bool]] = [
    ("Signed employment contract on file", ChecklistItem.Category.DOCUMENT, True),
    ("National ID / passport copy", ChecklistItem.Category.DOCUMENT, True),
    ("Professional licence verified (NPC)", ChecklistItem.Category.COMPLIANCE, False),
    ("RSSB number captured", ChecklistItem.Category.COMPLIANCE, True),
    ("Bank / MoMo details captured", ChecklistItem.Category.FINANCE, True),
    ("System login provisioned (PF number)", ChecklistItem.Category.ACCESS, True),
    ("Uniform & badge issued", ChecklistItem.Category.ASSET, False),
    ("SOP pack acknowledged", ChecklistItem.Category.TRAINING, True),
    ("GDP & data-protection induction", ChecklistItem.Category.TRAINING, True),
]

DEFAULT_CLEARANCE_ITEMS: list[tuple[str, str, bool]] = [
    ("Return uniform & badge", ChecklistItem.Category.ASSET, True),
    ("Return keys / CD safe access", ChecklistItem.Category.ASSET, True),
    ("Return laptop / device", ChecklistItem.Category.ASSET, False),
    ("System access revoked", ChecklistItem.Category.ACCESS, True),
    ("Handover completed", ChecklistItem.Category.OTHER, True),
    ("Outstanding loans settled", ChecklistItem.Category.FINANCE, True),
    ("Final payslip issued", ChecklistItem.Category.FINANCE, True),
    ("Certificate of service issued", ChecklistItem.Category.DOCUMENT, True),
]


@transaction.atomic
def start_onboarding(*, employee: Employee, user: User | None = None) -> OnboardingChecklist:
    checklist, created = OnboardingChecklist.objects.get_or_create(
        employee=employee,
        defaults={"target_completion": timezone.localdate() + timedelta(days=14)},
    )
    if created:
        for order, (label, category, mandatory) in enumerate(DEFAULT_ONBOARDING_ITEMS):
            ChecklistItem.objects.create(
                onboarding=checklist,
                phase=ChecklistItem.Phase.ONBOARDING,
                category=category,
                label=label,
                is_mandatory=mandatory,
                sort_order=order,
            )
    return checklist


@transaction.atomic
def hire_applicant(
    *,
    applicant: Applicant,
    organization: Organization,
    hire_date: date,
    user: User | None = None,
) -> Employee:
    """Turn a successful applicant into an employee, contract and onboarding."""
    if applicant.stage == Applicant.Stage.HIRED:
        raise PeopleError("This applicant has already been hired.")
    if applicant.hired_employee_id:
        raise PeopleError("This applicant is already linked to an employee record.")

    employee = Employee.objects.create(
        organization=organization,
        first_name=applicant.first_name,
        last_name=applicant.last_name,
        national_id=applicant.national_id,
        gender=applicant.gender,
        personal_email=applicant.email,
        personal_phone=applicant.phone,
        job_title=applicant.requisition.job_title,
        hire_date=hire_date,
        employment_status=Employee.Status.PROBATION,
        base_salary=applicant.offered_salary or ZERO,
    )
    issue_contract(
        employee=employee,
        kind=EmploymentContract.Kind.PERMANENT,
        job_title=applicant.requisition.job_title,
        start_date=hire_date,
        user=user,
        department=applicant.requisition.department,
    )
    if applicant.offered_salary:
        set_salary_structure(
            employee=employee,
            effective_from=hire_date,
            components=[{"code": SalaryComponent.Code.BASIC, "amount": applicant.offered_salary}],
            reason=SalaryRevision.Reason.OTHER,
            note="Opening salary from offer",
            user=user,
        )
    start_onboarding(employee=employee, user=user)

    applicant.stage = Applicant.Stage.HIRED
    applicant.hired_employee = employee
    applicant.save(update_fields=["stage", "hired_employee", "updated_at"])
    requisition = applicant.requisition
    requisition.headcount_filled += 1
    if requisition.headcount_filled >= requisition.headcount:
        requisition.status = requisition.Status.FILLED
    requisition.save(update_fields=["headcount_filled", "status", "updated_at"])

    record_audit(
        action="APPLICANT_HIRED",
        user=user,
        organization=organization,
        entity_type="employee",
        entity_id=str(employee.pk),
        changes={"applicant": applicant.full_name, "requisition": requisition.reference},
    )
    return employee


# ---------------------------------------------------------------------------
# Offboarding
# ---------------------------------------------------------------------------


@transaction.atomic
def initiate_termination(
    *,
    employee: Employee,
    reason: str,
    last_working_day: date,
    user: User | None = None,
    **fields: Any,
) -> Termination:
    """Open an exit, with the clearance checklist ready.

    Blocked while an open payroll run still references the employee — otherwise
    the run and the final settlement would both try to pay the same days.
    """
    open_run = PayrollRun.objects.filter(
        organization=employee.organization,
        status__in=[PayrollRun.Status.DRAFT, PayrollRun.Status.PENDING_APPROVAL],
        records__employee=employee,
    ).exists()
    if open_run:
        raise PeopleError(
            "This employee is on an open payroll run — approve or discard it before terminating."
        )
    if hasattr(employee, "termination"):
        raise PeopleError("A termination already exists for this employee.")

    termination = Termination.objects.create(
        employee=employee,
        reason=reason,
        last_working_day=last_working_day,
        initiated_by=user,
        **fields,
    )
    for order, (label, category, mandatory) in enumerate(DEFAULT_CLEARANCE_ITEMS):
        ChecklistItem.objects.create(
            termination=termination,
            phase=ChecklistItem.Phase.CLEARANCE,
            category=category,
            label=label,
            is_mandatory=mandatory,
            sort_order=order,
        )
    return termination


@transaction.atomic
def compute_final_settlement(
    *, termination: Termination, user: User | None = None
) -> FinalSettlement:
    """Work out what is owed on exit: pro-rata pay, encashed leave, less loans."""
    employee = termination.employee
    last_day = termination.last_working_day
    structure = current_salary_structure(employee, last_day)
    monthly = structure.gross if structure else employee.base_salary

    days_in_month = 30
    worked_days = min(last_day.day, days_in_month)
    pro_rata = _q(Decimal(monthly) * Decimal(worked_days) / Decimal(days_in_month))

    encashable_days = ZERO
    for balance in employee.leave_balances.select_related("leave_type").filter(year=last_day.year):
        if balance.leave_type.is_encashable:
            encashable_days += max(ZERO, balance.available)
    daily_rate = _q(Decimal(monthly) / Decimal(days_in_month))
    encashment = _q(encashable_days * daily_rate)

    loan_balance = _q(
        LoanAdvance.objects.filter(employee=employee, status=LoanAdvance.Status.ACTIVE).aggregate(
            total=Sum("balance")
        )["total"]
        or ZERO
    )

    notice_pay = (
        ZERO if termination.notice_period_served else _q(termination.notice_pay_in_lieu or ZERO)
    )

    settlement, _ = FinalSettlement.objects.update_or_create(
        termination=termination,
        defaults={
            "pro_rata_salary": pro_rata,
            "leave_days_encashed": encashable_days,
            "leave_encashment": encashment,
            "notice_pay": notice_pay,
            "loan_recovery": loan_balance,
            "computed_on": timezone.localdate(),
        },
    )
    settlement.net_payable = _q(settlement.gross_dues - settlement.total_deductions)
    settlement.save(update_fields=["net_payable"])
    return settlement


@transaction.atomic
def approve_termination(*, termination: Termination, user: User) -> Termination:
    """Approve the exit: compute the settlement and de-provision the login."""
    if termination.status == Termination.Status.APPROVED:
        raise PeopleError("This termination is already approved.")
    if termination.employee.user_id == user.pk:
        raise PeopleError("You cannot approve your own termination.")

    termination.status = Termination.Status.APPROVED
    termination.approved_by = user
    termination.approved_at = timezone.now()
    termination.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])

    compute_final_settlement(termination=termination, user=user)

    employee = termination.employee
    employee.employment_status = Employee.Status.TERMINATED
    employee.end_date = termination.last_working_day
    employee.termination_reason = termination.reason
    employee.is_eligible_for_rehire = termination.is_eligible_for_rehire
    employee.save(
        update_fields=[
            "employment_status",
            "end_date",
            "termination_reason",
            "is_eligible_for_rehire",
            "updated_at",
        ]
    )
    user_account = employee.user
    if user_account is not None:
        user_account.is_active = False
        user_account.save(update_fields=["is_active"])

    record_audit(
        action="EMPLOYEE_TERMINATED",
        user=user,
        organization=employee.organization,
        entity_type="termination",
        entity_id=str(termination.pk),
        changes={"employee": str(employee), "reason": termination.reason},
    )
    return termination


# ---------------------------------------------------------------------------
# Compliance gates
# ---------------------------------------------------------------------------


def has_valid_competency(employee: Employee, competency: str) -> bool:
    return any(
        assessment.is_valid for assessment in employee.competencies.filter(competency=competency)
    )


def assert_can_handle_controlled(employee: Employee) -> None:
    """Controlled-drug handling needs a current competency assessment."""
    if not has_valid_competency(employee, CompetencyAssessment.Competency.CONTROLLED_DRUG_HANDLING):
        raise PeopleError(
            f"{employee.full_name} has no current controlled-drug competency assessment."
        )


def compliance_alerts(organization: Organization, within_days: int = 90) -> dict[str, Any]:
    """Everything about to lapse — the People dashboard's warning list."""
    horizon = timezone.localdate() + timedelta(days=within_days)
    employees = Employee.objects.filter(organization=organization).exclude(
        employment_status=Employee.Status.TERMINATED
    )
    return {
        "contracts_expiring": list(
            EmploymentContract.objects.filter(
                employee__organization=organization,
                is_current=True,
                end_date__isnull=False,
                end_date__lte=horizon,
            ).values("employee__id", "employee__first_name", "employee__last_name", "end_date")
        ),
        "work_permits_expiring": list(
            employees.filter(
                work_permit_expiry__isnull=False, work_permit_expiry__lte=horizon
            ).values("id", "first_name", "last_name", "work_permit_expiry")
        ),
        "probations_ending": list(
            employees.filter(
                employment_status=Employee.Status.PROBATION,
                probation_end__isnull=False,
                probation_end__lte=horizon,
            ).values("id", "first_name", "last_name", "probation_end")
        ),
        "competencies_expiring": list(
            CompetencyAssessment.objects.filter(
                employee__organization=organization,
                valid_until__isnull=False,
                valid_until__lte=horizon,
            ).values("employee__id", "competency", "valid_until")
        ),
        "loans_overdue": LoanInstallment.objects.filter(
            loan__employee__organization=organization,
            is_paid=False,
            due_date__lt=timezone.localdate(),
        ).count(),
    }
