from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.hr.models import (
    AttendanceLog,
    Employee,
    EmployeeDocument,
    LeaveRequest,
    PayrollRecord,
    PayrollRun,
    ShiftRoster,
    StatutoryRate,
)
from apps.hr.services import allocate_employee_number


class EmployeeDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeDocument
        fields = ["id", "doc_type", "document_url", "uploaded_at"]
        read_only_fields = ["id", "uploaded_at"]


class EmployeeSerializer(serializers.ModelSerializer):
    documents = EmployeeDocumentSerializer(many=True, read_only=True)
    full_name = serializers.CharField(read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True, default=None)
    license_number = serializers.CharField(
        source="license.license_number", read_only=True, default=None
    )
    user_username = serializers.CharField(source="user.username", read_only=True, default=None)

    class Meta:
        model = Employee
        fields = [
            "id",
            "user",
            "user_username",
            "organization",
            "organization_name",
            "department",
            "department_name",
            "employee_number",
            "first_name",
            "last_name",
            "full_name",
            "national_id",
            "job_title",
            "employment_type",
            "employment_status",
            "hire_date",
            "end_date",
            "base_salary",
            "bank_account",
            "momo_number",
            "rssb_number",
            "tin",
            "pay_group",
            "pay_frequency",
            "gender",
            "dob",
            "photo",
            "probation_end",
            "contract_end",
            "supervisor",
            "license",
            "license_number",
            "next_of_kin_name",
            "next_of_kin_relation",
            "next_of_kin_phone",
            "emergency_contact_phone",
            "address",
            "documents",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "employee_number",
            "employment_status",
            "end_date",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data: dict[str, Any]) -> Employee:
        employee = Employee.objects.create(**validated_data)
        employee.employee_number = allocate_employee_number(employee)
        employee.save(update_fields=["employee_number"])
        return employee


class StatutoryRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = StatutoryRate
        fields = [
            "id",
            "country",
            "rate_type",
            "band_min",
            "band_max",
            "rate_pct",
            "effective_from",
            "effective_to",
        ]
        read_only_fields = ["id"]


class PayrollRecordSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    employee_number = serializers.CharField(source="employee.employee_number", read_only=True)

    class Meta:
        model = PayrollRecord
        fields = [
            "id",
            "employee",
            "employee_name",
            "employee_number",
            "base_salary",
            "allowances",
            "overtime_amount",
            "bonus_commission",
            "shift_premium",
            "gross",
            "paye",
            "pension_employee",
            "pension_employer",
            "maternity_employee",
            "maternity_employer",
            "cbhi",
            "loans_advances",
            "other_deductions",
            "net_pay",
            "payslip_document_id",
        ]
        read_only_fields = fields


class PayrollRunSerializer(serializers.ModelSerializer):
    records = PayrollRecordSerializer(many=True, read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.username", read_only=True, default=None
    )
    approved_by_name = serializers.CharField(
        source="approved_by.username", read_only=True, default=None
    )
    total_net_pay = serializers.SerializerMethodField()

    class Meta:
        model = PayrollRun
        fields = [
            "id",
            "organization",
            "organization_name",
            "period_start",
            "period_end",
            "status",
            "created_by",
            "created_by_name",
            "approved_by",
            "approved_by_name",
            "created_at",
            "approved_at",
            "records",
            "total_net_pay",
        ]
        read_only_fields = fields

    def get_total_net_pay(self, obj: PayrollRun) -> str:
        return str(sum((r.net_pay for r in obj.records.all()), 0))


class AttendanceLogSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    employee_number = serializers.CharField(source="employee.employee_number", read_only=True)

    class Meta:
        model = AttendanceLog
        fields = [
            "id",
            "employee",
            "employee_name",
            "employee_number",
            "date",
            "clock_in",
            "clock_out",
            "overtime_hours",
            "status",
            "notes",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class ShiftRosterSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = ShiftRoster
        fields = [
            "id",
            "organization",
            "organization_name",
            "employee",
            "employee_name",
            "date",
            "shift_type",
            "requires_pharmacist_license",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class LeaveRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    approved_by_name = serializers.CharField(source="approved_by.username", read_only=True, default=None)

    class Meta:
        model = LeaveRequest
        fields = [
            "id",
            "employee",
            "employee_name",
            "leave_type",
            "start_date",
            "end_date",
            "days_count",
            "status",
            "reason",
            "approved_by",
            "approved_by_name",
            "created_at",
        ]
        read_only_fields = ["id", "status", "approved_by", "created_at"]
