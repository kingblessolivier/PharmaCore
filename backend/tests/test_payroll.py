"""Payroll gross->net engine: statutory-rate-driven calculation, the approval-gated
run lifecycle (no self-approval), and auto-posting into the Finance GL."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from apps.approvals.services import ApprovalError, claim, decide
from apps.finance.models import JournalEntry
from apps.hr.models import Employee, PayrollRun
from apps.hr.payroll import compute_paye, compute_payroll_line
from apps.hr.payroll_run import build_payroll_run, mark_payroll_run_paid, submit_payroll_run
from apps.iam.models import Organization, Role, User
from rest_framework.test import APIClient


def _auth(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def org(db: None) -> Organization:
    return Organization.objects.create(name="Branch Pharmacy", type="RETAIL")


@pytest.fixture
def hr_officer(org: Organization) -> User:
    u = User.objects.create_user(username="hrpay", password="x", organization=org)
    u.roles.add(Role.objects.get(code="HR_MANAGER"))
    return u


@pytest.fixture
def org_admin(org: Organization) -> User:
    u = User.objects.create_user(username="paysenior", password="x", organization=org)
    u.roles.add(Role.objects.get(code="ORG_ADMIN"))
    return u


@pytest.fixture
def employee(org: Organization) -> Employee:
    return Employee.objects.create(
        organization=org,
        first_name="Aline",
        last_name="Uwase",
        hire_date=date(2024, 1, 1),
        employment_status=Employee.Status.ACTIVE,
        base_salary=Decimal("250000"),
    )


@pytest.mark.django_db
def test_paye_progressive_bands() -> None:
    # 250,000: 0 on first 60k, 10% on next 40k (=4000), 20% on next 100k (=20000),
    # 30% on remaining 50k (=15000) => 39,000.
    assert compute_paye(Decimal("250000"), date(2026, 1, 1)) == Decimal("39000.00")
    assert compute_paye(Decimal("50000"), date(2026, 1, 1)) == Decimal("0.00")
    assert compute_paye(Decimal("100000"), date(2026, 1, 1)) == Decimal("4000.00")


@pytest.mark.django_db
def test_compute_payroll_line_gross_to_net(employee: Employee) -> None:
    line = compute_payroll_line(employee=employee, on_date=date(2026, 1, 1))
    assert line.gross == Decimal("250000.00")
    assert line.paye == Decimal("39000.00")
    assert line.pension_employee == Decimal("15000.00")  # 6% of 250,000
    assert line.maternity_employee == Decimal("750.00")  # 0.3% of 250,000
    net_before_cbhi = line.gross - line.paye - line.pension_employee - line.maternity_employee
    assert line.cbhi == (net_before_cbhi * Decimal("0.005")).quantize(Decimal("0.01"))
    assert line.net_pay == net_before_cbhi - line.cbhi


@pytest.mark.django_db
def test_payroll_run_requires_approval_no_self_approval_and_posts_journal(
    org: Organization, employee: Employee, hr_officer: User, org_admin: User
) -> None:
    run = build_payroll_run(
        organization=org,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        created_by=hr_officer,
    )
    assert run.records.count() == 1
    assert run.status == PayrollRun.Status.DRAFT

    approval = submit_payroll_run(run=run, requested_by=hr_officer)
    run.refresh_from_db()
    assert run.status == PayrollRun.Status.PENDING_APPROVAL

    with pytest.raises(ApprovalError):
        claim(approval=approval, user=hr_officer)

    claim(approval=approval, user=org_admin)
    decide(approval=approval, user=org_admin, approve=True)

    run.refresh_from_db()
    assert run.status == PayrollRun.Status.APPROVED
    record = run.records.first()
    record.refresh_from_db()
    assert record.payslip_document_id

    # Journal posted: one employee-side entry (gross expense, statutory
    # payables, net-pay payable) plus one entry per employer-side contribution,
    # each under its own reference so none of them deduplicate each other away.
    entries = JournalEntry.objects.filter(organization=org, reference_type="payroll_run")
    assert entries.count() == 1
    employer_entries = JournalEntry.objects.filter(
        organization=org, reference_type="payroll_employer"
    )
    assert employer_entries.count() >= 2  # RSSB pension + maternity at minimum
    for entry in employer_entries:
        assert entry.total_debit == entry.total_credit
    main_entry = (
        entries.filter(description__icontains="Payroll —")
        .exclude(description__icontains="employer")
        .first()
    )
    assert main_entry.total_debit == float(record.gross)


@pytest.mark.django_db
def test_mark_paid_requires_approved_status(
    org: Organization, employee: Employee, hr_officer: User, org_admin: User
) -> None:
    run = build_payroll_run(
        organization=org,
        period_start=date(2026, 2, 1),
        period_end=date(2026, 2, 28),
        created_by=hr_officer,
    )
    with pytest.raises(ValueError):
        mark_payroll_run_paid(run=run, user=hr_officer)

    approval = submit_payroll_run(run=run, requested_by=hr_officer)
    claim(approval=approval, user=org_admin)
    decide(approval=approval, user=org_admin, approve=True)
    run.refresh_from_db()

    mark_payroll_run_paid(run=run, user=hr_officer)
    run.refresh_from_db()
    assert run.status == PayrollRun.Status.PAID


@pytest.mark.django_db
def test_payroll_run_api_build_submit(
    org: Organization, employee: Employee, hr_officer: User
) -> None:
    resp = _auth(hr_officer).post(
        "/api/hr/payroll-runs/",
        {"organization": org.pk, "period_start": "2026-03-01", "period_end": "2026-03-31"},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    run_id = resp.json()["id"]

    submit = _auth(hr_officer).post(f"/api/hr/payroll-runs/{run_id}/submit/")
    assert submit.status_code == 200, submit.content
    assert submit.json()["status"] == "PENDING_APPROVAL"


@pytest.mark.django_db
def test_duplicate_payroll_period_returns_clean_400(
    org: Organization, employee: Employee, hr_officer: User
) -> None:
    """Regression: a duplicate (org, period) run used to hit the DB's unique
    constraint directly and surface as an unhandled 500."""
    payload = {"organization": org.pk, "period_start": "2026-04-01", "period_end": "2026-04-30"}
    first = _auth(hr_officer).post("/api/hr/payroll-runs/", payload, format="json")
    assert first.status_code == 201, first.content

    second = _auth(hr_officer).post("/api/hr/payroll-runs/", payload, format="json")
    assert second.status_code == 400
    assert "already exists" in second.json()[0]


@pytest.mark.django_db
def test_statutory_rates_endpoint_lists_seeded_rates(hr_officer: User) -> None:
    resp = _auth(hr_officer).get("/api/hr/statutory-rates/")
    assert resp.status_code == 200
    codes = {r["rate_type"] for r in resp.json()["results"]}
    assert "PAYE_BRACKET" in codes
    assert "CBHI" in codes
