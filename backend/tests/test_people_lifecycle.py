"""People (§10) — contracts, pay structure, leave, timesheets, loans, the hiring
and exit lifecycle, compliance records and statutory filings.

The tests are written around the invariants rather than the CRUD: leave must be
held against a real balance, payroll must read an approved timesheet, a loan
installment must be settled once, and nobody approves their own anything.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from apps.hr import services_people as people
from apps.hr.models import (
    Applicant,
    AttendanceLog,
    CompetencyAssessment,
    Employee,
    EmploymentContract,
    JobRequisition,
    LeaveBalance,
    LeaveType,
    LoanAdvance,
    PayrollRun,
    SalaryComponent,
    StatutoryFiling,
    Termination,
    Timesheet,
)
from apps.iam.models import Organization, Role, User
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def _auth(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def org(db: None) -> Organization:
    return Organization.objects.create(name="Kigali Pharmacy", type="RETAIL")


@pytest.fixture
def hr(org: Organization) -> User:
    user = User.objects.create_user(username="hrmanager", password="x", organization=org)
    user.roles.add(Role.objects.get(code="HR_MANAGER"))
    return user


@pytest.fixture
def boss(org: Organization) -> User:
    user = User.objects.create_user(username="director", password="x", organization=org)
    user.roles.add(Role.objects.get(code="ORG_ADMIN"))
    return user


@pytest.fixture
def employee(org: Organization) -> Employee:
    return Employee.objects.create(
        organization=org,
        employee_number="PF-0001",
        first_name="Aline",
        last_name="Uwase",
        job_title="Pharmacist",
        hire_date=date(2025, 1, 15),
        base_salary=Decimal("600000"),
        gender="F",
    )


@pytest.fixture
def leave_types(org: Organization) -> list[LeaveType]:
    return people.seed_default_leave_types(org)


# ---------------------------------------------------------------------------
# Contracts & salary structure
# ---------------------------------------------------------------------------


def test_issuing_a_contract_supersedes_the_previous_one(employee: Employee, hr: User) -> None:
    first = people.issue_contract(
        employee=employee,
        kind=EmploymentContract.Kind.FIXED_TERM,
        job_title="Pharmacy technician",
        start_date=date(2025, 1, 15),
        user=hr,
        end_date=date(2025, 12, 31),
    )
    second = people.issue_contract(
        employee=employee,
        kind=EmploymentContract.Kind.PERMANENT,
        job_title="Pharmacist",
        start_date=date(2026, 1, 1),
        user=hr,
    )
    first.refresh_from_db()
    assert first.is_current is False
    assert first.status == EmploymentContract.Status.RENEWED
    assert second.is_current is True
    # Only one contract may be current — the DB constraint backs this up.
    assert EmploymentContract.objects.filter(employee=employee, is_current=True).count() == 1
    employee.refresh_from_db()
    assert employee.job_title == "Pharmacist"


def test_salary_structure_splits_the_statutory_bases(employee: Employee, hr: User) -> None:
    """Transport is pensionable but sits outside the maternity base — the whole
    reason components exist rather than one `base_salary` number."""
    structure = people.set_salary_structure(
        employee=employee,
        effective_from=date(2026, 1, 1),
        components=[
            {"code": SalaryComponent.Code.BASIC, "amount": "500000"},
            {"code": SalaryComponent.Code.HOUSING, "amount": "80000"},
            {"code": SalaryComponent.Code.TRANSPORT, "amount": "60000"},
        ],
        user=hr,
    )
    assert structure.gross == Decimal("640000")
    assert structure.pension_base == Decimal("640000")  # includes transport
    assert structure.maternity_base == Decimal("580000")  # excludes transport
    employee.refresh_from_db()
    assert employee.base_salary == Decimal("640000")


def test_a_raise_closes_the_old_structure_and_logs_a_revision(employee: Employee, hr: User) -> None:
    people.set_salary_structure(
        employee=employee,
        effective_from=date(2026, 1, 1),
        components=[{"code": SalaryComponent.Code.BASIC, "amount": "500000"}],
        user=hr,
    )
    people.set_salary_structure(
        employee=employee,
        effective_from=date(2026, 7, 1),
        components=[{"code": SalaryComponent.Code.BASIC, "amount": "600000"}],
        reason="PROMOTION",
        user=hr,
    )
    old = employee.salary_structures.order_by("effective_from").first()
    assert old.effective_to == date(2026, 6, 30)
    assert old.is_active is False

    revision = employee.salary_revisions.order_by("-effective_date").first()
    assert revision.previous_gross == Decimal("500000")
    assert revision.new_gross == Decimal("600000")
    assert revision.change_pct == Decimal("20.00")

    # History still resolves: June pays the old rate, July the new one.
    assert people.current_salary_structure(employee, date(2026, 6, 15)).gross == Decimal("500000")
    assert people.current_salary_structure(employee, date(2026, 7, 15)).gross == Decimal("600000")


# ---------------------------------------------------------------------------
# Leave
# ---------------------------------------------------------------------------


def test_leave_is_held_against_a_real_balance(
    employee: Employee, leave_types: list[LeaveType], hr: User
) -> None:
    annual = next(t for t in leave_types if t.code == "ANNUAL")
    balance = people.ensure_leave_balance(employee, annual, 2026)
    balance.accrued = Decimal("18")
    balance.save(update_fields=["accrued"])

    request = people.request_leave(
        employee=employee,
        leave_type=annual,
        start_date=date(2026, 3, 2),
        end_date=date(2026, 3, 6),
        user=hr,
    )
    balance.refresh_from_db()
    # Mon–Fri = 5 working days, held as pending (not yet taken).
    assert request.days_count == 5
    assert balance.pending == Decimal("5")
    assert balance.taken == Decimal("0")
    assert balance.available == Decimal("13")

    people.decide_leave(request=request, approve=True, user=hr)
    balance.refresh_from_db()
    assert balance.pending == Decimal("0")
    assert balance.taken == Decimal("5")
    assert balance.available == Decimal("13")


def test_leave_beyond_the_balance_is_refused(
    employee: Employee, leave_types: list[LeaveType], hr: User
) -> None:
    annual = next(t for t in leave_types if t.code == "ANNUAL")
    people.ensure_leave_balance(employee, annual, 2026)  # 0 accrued
    with pytest.raises(people.PeopleError, match="remain"):
        people.request_leave(
            employee=employee,
            leave_type=annual,
            start_date=date(2026, 3, 2),
            end_date=date(2026, 3, 6),
            user=hr,
        )


def test_overlapping_leave_is_refused(
    employee: Employee, leave_types: list[LeaveType], hr: User
) -> None:
    annual = next(t for t in leave_types if t.code == "ANNUAL")
    balance = people.ensure_leave_balance(employee, annual, 2026)
    balance.accrued = Decimal("18")
    balance.save(update_fields=["accrued"])
    people.request_leave(
        employee=employee,
        leave_type=annual,
        start_date=date(2026, 3, 2),
        end_date=date(2026, 3, 6),
        user=hr,
    )
    with pytest.raises(people.PeopleError, match="already has leave"):
        people.request_leave(
            employee=employee,
            leave_type=annual,
            start_date=date(2026, 3, 4),
            end_date=date(2026, 3, 10),
            user=hr,
        )


def test_rejecting_leave_releases_the_hold(
    employee: Employee, leave_types: list[LeaveType], hr: User
) -> None:
    annual = next(t for t in leave_types if t.code == "ANNUAL")
    balance = people.ensure_leave_balance(employee, annual, 2026)
    balance.accrued = Decimal("18")
    balance.save(update_fields=["accrued"])
    request = people.request_leave(
        employee=employee,
        leave_type=annual,
        start_date=date(2026, 3, 2),
        end_date=date(2026, 3, 6),
        user=hr,
    )
    people.decide_leave(request=request, approve=False, user=hr, note="Cover needed")
    balance.refresh_from_db()
    assert balance.pending == Decimal("0")
    assert balance.taken == Decimal("0")
    assert balance.available == Decimal("18")


def test_paternity_leave_does_not_apply_to_a_female_employee(
    employee: Employee, leave_types: list[LeaveType], hr: User
) -> None:
    paternity = next(t for t in leave_types if t.code == "PATERNITY")
    with pytest.raises(people.PeopleError, match="does not apply"):
        people.request_leave(
            employee=employee,
            leave_type=paternity,
            start_date=date(2026, 3, 2),
            end_date=date(2026, 3, 5),
            user=hr,
        )


def test_monthly_accrual_is_idempotent(
    org: Organization, employee: Employee, leave_types: list[LeaveType], hr: User
) -> None:
    employee.employment_status = Employee.Status.ACTIVE
    employee.save(update_fields=["employment_status"])
    first = people.accrue_monthly_leave(organization=org, up_to=date(2026, 3, 31), user=hr)
    second = people.accrue_monthly_leave(organization=org, up_to=date(2026, 3, 31), user=hr)
    assert first > 0
    assert second == 0  # same month, nothing added twice

    annual = next(t for t in leave_types if t.code == "ANNUAL")
    balance = LeaveBalance.objects.get(employee=employee, leave_type=annual, year=2026)
    assert balance.accrued == Decimal("1.50")  # 18 / 12


# ---------------------------------------------------------------------------
# Timesheets
# ---------------------------------------------------------------------------


def test_timesheet_derives_hours_and_overtime_from_attendance(employee: Employee, hr: User) -> None:
    from django.utils import timezone

    for day in (1, 2, 3):
        start = timezone.make_aware(timezone.datetime(2026, 6, day, 8, 0))
        AttendanceLog.objects.create(
            employee=employee,
            date=date(2026, 6, day),
            clock_in=start,
            clock_out=start + timedelta(hours=9),
            overtime_hours=Decimal("1.00"),
            status=AttendanceLog.Status.LATE if day == 2 else AttendanceLog.Status.PRESENT,
        )
    AttendanceLog.objects.create(
        employee=employee, date=date(2026, 6, 4), status=AttendanceLog.Status.ABSENT
    )

    timesheet = people.build_timesheet(
        employee=employee, period_start=date(2026, 6, 1), period_end=date(2026, 6, 30)
    )
    assert timesheet.days_worked == Decimal("3.00")
    assert timesheet.days_absent == Decimal("1.00")
    assert timesheet.hours_worked == Decimal("27.00")
    assert timesheet.overtime_hours == Decimal("3.00")
    assert timesheet.late_count == 1
    assert timesheet.status == Timesheet.Status.DRAFT


def test_nobody_approves_their_own_timesheet(employee: Employee, hr: User) -> None:
    employee.user = hr
    employee.save(update_fields=["user"])
    timesheet = people.build_timesheet(
        employee=employee, period_start=date(2026, 6, 1), period_end=date(2026, 6, 30)
    )
    with pytest.raises(people.PeopleError, match="your own timesheet"):
        people.decide_timesheet(timesheet=timesheet, approve=True, user=hr)


def test_payroll_is_blocked_while_a_timesheet_is_pending(
    org: Organization, employee: Employee, hr: User
) -> None:
    people.build_timesheet(
        employee=employee, period_start=date(2026, 6, 1), period_end=date(2026, 6, 30)
    )
    run = PayrollRun.objects.create(
        organization=org, period_start=date(2026, 6, 1), period_end=date(2026, 6, 30)
    )
    with pytest.raises(people.PeopleError, match="still unapproved"):
        people.assert_timesheets_ready(run)

    timesheet = Timesheet.objects.get(employee=employee)
    people.decide_timesheet(timesheet=timesheet, approve=True, user=hr)
    people.assert_timesheets_ready(run)  # now fine


# ---------------------------------------------------------------------------
# Loans
# ---------------------------------------------------------------------------


def test_loan_schedule_ties_exactly_to_the_total(employee: Employee, hr: User) -> None:
    loan = people.create_loan(
        employee=employee,
        principal=Decimal("100000"),
        installments_count=3,
        interest_rate_pct=Decimal("0"),
        user=hr,
    )
    installments = list(loan.installments.all())
    assert len(installments) == 3
    # 100,000 / 3 does not divide evenly — the last installment absorbs the remainder.
    assert sum(i.amount for i in installments) == Decimal("100000.00")
    assert loan.balance == Decimal("100000.00")


def test_payroll_settles_one_installment_and_skips_unpaid_leave(
    org: Organization, employee: Employee, hr: User, boss: User
) -> None:
    loan = people.create_loan(
        employee=employee,
        principal=Decimal("90000"),
        installments_count=3,
        start_date=date(2026, 6, 1),
        user=hr,
    )
    people.approve_loan(loan=loan, user=boss)

    run = PayrollRun.objects.create(
        organization=org, period_start=date(2026, 6, 1), period_end=date(2026, 6, 30)
    )
    deductions = people.settle_due_installments(run=run)
    assert deductions[employee.pk] == Decimal("30000.00")
    loan.refresh_from_db()
    assert loan.balance == Decimal("60000.00")

    # A period with unpaid leave skips the installment rather than charging it.
    timesheet = people.build_timesheet(
        employee=employee, period_start=date(2026, 7, 1), period_end=date(2026, 7, 31)
    )
    timesheet.unpaid_leave_days = Decimal("5")
    timesheet.save(update_fields=["unpaid_leave_days"])
    july = PayrollRun.objects.create(
        organization=org, period_start=date(2026, 7, 1), period_end=date(2026, 7, 31)
    )
    assert people.settle_due_installments(run=july) == {}
    loan.refresh_from_db()
    assert loan.balance == Decimal("60000.00")


def test_a_fully_repaid_loan_settles_itself(employee: Employee, hr: User, boss: User) -> None:
    loan = people.create_loan(
        employee=employee,
        principal=Decimal("30000"),
        installments_count=1,
        start_date=date(2026, 6, 1),
        user=hr,
    )
    people.approve_loan(loan=loan, user=boss)
    run = PayrollRun.objects.create(
        organization=employee.organization,
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 30),
    )
    people.settle_due_installments(run=run)
    loan.refresh_from_db()
    assert loan.balance == Decimal("0.00")
    assert loan.status == LoanAdvance.Status.SETTLED


def test_nobody_approves_their_own_loan(employee: Employee, hr: User) -> None:
    employee.user = hr
    employee.save(update_fields=["user"])
    loan = people.create_loan(
        employee=employee, principal=Decimal("50000"), installments_count=2, user=hr
    )
    with pytest.raises(people.PeopleError, match="your own loan"):
        people.approve_loan(loan=loan, user=hr)


# ---------------------------------------------------------------------------
# Recruitment → onboarding
# ---------------------------------------------------------------------------


def test_hiring_an_applicant_creates_employee_contract_and_onboarding(
    org: Organization, hr: User
) -> None:
    requisition = JobRequisition.objects.create(
        organization=org, job_title="Cashier", headcount=1, status=JobRequisition.Status.OPEN
    )
    applicant = Applicant.objects.create(
        requisition=requisition,
        first_name="Jean",
        last_name="Habimana",
        stage=Applicant.Stage.OFFERED,
        offered_salary=Decimal("300000"),
    )
    employee = people.hire_applicant(
        applicant=applicant, organization=org, hire_date=date(2026, 8, 1), user=hr
    )

    assert employee.job_title == "Cashier"
    assert employee.employment_status == Employee.Status.PROBATION
    assert employee.contracts.filter(is_current=True).exists()
    assert employee.salary_structures.first().gross == Decimal("300000")
    assert employee.onboarding.items.count() > 0
    assert employee.onboarding.progress_pct == Decimal("0.00")

    applicant.refresh_from_db()
    requisition.refresh_from_db()
    assert applicant.stage == Applicant.Stage.HIRED
    assert requisition.headcount_filled == 1
    assert requisition.status == JobRequisition.Status.FILLED


def test_onboarding_progress_tracks_completed_items(employee: Employee, hr: User) -> None:
    checklist = people.start_onboarding(employee=employee, user=hr)
    total = checklist.items.count()
    item = checklist.items.first()
    item.is_done = True
    item.save(update_fields=["is_done"])
    checklist.refresh_from_db()
    expected = (Decimal("1") * 100 / Decimal(total)).quantize(Decimal("0.01"))
    assert checklist.progress_pct == expected


# ---------------------------------------------------------------------------
# Offboarding
# ---------------------------------------------------------------------------


def test_termination_is_blocked_by_an_open_payroll_run(
    org: Organization, employee: Employee, hr: User
) -> None:
    from apps.hr.models import PayrollRecord

    run = PayrollRun.objects.create(
        organization=org, period_start=date(2026, 6, 1), period_end=date(2026, 6, 30)
    )
    PayrollRecord.objects.create(run=run, employee=employee, gross=Decimal("600000"))
    with pytest.raises(people.PeopleError, match="open payroll run"):
        people.initiate_termination(
            employee=employee,
            reason=Termination.Reason.RESIGNATION,
            last_working_day=date(2026, 7, 31),
            user=hr,
        )


def test_termination_settles_leave_and_loans_and_deactivates_the_login(
    org: Organization, employee: Employee, leave_types: list[LeaveType], hr: User, boss: User
) -> None:
    login = User.objects.create_user(username="aline", password="x", organization=org)
    employee.user = login
    employee.base_salary = Decimal("600000")
    employee.save(update_fields=["user", "base_salary"])

    annual = next(t for t in leave_types if t.code == "ANNUAL")
    balance = people.ensure_leave_balance(employee, annual, 2026)
    balance.accrued = Decimal("10")
    balance.save(update_fields=["accrued"])

    loan = people.create_loan(
        employee=employee, principal=Decimal("60000"), installments_count=2, user=hr
    )
    people.approve_loan(loan=loan, user=boss)

    termination = people.initiate_termination(
        employee=employee,
        reason=Termination.Reason.RESIGNATION,
        last_working_day=date(2026, 6, 30),
        user=hr,
    )
    assert termination.items.count() > 0  # clearance checklist laid out

    people.approve_termination(termination=termination, user=boss)
    termination.refresh_from_db()
    settlement = termination.settlement

    # 10 unused days × (600,000 / 30) = 200,000 encashed; 60,000 loan recovered.
    assert settlement.leave_days_encashed == Decimal("10.00")
    assert settlement.leave_encashment == Decimal("200000.00")
    assert settlement.loan_recovery == Decimal("60000.00")
    assert settlement.net_payable == settlement.gross_dues - settlement.total_deductions

    employee.refresh_from_db()
    login.refresh_from_db()
    assert employee.employment_status == Employee.Status.TERMINATED
    assert employee.end_date == date(2026, 6, 30)
    assert login.is_active is False


# ---------------------------------------------------------------------------
# Compliance gates
# ---------------------------------------------------------------------------


def test_controlled_drug_handling_needs_a_current_competency(employee: Employee, hr: User) -> None:
    with pytest.raises(people.PeopleError, match="controlled-drug competency"):
        people.assert_can_handle_controlled(employee)

    CompetencyAssessment.objects.create(
        employee=employee,
        competency=CompetencyAssessment.Competency.CONTROLLED_DRUG_HANDLING,
        result=CompetencyAssessment.Result.COMPETENT,
        valid_until=date.today() + timedelta(days=180),
    )
    people.assert_can_handle_controlled(employee)  # no raise


def test_an_expired_competency_does_not_count(employee: Employee) -> None:
    CompetencyAssessment.objects.create(
        employee=employee,
        competency=CompetencyAssessment.Competency.CONTROLLED_DRUG_HANDLING,
        result=CompetencyAssessment.Result.COMPETENT,
        valid_until=date.today() - timedelta(days=1),
    )
    with pytest.raises(people.PeopleError):
        people.assert_can_handle_controlled(employee)


# ---------------------------------------------------------------------------
# Statutory filings
# ---------------------------------------------------------------------------


def test_filing_generates_from_payroll_and_flags_a_ledger_mismatch(
    org: Organization, employee: Employee, hr: User
) -> None:
    from apps.hr.models import PayrollRecord
    from apps.hr.statutory import generate_filing

    run = PayrollRun.objects.create(
        organization=org,
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 30),
        status=PayrollRun.Status.APPROVED,
    )
    PayrollRecord.objects.create(
        run=run, employee=employee, gross=Decimal("600000"), paye=Decimal("120000")
    )

    filing = generate_filing(
        organization=org,
        kind=StatutoryFiling.Kind.PAYE_MONTHLY,
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 30),
        user=hr,
    )
    assert filing.employee_count == 1
    assert filing.amount_due == Decimal("120000.00")
    assert filing.due_date == date(2026, 7, 15)  # the 15th of the following month
    # Nothing has been posted to the GL, so the filing must not tie out yet.
    assert filing.gl_balance_at_generation == Decimal("0.00")
    assert filing.ties_to_ledger is False


def test_a_filing_that_does_not_tie_cannot_be_marked_filed(
    org: Organization, employee: Employee, hr: User
) -> None:
    from apps.hr.models import PayrollRecord
    from apps.hr.statutory import generate_filing

    run = PayrollRun.objects.create(
        organization=org,
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 30),
        status=PayrollRun.Status.APPROVED,
    )
    PayrollRecord.objects.create(
        run=run, employee=employee, gross=Decimal("600000"), paye=Decimal("120000")
    )
    filing = generate_filing(
        organization=org,
        kind=StatutoryFiling.Kind.PAYE_MONTHLY,
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 30),
        user=hr,
    )
    resp = _auth(hr).post(f"/api/hr/filings/{filing.pk}/mark-filed/", {}, format="json")
    assert resp.status_code == 400
    assert "does not tie" in str(resp.content)


# ---------------------------------------------------------------------------
# API surface & scoping
# ---------------------------------------------------------------------------


def test_people_screens_load_and_are_org_scoped(
    org: Organization, employee: Employee, hr: User, leave_types: list[LeaveType]
) -> None:
    client = _auth(hr)
    for path in [
        "contracts",
        "salary-structures",
        "salary-revisions",
        "payroll-adjustments",
        "leave-types",
        "leave-balances",
        "timesheets",
        "loans",
        "requisitions",
        "applicants",
        "interviews",
        "onboarding",
        "checklist-items",
        "terminations",
        "training",
        "cpd",
        "competencies",
        "disciplinary",
        "reviews",
        "filings",
    ]:
        resp = client.get(f"/api/hr/{path}/")
        assert resp.status_code == 200, f"{path} → {resp.status_code} {resp.content[:200]}"

    overview = client.get("/api/hr/overview/")
    assert overview.status_code == 200, overview.content
    body = overview.json()
    assert body["headcount"] == 1
    assert "alerts" in body

    other = Organization.objects.create(name="Rival", type="RETAIL")
    outsider = User.objects.create_user(username="rivalhr", password="x", organization=other)
    outsider.roles.add(Role.objects.get(code="HR_MANAGER"))
    people.issue_contract(
        employee=employee,
        kind=EmploymentContract.Kind.PERMANENT,
        job_title="Pharmacist",
        start_date=date(2026, 1, 1),
        user=hr,
    )
    assert _auth(outsider).get("/api/hr/contracts/").json()["results"] == []


def test_salary_can_be_set_through_the_api(employee: Employee, hr: User) -> None:
    resp = _auth(hr).post(
        "/api/hr/salary-structures/set_for_employee/",
        {
            "employee": employee.pk,
            "effective_from": "2026-01-01",
            "reason": "PROMOTION",
            "components": [
                {"code": "BASIC", "amount": "500000"},
                {"code": "TRANSPORT", "amount": "60000"},
            ],
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert body["gross"] == "560000.00"
    assert body["pension_base"] == "560000.00"
    assert body["maternity_base"] == "500000.00"


def test_loan_lifecycle_through_the_api(employee: Employee, hr: User, boss: User) -> None:
    created = _auth(hr).post(
        "/api/hr/loans/",
        {
            "employee": employee.pk,
            "principal": "120000",
            "installments_count": 4,
            "kind": "SALARY_ADVANCE",
            "reason": "School fees",
        },
        format="json",
    )
    assert created.status_code == 201, created.content
    loan_id = created.json()["id"]
    assert created.json()["monthly_installment"] == "30000.00"
    assert len(created.json()["installments"]) == 4

    approved = _auth(boss).post(f"/api/hr/loans/{loan_id}/approve/", {}, format="json")
    assert approved.status_code == 200, approved.content
    assert approved.json()["status"] == "ACTIVE"

    disbursed = _auth(hr).post(
        f"/api/hr/loans/{loan_id}/disburse/",
        {"method": "MOMO", "reference": "MM-99"},
        format="json",
    )
    assert disbursed.status_code == 200
    assert disbursed.json()["disbursement_reference"] == "MM-99"
