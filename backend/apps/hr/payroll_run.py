"""Payroll run lifecycle: build (DRAFT) → submit (PENDING_APPROVAL, via the
approvals engine — no self-approval) → approve (posts the payroll journal to
Finance + generates payslips) → mark paid (bank/MoMo disbursement, manual for now;
the MoMo Disbursements API integration is a later slice)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.approvals import registry
from apps.approvals.models import ApprovalRequest
from apps.approvals.services import request_approval
from apps.documents.models import DocType
from apps.documents.services import generate_document
from apps.finance.services import post_payroll_journal
from apps.hr.models import Employee, PayrollRecord, PayrollRun
from apps.hr.payroll import compute_payroll_line
from apps.iam.audit import record_audit
from apps.iam.models import Organization, User


@transaction.atomic
def build_payroll_run(
    *,
    organization: Organization,
    period_start: Any,
    period_end: Any,
    created_by: User,
    extras_by_employee: dict[int, dict[str, Decimal]] | None = None,
) -> PayrollRun:
    """Compute a payroll run for every active/probationary employee in the org.

    ``extras_by_employee`` maps employee id -> {allowances, overtime_amount,
    bonus_commission, shift_premium, loans_advances, other_deductions}, for the
    inputs the calculator can't infer on its own (attendance/overtime isn't built yet).
    """
    extras_by_employee = extras_by_employee or {}
    run = PayrollRun.objects.create(
        organization=organization,
        period_start=period_start,
        period_end=period_end,
        created_by=created_by,
    )
    employees = Employee.objects.filter(
        organization=organization,
        employment_status__in=[Employee.Status.ACTIVE, Employee.Status.PROBATION],
    )
    for employee in employees:
        extra = extras_by_employee.get(employee.pk, {})
        line = compute_payroll_line(
            employee=employee,
            on_date=period_end,
            allowances=Decimal(str(extra.get("allowances", 0))),
            overtime_amount=Decimal(str(extra.get("overtime_amount", 0))),
            bonus_commission=Decimal(str(extra.get("bonus_commission", 0))),
            shift_premium=Decimal(str(extra.get("shift_premium", 0))),
            loans_advances=Decimal(str(extra.get("loans_advances", 0))),
            other_deductions=Decimal(str(extra.get("other_deductions", 0))),
        )
        PayrollRecord.objects.create(
            run=run,
            employee=employee,
            base_salary=line.base_salary,
            allowances=line.allowances,
            overtime_amount=line.overtime_amount,
            bonus_commission=line.bonus_commission,
            shift_premium=line.shift_premium,
            gross=line.gross,
            paye=line.paye,
            pension_employee=line.pension_employee,
            pension_employer=line.pension_employer,
            maternity_employee=line.maternity_employee,
            maternity_employer=line.maternity_employer,
            cbhi=line.cbhi,
            loans_advances=line.loans_advances,
            other_deductions=line.other_deductions,
            net_pay=line.net_pay,
        )
    return run


def submit_payroll_run(*, run: PayrollRun, requested_by: User) -> ApprovalRequest:
    if run.status != PayrollRun.Status.DRAFT:
        raise ValueError("Only a draft payroll run can be submitted.")
    if not run.records.exists():
        raise ValueError("This payroll run has no employees to pay.")
    approval = request_approval(
        resource_type="hr.payroll_run",
        resource_id=str(run.pk),
        organization=run.organization,
        requested_by=requested_by,
        payload={},
        reason=f"Payroll run {run.period_start}–{run.period_end}",
    )
    run.status = PayrollRun.Status.PENDING_APPROVAL
    run.save(update_fields=["status"])
    return approval


@registry.register("hr.payroll_run")
@transaction.atomic
def _apply_payroll_run(approval: ApprovalRequest) -> None:
    run = PayrollRun.objects.select_related("organization").get(pk=int(approval.resource_id))
    run.status = PayrollRun.Status.APPROVED
    run.approved_by = approval.decided_by
    run.approved_at = timezone.now()
    run.save(update_fields=["status", "approved_by", "approved_at"])

    records = list(run.records.select_related("employee").all())
    totals = {
        "gross": sum((r.gross for r in records), Decimal("0")),
        "paye": sum((r.paye for r in records), Decimal("0")),
        "pension_employee": sum((r.pension_employee for r in records), Decimal("0")),
        "pension_employer": sum((r.pension_employer for r in records), Decimal("0")),
        "maternity_employee": sum((r.maternity_employee for r in records), Decimal("0")),
        "maternity_employer": sum((r.maternity_employer for r in records), Decimal("0")),
        "cbhi": sum((r.cbhi for r in records), Decimal("0")),
        # Occupational Hazards + RAMA roll into PayrollRecord once those statutory
        # lines are added (F3.2). Until then the GL posts a zero, which the
        # payroll journal helper short-circuits — no orphan zero-valued entries.
        "occupational_hazard": Decimal("0"),
        "rama": Decimal("0"),
        "net_pay": sum((r.net_pay for r in records), Decimal("0")),
    }
    period_label = f"{run.period_start}–{run.period_end}"
    post_payroll_journal(
        organization=run.organization,
        period_label=period_label,
        total_gross=totals["gross"],
        total_paye=totals["paye"],
        total_pension_employee=totals["pension_employee"],
        total_pension_employer=totals["pension_employer"],
        total_maternity_employee=totals["maternity_employee"],
        total_maternity_employer=totals["maternity_employer"],
        total_cbhi=totals["cbhi"],
        total_occupational_hazard=totals["occupational_hazard"],
        total_rama=totals["rama"],
        total_net_pay=totals["net_pay"],
        user=approval.decided_by,
        reference_id=str(run.pk),
    )

    for record in records:
        doc = generate_document(
            organization=run.organization,
            doc_type=DocType.PAYSLIP,
            context={
                "employee_name": record.employee.full_name,
                "employee_number": record.employee.employee_number,
                "job_title": record.employee.job_title,
                "period_start": run.period_start,
                "period_end": run.period_end,
                "base_salary": record.base_salary,
                "allowances": record.allowances,
                "overtime_amount": record.overtime_amount,
                "bonus_commission": record.bonus_commission,
                "shift_premium": record.shift_premium,
                "gross": record.gross,
                "paye": record.paye,
                "pension_employee": record.pension_employee,
                "pension_employer": record.pension_employer,
                "maternity_employee": record.maternity_employee,
                "maternity_employer": record.maternity_employer,
                "cbhi": record.cbhi,
                "loans_advances": record.loans_advances,
                "other_deductions": record.other_deductions,
                "net_pay": record.net_pay,
            },
            reference_type="payroll_record",
            reference_id=str(record.pk),
            user=approval.decided_by,
        )
        record.payslip_document_id = str(doc.pk)
        record.save(update_fields=["payslip_document_id"])

    record_audit(
        action="APPROVE_PAYROLL",
        user=approval.decided_by,
        organization=run.organization,
        entity_type="payroll_run",
        entity_id=str(run.pk),
        changes={k: str(v) for k, v in totals.items()},
    )


def mark_payroll_run_paid(*, run: PayrollRun, user: User) -> PayrollRun:
    if run.status != PayrollRun.Status.APPROVED:
        raise ValueError("Only an approved payroll run can be marked paid.")
    run.status = PayrollRun.Status.PAID
    run.save(update_fields=["status"])
    record_audit(
        action="MARK_PAID",
        user=user,
        organization=run.organization,
        entity_type="payroll_run",
        entity_id=str(run.pk),
    )
    return run
