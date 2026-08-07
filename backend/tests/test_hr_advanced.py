from datetime import date
from decimal import Decimal

import pytest
from apps.hr.models import AttendanceLog, Employee, LeaveRequest, ShiftRoster
from apps.iam.models import Organization, User
from django.utils import timezone

pytestmark = pytest.mark.django_db


def test_attendance_clock_in_out_and_overtime():
    org = Organization.objects.create(name="Central Depot", type="DEPOT")
    emp = Employee.objects.create(
        organization=org,
        first_name="Jean",
        last_name="Mugabo",
        national_id="1199080012345678",
        job_title="Pharmacist Tech",
        hire_date=date(2025, 1, 1),
    )
    now = timezone.now()
    log = AttendanceLog.objects.create(
        employee=emp,
        date=date(2026, 8, 6),
        clock_in=now,
        clock_out=now,
        overtime_hours=Decimal("2.00"),
        status=AttendanceLog.Status.PRESENT,
    )
    assert log.overtime_hours == Decimal("2.00")
    assert log.status == AttendanceLog.Status.PRESENT


def test_shift_roster_credential_guard():
    org = Organization.objects.create(name="Central Depot", type="DEPOT")
    emp = Employee.objects.create(
        organization=org,
        first_name="Alice",
        last_name="Uwase",
        national_id="1199580012345678",
        job_title="Head Pharmacist",
        hire_date=date(2025, 1, 1),
    )
    roster = ShiftRoster.objects.create(
        organization=org,
        employee=emp,
        date=date(2026, 8, 6),
        shift_type=ShiftRoster.ShiftType.MORNING,
        requires_pharmacist_license=True,
    )
    assert roster.requires_pharmacist_license is True
    assert roster.shift_type == ShiftRoster.ShiftType.MORNING


def test_leave_request_approval_workflow():
    org = Organization.objects.create(name="Central Depot", type="DEPOT")
    user = User.objects.create_user(username="hr_admin", password="password")
    emp = Employee.objects.create(
        organization=org,
        first_name="Eric",
        last_name="Nshimiyimana",
        national_id="1199280012345678",
        job_title="Dispenser",
        hire_date=date(2025, 1, 1),
    )
    leave = LeaveRequest.objects.create(
        employee=emp,
        leave_type=LeaveRequest.LeaveType.ANNUAL,
        start_date=date(2026, 8, 10),
        end_date=date(2026, 8, 15),
        days_count=5,
        reason="Family holiday",
    )
    assert leave.status == LeaveRequest.Status.PENDING
    leave.status = LeaveRequest.Status.APPROVED
    leave.approved_by = user
    leave.save()
    assert leave.status == LeaveRequest.Status.APPROVED
    assert leave.approved_by == user
