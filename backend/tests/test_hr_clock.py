"""BE3 — attendance clock in/out.

Exercises the new ``clock`` action on ``AttendanceLogViewSet`` and the
``clock_attendance`` service: the user punches in once, then out; double-IN
and OUT-before-IN are refused; a user with no employee record is refused;
overtime is computed when the shift runs longer than 8 hours.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from apps.hr.models import AttendanceLog, Employee
from apps.hr.services import clock_attendance
from apps.iam.models import Organization, Role, User
from django.utils import timezone
from rest_framework.test import APIClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def org(db: None) -> Organization:
    return Organization.objects.create(name="Branch Pharmacy", type="RETAIL")


@pytest.fixture
def pharmacist_user(db: None, org: Organization) -> User:
    user = User.objects.create_user(username="pha1", password="x", organization=org)
    user.roles.add(Role.objects.get(code="PHARMACIST"))
    return user


@pytest.fixture
def pharmacist_employee(db: None, org: Organization, pharmacist_user: User) -> Employee:
    return Employee.objects.create(
        organization=org,
        user=pharmacist_user,
        first_name="Aline",
        last_name="Uwase",
        hire_date=date(2025, 1, 1),
    )


@pytest.fixture
def hr_officer(db: None, org: Organization) -> User:
    user = User.objects.create_user(username="hr1", password="x", organization=org)
    user.roles.add(Role.objects.get(code="HR_MANAGER"))
    return user


def _auth(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# ---------------------------------------------------------------------------
# Service-layer tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_clock_in_creates_log_for_today(
    pharmacist_employee: Employee, pharmacist_user: User
) -> None:
    log = clock_attendance(employee=pharmacist_employee, direction="IN", user=pharmacist_user)
    assert log.pk is not None
    assert log.clock_in is not None
    assert log.clock_out is None
    assert log.status == AttendanceLog.Status.PRESENT
    assert log.date == timezone.now().date() or log.date == date.today()


@pytest.mark.django_db
def test_double_clocking_in_is_refused(
    pharmacist_employee: Employee, pharmacist_user: User
) -> None:
    clock_attendance(employee=pharmacist_employee, direction="IN", user=pharmacist_user)
    with pytest.raises(ValueError, match="already clocked in"):
        clock_attendance(employee=pharmacist_employee, direction="IN", user=pharmacist_user)


@pytest.mark.django_db
def test_clock_out_without_in_is_refused(
    pharmacist_employee: Employee, pharmacist_user: User
) -> None:
    with pytest.raises(ValueError, match="has not clocked in"):
        clock_attendance(employee=pharmacist_employee, direction="OUT", user=pharmacist_user)


@pytest.mark.django_db
def test_clock_out_fills_out_time_and_status(
    pharmacist_employee: Employee, pharmacist_user: User
) -> None:
    clock_attendance(employee=pharmacist_employee, direction="IN", user=pharmacist_user)
    log = clock_attendance(employee=pharmacist_employee, direction="OUT", user=pharmacist_user)
    assert log.clock_out is not None
    assert log.clock_in is not None
    assert log.clock_out >= log.clock_in
    assert log.overtime_hours == Decimal("0.00")  # fresh punch: zero hours


@pytest.mark.django_db
def test_overtime_computed_when_shift_exceeds_eight_hours(
    pharmacist_employee: Employee, pharmacist_user: User
) -> None:
    """Backdate ``clock_in`` so the delta is 9h, then clock OUT — expect 1.0 overtime."""
    log = clock_attendance(employee=pharmacist_employee, direction="IN", user=pharmacist_user)
    log.clock_in = timezone.now() - timedelta(hours=9)
    log.save(update_fields=["clock_in"])

    log = clock_attendance(employee=pharmacist_employee, direction="OUT", user=pharmacist_user)
    assert log.overtime_hours == Decimal("1.00")


@pytest.mark.django_db
def test_invalid_direction_raises(pharmacist_employee: Employee, pharmacist_user: User) -> None:
    with pytest.raises(ValueError, match="direction must be"):
        clock_attendance(employee=pharmacist_employee, direction="SIDEWAYS", user=pharmacist_user)


# ---------------------------------------------------------------------------
# View-layer tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_post_clock_in_creates_log_via_api(
    pharmacist_employee: Employee, pharmacist_user: User
) -> None:
    resp = _auth(pharmacist_user).post(
        "/api/hr/attendance/clock/", {"direction": "IN"}, format="json"
    )
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert body["clock_in"] is not None
    assert body["clock_out"] is None
    assert AttendanceLog.objects.filter(employee=pharmacist_employee).count() == 1


@pytest.mark.django_db
def test_post_clock_in_then_out_via_api(
    pharmacist_employee: Employee, pharmacist_user: User
) -> None:
    client = _auth(pharmacist_user)
    r1 = client.post("/api/hr/attendance/clock/", {"direction": "IN"}, format="json")
    assert r1.status_code == 201
    r2 = client.post("/api/hr/attendance/clock/", {"direction": "OUT"}, format="json")
    assert r2.status_code == 201, r2.content
    body = r2.json()
    assert body["clock_in"] is not None
    assert body["clock_out"] is not None


@pytest.mark.django_db
def test_double_clock_in_via_api_returns_400(
    pharmacist_employee: Employee, pharmacist_user: User
) -> None:
    client = _auth(pharmacist_user)
    client.post("/api/hr/attendance/clock/", {"direction": "IN"}, format="json")
    r2 = client.post("/api/hr/attendance/clock/", {"direction": "IN"}, format="json")
    assert r2.status_code == 400
    assert "already clocked in" in str(r2.content).lower()


@pytest.mark.django_db
def test_clock_out_without_in_via_api_returns_400(
    pharmacist_employee: Employee, pharmacist_user: User
) -> None:
    client = _auth(pharmacist_user)
    r = client.post("/api/hr/attendance/clock/", {"direction": "OUT"}, format="json")
    assert r.status_code == 400
    assert "clock in" in str(r.content).lower()


@pytest.mark.django_db
def test_user_with_no_employee_record_is_refused(pharmacist_user: User) -> None:
    """The caller has no Employee link — the API must refuse with a clear 400."""
    resp = _auth(pharmacist_user).post(
        "/api/hr/attendance/clock/", {"direction": "IN"}, format="json"
    )
    assert resp.status_code == 400
    assert "no employee record" in str(resp.content).lower()


@pytest.mark.django_db
def test_hr_can_clock_on_behalf_via_employee_id(
    hr_officer: User, pharmacist_employee: Employee
) -> None:
    """HR manager passes ?employee_id= to mark a floor employee's punch."""
    resp = _auth(hr_officer).post(
        f"/api/hr/attendance/clock/?employee_id={pharmacist_employee.pk}",
        {"direction": "IN"},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    assert AttendanceLog.objects.filter(employee=pharmacist_employee).count() == 1


@pytest.mark.django_db
def test_non_hr_cannot_clock_on_behalf(
    pharmacist_user: User, pharmacist_employee: Employee
) -> None:
    """A non-HR user cannot pass ``?employee_id`` to act on someone else."""
    resp = _auth(pharmacist_user).post(
        f"/api/hr/attendance/clock/?employee_id={pharmacist_employee.pk}",
        {"direction": "IN"},
        format="json",
    )
    assert resp.status_code == 403
