"""HR: the Employee master, scoping/permissions, and the approval-gated
(no self-approval) termination flow."""

from __future__ import annotations

from datetime import date

import pytest
from apps.approvals.models import ApprovalRequest
from apps.approvals.services import ApprovalError, claim, decide
from apps.hr.models import Employee
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
def other_org(db: None) -> Organization:
    return Organization.objects.create(name="Other Pharmacy", type="RETAIL")


@pytest.fixture
def hr_officer(org: Organization) -> User:
    u = User.objects.create_user(username="hr1", password="x", organization=org)
    u.roles.add(Role.objects.get(code="HR_MANAGER"))
    return u


@pytest.fixture
def org_admin(org: Organization) -> User:
    u = User.objects.create_user(username="admin1", password="x", organization=org)
    u.roles.add(Role.objects.get(code="ORG_ADMIN"))
    return u


@pytest.fixture
def cashier(org: Organization) -> User:
    u = User.objects.create_user(username="till1", password="x", organization=org)
    u.roles.add(Role.objects.get(code="CASHIER"))
    return u


@pytest.mark.django_db
def test_hr_officer_can_create_employee(hr_officer: User, org: Organization) -> None:
    resp = _auth(hr_officer).post(
        "/api/hr/employees/",
        {
            "organization": org.pk,
            "first_name": "Aline",
            "last_name": "Uwase",
            "hire_date": "2026-01-05",
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert body["employee_number"] == f"EMP-{body['id']:05d}"
    assert body["employment_status"] == "PROBATION"


@pytest.mark.django_db
def test_cashier_cannot_create_employee(cashier: User, org: Organization) -> None:
    resp = _auth(cashier).post(
        "/api/hr/employees/",
        {"organization": org.pk, "first_name": "X", "last_name": "Y", "hire_date": "2026-01-05"},
        format="json",
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_employee_list_scoped_to_visible_orgs(
    hr_officer: User, org: Organization, other_org: Organization
) -> None:
    Employee.objects.create(
        organization=org, first_name="A", last_name="B", hire_date=date(2025, 1, 1)
    )
    Employee.objects.create(
        organization=other_org, first_name="C", last_name="D", hire_date=date(2025, 1, 1)
    )
    resp = _auth(hr_officer).get("/api/hr/employees/")
    assert resp.status_code == 200
    assert resp.json()["count"] == 1


@pytest.mark.django_db
def test_termination_requires_approval_no_self_approval(
    hr_officer: User, org_admin: User, org: Organization
) -> None:
    employee = Employee.objects.create(
        organization=org, first_name="A", last_name="B", hire_date=date(2025, 1, 1)
    )
    resp = _auth(hr_officer).post(
        f"/api/hr/employees/{employee.pk}/request-termination/", {"reason": "Policy breach"}
    )
    assert resp.status_code == 201, resp.content
    approval_id = resp.json()["approval_request"]

    employee.refresh_from_db()
    assert employee.employment_status != Employee.Status.TERMINATED

    approval = ApprovalRequest.objects.get(pk=approval_id)
    with pytest.raises(ApprovalError):
        claim(approval=approval, user=hr_officer)

    claim(approval=approval, user=org_admin)
    decide(approval=approval, user=org_admin, approve=True)

    employee.refresh_from_db()
    assert employee.employment_status == Employee.Status.TERMINATED
    assert employee.end_date is not None


@pytest.mark.django_db
def test_terminating_employee_deactivates_linked_user(
    hr_officer: User, org_admin: User, org: Organization
) -> None:
    linked_user = User.objects.create_user(username="staffer", password="x", organization=org)
    employee = Employee.objects.create(
        organization=org,
        user=linked_user,
        first_name="A",
        last_name="B",
        hire_date=date(2025, 1, 1),
    )
    resp = _auth(hr_officer).post(
        f"/api/hr/employees/{employee.pk}/request-termination/", {"reason": "Resignation"}
    )
    approval = ApprovalRequest.objects.get(pk=resp.json()["approval_request"])
    claim(approval=approval, user=org_admin)
    decide(approval=approval, user=org_admin, approve=True)

    linked_user.refresh_from_db()
    assert linked_user.is_active is False
