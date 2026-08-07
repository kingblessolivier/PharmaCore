from __future__ import annotations

from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.hr.views import (
    AttendanceLogViewSet,
    EmployeeViewSet,
    LeaveRequestViewSet,
    PayrollRunViewSet,
    ShiftRosterViewSet,
    StatutoryRateViewSet,
)
from apps.hr.views_people import (
    ApplicantViewSet,
    ChecklistItemViewSet,
    CompetencyAssessmentViewSet,
    CPDRecordViewSet,
    DisciplinaryActionViewSet,
    EmploymentContractViewSet,
    InterviewSlotViewSet,
    JobRequisitionViewSet,
    LeaveBalanceViewSet,
    LeaveTypeViewSet,
    LoanAdvanceViewSet,
    OnboardingViewSet,
    PayrollAdjustmentViewSet,
    PeopleOverviewView,
    PerformanceReviewViewSet,
    SalaryRevisionViewSet,
    SalaryStructureViewSet,
    StatutoryFilingViewSet,
    TerminationViewSet,
    TimesheetViewSet,
    TrainingRecordViewSet,
)

router = DefaultRouter()
# --- core master data (pre-existing) ---
router.register("employees", EmployeeViewSet, basename="employee")
router.register("statutory-rates", StatutoryRateViewSet, basename="statutory-rate")
router.register("payroll-runs", PayrollRunViewSet, basename="payroll-run")
router.register("attendance", AttendanceLogViewSet, basename="attendance")
router.register("roster", ShiftRosterViewSet, basename="roster")
router.register("leave", LeaveRequestViewSet, basename="leave")

# --- contract & pay ---
router.register("contracts", EmploymentContractViewSet, basename="employment-contract")
router.register("salary-structures", SalaryStructureViewSet, basename="salary-structure")
router.register("salary-revisions", SalaryRevisionViewSet, basename="salary-revision")
router.register("payroll-adjustments", PayrollAdjustmentViewSet, basename="payroll-adjustment")

# --- leave & time ---
router.register("leave-types", LeaveTypeViewSet, basename="leave-type")
router.register("leave-balances", LeaveBalanceViewSet, basename="leave-balance")
router.register("timesheets", TimesheetViewSet, basename="timesheet")

# --- loans ---
router.register("loans", LoanAdvanceViewSet, basename="loan-advance")

# --- recruitment & onboarding ---
router.register("requisitions", JobRequisitionViewSet, basename="job-requisition")
router.register("applicants", ApplicantViewSet, basename="applicant")
router.register("interviews", InterviewSlotViewSet, basename="interview-slot")
router.register("onboarding", OnboardingViewSet, basename="onboarding")
router.register("checklist-items", ChecklistItemViewSet, basename="checklist-item")

# --- offboarding ---
router.register("terminations", TerminationViewSet, basename="termination")

# --- development & compliance ---
router.register("training", TrainingRecordViewSet, basename="training-record")
router.register("cpd", CPDRecordViewSet, basename="cpd-record")
router.register("competencies", CompetencyAssessmentViewSet, basename="competency")
router.register("disciplinary", DisciplinaryActionViewSet, basename="disciplinary-action")
router.register("reviews", PerformanceReviewViewSet, basename="performance-review")

# --- statutory ---
router.register("filings", StatutoryFilingViewSet, basename="statutory-filing")

urlpatterns = [
    path("overview/", PeopleOverviewView.as_view(), name="people-overview"),
    *router.urls,
]
