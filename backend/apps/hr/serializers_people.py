"""Serializers for the People lifecycle: contracts, pay, leave, time, loans,
recruitment, offboarding, training and statutory filings.

Same convention as Procurement: a record is written header-plus-nested-lines in
one payload, and every computed number the screen shows is exposed read-only so
the UI never re-derives (and never disagrees with) the server.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.hr.models import (
    Applicant,
    ChecklistItem,
    CompetencyAssessment,
    CPDRecord,
    DisciplinaryAction,
    EmploymentContract,
    FinalSettlement,
    InterviewSlot,
    JobRequisition,
    LeaveAccrual,
    LeaveBalance,
    LeaveType,
    LoanAdvance,
    LoanInstallment,
    OnboardingChecklist,
    PayrollAdjustment,
    PerformanceReview,
    SalaryComponent,
    SalaryRevision,
    SalaryStructure,
    StatutoryFiling,
    Termination,
    Timesheet,
    TrainingRecord,
)

# Annotated: without this the values infer as ``int`` (bool subclasses int), and
# ``**MONEY`` then fails to match DecimalField's keyword signature.
MONEY: dict[str, Any] = {"max_digits": 14, "decimal_places": 2, "read_only": True}


class EmploymentContractSerializer(serializers.ModelSerializer[EmploymentContract]):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    employee_number = serializers.CharField(source="employee.employee_number", read_only=True)
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True, default=None)
    reports_to_name = serializers.CharField(
        source="reports_to.full_name", read_only=True, default=None
    )
    is_expiring = serializers.BooleanField(read_only=True)

    class Meta:
        model = EmploymentContract
        fields = [
            "id",
            "employee",
            "employee_name",
            "employee_number",
            "reference",
            "kind",
            "kind_display",
            "status",
            "status_display",
            "job_title",
            "grade",
            "step",
            "department",
            "department_name",
            "reports_to",
            "reports_to_name",
            "start_date",
            "end_date",
            "probation_months",
            "probation_end",
            "notice_period_days",
            "working_hours_per_week",
            "annual_leave_days",
            "is_current",
            "signed_on",
            "signed_document_url",
            "terms",
            "is_expiring",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["status", "is_current", "created_at", "updated_at"]


class SalaryComponentSerializer(serializers.ModelSerializer[SalaryComponent]):
    code_display = serializers.CharField(source="get_code_display", read_only=True)

    class Meta:
        model = SalaryComponent
        fields = [
            "id",
            "code",
            "code_display",
            "label",
            "amount",
            "is_taxable",
            "in_pension_base",
            "in_maternity_base",
            "is_prorated",
            "sort_order",
        ]


class SalaryStructureSerializer(serializers.ModelSerializer[SalaryStructure]):
    components = SalaryComponentSerializer(many=True, read_only=True)
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    gross = serializers.DecimalField(**MONEY)
    pension_base = serializers.DecimalField(**MONEY)
    maternity_base = serializers.DecimalField(**MONEY)
    taxable_base = serializers.DecimalField(**MONEY)

    class Meta:
        model = SalaryStructure
        fields = [
            "id",
            "employee",
            "employee_name",
            "contract",
            "effective_from",
            "effective_to",
            "currency",
            "is_active",
            "note",
            "components",
            "gross",
            "pension_base",
            "maternity_base",
            "taxable_base",
            "created_at",
        ]
        read_only_fields = fields


class SalaryRevisionSerializer(serializers.ModelSerializer[SalaryRevision]):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    reason_display = serializers.CharField(source="get_reason_display", read_only=True)
    change_pct = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)
    approved_by_name = serializers.CharField(
        source="approved_by.username", read_only=True, default=None
    )

    class Meta:
        model = SalaryRevision
        fields = [
            "id",
            "employee",
            "employee_name",
            "previous_structure",
            "new_structure",
            "effective_date",
            "reason",
            "reason_display",
            "previous_gross",
            "new_gross",
            "change_pct",
            "note",
            "approved_by",
            "approved_by_name",
            "approved_at",
            "created_at",
        ]
        read_only_fields = fields


class LeaveTypeSerializer(serializers.ModelSerializer[LeaveType]):
    accrual_display = serializers.CharField(source="get_accrual_display", read_only=True)

    class Meta:
        model = LeaveType
        fields = [
            "id",
            "organization",
            "code",
            "name",
            "days_per_year",
            "accrual",
            "accrual_display",
            "is_paid",
            "carry_over_max_days",
            "carry_over_expires_months",
            "requires_document",
            "max_consecutive_days",
            "min_notice_days",
            "is_encashable",
            "gender_restriction",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["created_at"]


class LeaveAccrualSerializer(serializers.ModelSerializer[LeaveAccrual]):
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)

    class Meta:
        model = LeaveAccrual
        fields = [
            "id",
            "kind",
            "kind_display",
            "days",
            "occurred_on",
            "leave_request",
            "note",
            "created_at",
        ]
        read_only_fields = fields


class LeaveBalanceSerializer(serializers.ModelSerializer[LeaveBalance]):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    employee_number = serializers.CharField(source="employee.employee_number", read_only=True)
    leave_type_name = serializers.CharField(source="leave_type.name", read_only=True)
    leave_type_code = serializers.CharField(source="leave_type.code", read_only=True)
    is_paid = serializers.BooleanField(source="leave_type.is_paid", read_only=True)
    entitled = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)
    available = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)
    movements = LeaveAccrualSerializer(many=True, read_only=True)

    class Meta:
        model = LeaveBalance
        fields = [
            "id",
            "employee",
            "employee_name",
            "employee_number",
            "leave_type",
            "leave_type_name",
            "leave_type_code",
            "is_paid",
            "year",
            "opening_balance",
            "accrued",
            "carried_over",
            "taken",
            "pending",
            "encashed",
            "adjustment",
            "entitled",
            "available",
            "movements",
            "updated_at",
        ]
        read_only_fields = fields


class TimesheetSerializer(serializers.ModelSerializer[Timesheet]):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    employee_number = serializers.CharField(source="employee.employee_number", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    approved_by_name = serializers.CharField(
        source="approved_by.username", read_only=True, default=None
    )
    is_editable = serializers.BooleanField(read_only=True)

    class Meta:
        model = Timesheet
        fields = [
            "id",
            "employee",
            "employee_name",
            "employee_number",
            "period_start",
            "period_end",
            "status",
            "status_display",
            "days_worked",
            "days_absent",
            "days_on_leave",
            "unpaid_leave_days",
            "hours_worked",
            "hours_rostered",
            "overtime_hours",
            "night_hours",
            "holiday_hours",
            "late_count",
            "early_leave_count",
            "submitted_at",
            "approved_by",
            "approved_by_name",
            "approved_at",
            "rejection_reason",
            "notes",
            "is_editable",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "status",
            "days_worked",
            "days_absent",
            "days_on_leave",
            "unpaid_leave_days",
            "hours_worked",
            "hours_rostered",
            "overtime_hours",
            "night_hours",
            "late_count",
            "submitted_at",
            "approved_by",
            "approved_at",
            "created_at",
            "updated_at",
        ]


class LoanInstallmentSerializer(serializers.ModelSerializer[LoanInstallment]):
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = LoanInstallment
        fields = [
            "id",
            "sequence",
            "due_date",
            "amount",
            "amount_paid",
            "is_paid",
            "payroll_run",
            "skipped_reason",
            "paid_at",
            "is_overdue",
        ]
        read_only_fields = fields


class LoanAdvanceSerializer(serializers.ModelSerializer[LoanAdvance]):
    installments = LoanInstallmentSerializer(many=True, read_only=True)
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    employee_number = serializers.CharField(source="employee.employee_number", read_only=True)
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    guarantor_name = serializers.CharField(
        source="guarantor.full_name", read_only=True, default=None
    )
    total_repayable = serializers.DecimalField(**MONEY)
    repaid = serializers.DecimalField(**MONEY)
    progress_pct = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)

    class Meta:
        model = LoanAdvance
        fields = [
            "id",
            "reference",
            "employee",
            "employee_name",
            "employee_number",
            "kind",
            "kind_display",
            "status",
            "status_display",
            "principal",
            "interest_rate_pct",
            "balance",
            "monthly_installment",
            "installments_count",
            "start_date",
            "end_date",
            "reason",
            "guarantor",
            "guarantor_name",
            "disbursed_on",
            "disbursement_method",
            "disbursement_reference",
            "approved_by",
            "approved_at",
            "total_repayable",
            "repaid",
            "progress_pct",
            "installments",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "reference",
            "status",
            "balance",
            "monthly_installment",
            "end_date",
            "approved_by",
            "approved_at",
            "created_at",
            "updated_at",
        ]


class PayrollAdjustmentSerializer(serializers.ModelSerializer[PayrollAdjustment]):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)

    class Meta:
        model = PayrollAdjustment
        fields = [
            "id",
            "employee",
            "employee_name",
            "kind",
            "kind_display",
            "amount",
            "is_taxable",
            "in_pension_base",
            "reason",
            "relates_to_run",
            "applied_run",
            "apply_from",
            "approved_by",
            "approved_at",
            "created_at",
        ]
        read_only_fields = ["applied_run", "approved_by", "approved_at", "created_at"]


class StatutoryFilingSerializer(serializers.ModelSerializer[StatutoryFiling]):
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    ties_to_ledger = serializers.BooleanField(read_only=True)

    class Meta:
        model = StatutoryFiling
        fields = [
            "id",
            "organization",
            "organization_name",
            "reference",
            "kind",
            "kind_display",
            "status",
            "status_display",
            "period_start",
            "period_end",
            "due_date",
            "employee_count",
            "gross_total",
            "employee_contribution",
            "employer_contribution",
            "amount_due",
            "gl_balance_at_generation",
            "payload",
            "return_file",
            "authority_reference",
            "filed_on",
            "tax_payment",
            "rejection_reason",
            "notes",
            "is_overdue",
            "ties_to_ledger",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "reference",
            "status",
            "employee_count",
            "gross_total",
            "employee_contribution",
            "employer_contribution",
            "amount_due",
            "gl_balance_at_generation",
            "payload",
            "return_file",
            "filed_on",
            "created_at",
            "updated_at",
        ]


class InterviewSlotSerializer(serializers.ModelSerializer[InterviewSlot]):
    decision_display = serializers.CharField(source="get_decision_display", read_only=True)

    class Meta:
        model = InterviewSlot
        fields = [
            "id",
            "applicant",
            "round_number",
            "scheduled_at",
            "duration_minutes",
            "mode",
            "location",
            "panel",
            "score",
            "decision",
            "decision_display",
            "feedback",
            "created_at",
        ]
        read_only_fields = ["created_at"]


class ApplicantSerializer(serializers.ModelSerializer[Applicant]):
    interviews = InterviewSlotSerializer(many=True, read_only=True)
    full_name = serializers.CharField(read_only=True)
    stage_display = serializers.CharField(source="get_stage_display", read_only=True)
    requisition_title = serializers.CharField(source="requisition.job_title", read_only=True)

    class Meta:
        model = Applicant
        fields = [
            "id",
            "requisition",
            "requisition_title",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "phone",
            "national_id",
            "gender",
            "stage",
            "stage_display",
            "source",
            "years_experience",
            "highest_qualification",
            "licence_number",
            "cv_url",
            "cover_letter_url",
            "expected_salary",
            "offered_salary",
            "offer_sent_on",
            "offer_accepted_on",
            "proposed_start_date",
            "rejection_reason",
            "hired_employee",
            "notes",
            "interviews",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["hired_employee", "created_at", "updated_at"]


class JobRequisitionSerializer(serializers.ModelSerializer[JobRequisition]):
    applicants = ApplicantSerializer(many=True, read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True, default=None)
    hiring_manager_name = serializers.CharField(
        source="hiring_manager.full_name", read_only=True, default=None
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    vacancies_left = serializers.IntegerField(read_only=True)
    applicant_count = serializers.IntegerField(source="applicants.count", read_only=True)

    class Meta:
        model = JobRequisition
        fields = [
            "id",
            "reference",
            "organization",
            "organization_name",
            "department",
            "department_name",
            "job_title",
            "headcount",
            "headcount_filled",
            "vacancies_left",
            "employment_type",
            "status",
            "status_display",
            "is_replacement",
            "replaces",
            "hiring_manager",
            "hiring_manager_name",
            "budget_min",
            "budget_max",
            "requires_licence",
            "job_description",
            "requirements",
            "opened_at",
            "closes_at",
            "approved_by",
            "approved_at",
            "applicant_count",
            "applicants",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "reference",
            "headcount_filled",
            "approved_by",
            "approved_at",
            "created_at",
            "updated_at",
        ]


class ChecklistItemSerializer(serializers.ModelSerializer[ChecklistItem]):
    category_display = serializers.CharField(source="get_category_display", read_only=True)

    class Meta:
        model = ChecklistItem
        fields = [
            "id",
            "onboarding",
            "termination",
            "phase",
            "category",
            "category_display",
            "label",
            "is_mandatory",
            "is_done",
            "due_date",
            "completed_at",
            "completed_by",
            "evidence_url",
            "note",
            "sort_order",
        ]
        read_only_fields = ["completed_at", "completed_by"]


class OnboardingChecklistSerializer(serializers.ModelSerializer[OnboardingChecklist]):
    items = ChecklistItemSerializer(many=True, read_only=True)
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    progress_pct = serializers.DecimalField(max_digits=6, decimal_places=2, read_only=True)

    class Meta:
        model = OnboardingChecklist
        fields = [
            "id",
            "employee",
            "employee_name",
            "template",
            "started_on",
            "target_completion",
            "completed_at",
            "owner",
            "notes",
            "progress_pct",
            "items",
            "created_at",
        ]
        read_only_fields = ["completed_at", "created_at"]


class FinalSettlementSerializer(serializers.ModelSerializer[FinalSettlement]):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    gross_dues = serializers.DecimalField(**MONEY)
    total_deductions = serializers.DecimalField(**MONEY)

    class Meta:
        model = FinalSettlement
        fields = [
            "id",
            "termination",
            "status",
            "status_display",
            "computed_on",
            "pro_rata_salary",
            "leave_days_encashed",
            "leave_encashment",
            "notice_pay",
            "severance_pay",
            "other_dues",
            "loan_recovery",
            "advance_recovery",
            "paye",
            "other_deductions",
            "gross_dues",
            "total_deductions",
            "net_payable",
            "paid_on",
            "payment_method",
            "payment_reference",
            "approved_by",
            "approved_at",
            "notes",
            "created_at",
        ]
        read_only_fields = [
            "computed_on",
            "pro_rata_salary",
            "leave_days_encashed",
            "leave_encashment",
            "loan_recovery",
            "net_payable",
            "approved_by",
            "approved_at",
            "created_at",
        ]


class TerminationSerializer(serializers.ModelSerializer[Termination]):
    items = ChecklistItemSerializer(many=True, read_only=True)
    settlement = FinalSettlementSerializer(read_only=True)
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    employee_number = serializers.CharField(source="employee.employee_number", read_only=True)
    reason_display = serializers.CharField(source="get_reason_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    clearance_pct = serializers.DecimalField(max_digits=6, decimal_places=2, read_only=True)

    class Meta:
        model = Termination
        fields = [
            "id",
            "employee",
            "employee_name",
            "employee_number",
            "reason",
            "reason_display",
            "status",
            "status_display",
            "notice_given_on",
            "last_working_day",
            "notice_period_served",
            "notice_pay_in_lieu",
            "is_eligible_for_rehire",
            "exit_interview_done",
            "exit_interview_notes",
            "handover_to",
            "certificate_of_service_url",
            "detail",
            "initiated_by",
            "approved_by",
            "approved_at",
            "clearance_pct",
            "items",
            "settlement",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "status",
            "initiated_by",
            "approved_by",
            "approved_at",
            "created_at",
            "updated_at",
        ]


class TrainingRecordSerializer(serializers.ModelSerializer[TrainingRecord]):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = TrainingRecord
        fields = [
            "id",
            "employee",
            "employee_name",
            "course_name",
            "kind",
            "kind_display",
            "status",
            "status_display",
            "provider",
            "is_mandatory",
            "assigned_on",
            "due_on",
            "completed_on",
            "expires_on",
            "score",
            "hours",
            "certificate_number",
            "certificate_url",
            "acknowledged_at",
            "notes",
            "is_overdue",
            "created_at",
        ]
        read_only_fields = ["created_at"]


class CPDRecordSerializer(serializers.ModelSerializer[CPDRecord]):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)

    class Meta:
        model = CPDRecord
        fields = [
            "id",
            "employee",
            "employee_name",
            "activity",
            "activity_date",
            "hours",
            "provider",
            "cpd_year",
            "is_accredited",
            "accreditation_body",
            "evidence_url",
            "verified_by",
            "verified_at",
            "created_at",
        ]
        read_only_fields = ["verified_by", "verified_at", "created_at"]


class CompetencyAssessmentSerializer(serializers.ModelSerializer[CompetencyAssessment]):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    competency_display = serializers.CharField(source="get_competency_display", read_only=True)
    result_display = serializers.CharField(source="get_result_display", read_only=True)
    assessor_name = serializers.CharField(source="assessor.full_name", read_only=True, default=None)
    is_valid = serializers.BooleanField(read_only=True)  # type: ignore[assignment]

    class Meta:
        model = CompetencyAssessment
        fields = [
            "id",
            "employee",
            "employee_name",
            "competency",
            "competency_display",
            "result",
            "result_display",
            "assessed_on",
            "valid_until",
            "score",
            "assessor",
            "assessor_name",
            "evidence_url",
            "notes",
            "is_valid",
            "created_at",
        ]
        read_only_fields = ["created_at"]


class DisciplinaryActionSerializer(serializers.ModelSerializer[DisciplinaryAction]):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    is_live = serializers.BooleanField(read_only=True)

    class Meta:
        model = DisciplinaryAction
        fields = [
            "id",
            "employee",
            "employee_name",
            "kind",
            "kind_display",
            "status",
            "status_display",
            "incident_date",
            "issued_on",
            "expires_on",
            "reason",
            "employee_response",
            "responded_at",
            "suspension_start",
            "suspension_end",
            "is_suspension_paid",
            "document_url",
            "issued_by",
            "acknowledged_at",
            "is_live",
            "created_at",
        ]
        read_only_fields = ["issued_by", "created_at"]


class PerformanceReviewSerializer(serializers.ModelSerializer[PerformanceReview]):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    reviewer_name = serializers.CharField(source="reviewer.full_name", read_only=True, default=None)
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    rating_display = serializers.CharField(source="get_rating_display", read_only=True)

    class Meta:
        model = PerformanceReview
        fields = [
            "id",
            "employee",
            "employee_name",
            "reviewer",
            "reviewer_name",
            "kind",
            "kind_display",
            "status",
            "status_display",
            "period_start",
            "period_end",
            "rating",
            "rating_display",
            "overall_score",
            "goals",
            "strengths",
            "development_areas",
            "self_assessment",
            "manager_comments",
            "employee_comments",
            "training_recommended",
            "salary_action_recommended",
            "acknowledged_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["acknowledged_at", "completed_at", "created_at", "updated_at"]


class SalaryStructureWriteSerializer(serializers.Serializer[Any]):
    """Payload for ``POST /employees/{id}/set-salary/`` — header + components."""

    effective_from = serializers.DateField()
    reason = serializers.CharField(required=False, allow_blank=True, default="ANNUAL_REVIEW")
    note = serializers.CharField(required=False, allow_blank=True, default="")
    components = serializers.ListField(child=serializers.DictField(), allow_empty=False)
