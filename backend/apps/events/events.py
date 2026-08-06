"""First-class domain events (ADR-010).

Every value here is a *stable string* used on the wire and in storage; changing
one is a breaking change for every consumer. Keep the set small, named clearly,
and avoid free-form ``source_doc_type`` strings — extend the enum instead.
"""

from __future__ import annotations

from django.db import models


class EventType(models.TextChoices):
    # Sales & retail
    SALE_FINALISED = "SaleFinalised", "Sale finalised (POS completed)"
    SALE_VOIDED = "SaleVoided", "Sale voided"

    # Procurement & inventory
    PURCHASE_ORDER_APPROVED = "PurchaseOrderApproved", "Purchase order approved"
    GOODS_RECEIVED_NOTE_POSTED = "GoodsReceivedNotePosted", "Goods receipt posted to stock"
    INVENTORY_ADJUSTED = "InventoryAdjusted", "Inventory adjusted (write-on/off, recount)"
    STOCK_DISPOSED = "StockDisposed", "Stock disposed / destroyed"

    # Distribution (B2B)
    STOCK_ORDER_APPROVED = "StockOrderApproved", "Inter-branch stock order approved"
    STOCK_ORDER_SHIPPED = "StockOrderShipped", "Inter-branch stock order shipped"
    STOCK_ORDER_RECEIVED = "StockOrderReceived", "Inter-branch stock order received"

    # Finance — customer receivables
    CUSTOMER_INVOICE_ISSUED = "CustomerInvoiceIssued", "Customer invoice issued"
    PAYMENT_RECEIVED = "PaymentReceived", "Customer payment received"
    CREDIT_LIMIT_CHANGED = "CreditLimitChanged", "Customer credit limit changed"
    CREDIT_HOLD_ENGAGED = "CreditHoldEngaged", "Customer credit hold engaged"

    # Finance — payables
    SUPPLIER_BILL_APPROVED = "SupplierBillApproved", "Supplier bill approved (3-way matched)"
    PAYMENT_MADE = "PaymentMade", "Supplier payment made"

    # HR — people lifecycle
    EMPLOYEE_HIRED = "EmployeeHired", "Employee hired"
    EMPLOYEE_TERMINATED = "EmployeeTerminated", "Employee terminated"

    # HR — payroll
    TIMESHEET_APPROVED = "TimesheetApproved", "Timesheet approved"
    PAYROLL_RUN_APPROVED = "PayrollRunApproved", "Payroll run approved"
    PAYSLIP_PUBLISHED = "PayslipPublished", "Payslip published"

    # Statutory / tax
    STATUTORY_FILING_GENERATED = "StatutoryFilingGenerated", "Statutory filing generated"
    STATUTORY_PAYMENT_CONFIRMED = "StatutoryPaymentConfirmed", "Statutory payment confirmed"

    # Fiscal period lifecycle
    FISCAL_PERIOD_OPENED = "FiscalPeriodOpened", "Fiscal period opened"
    FISCAL_PERIOD_CLOSED = "FiscalPeriodClosed", "Fiscal period closed"
    PERIOD_REOPENED = "PeriodReopened", "Period reopened (audited)"

    # End-of-day / end-of-month
    EOD_CLOSE_FINALISED = "EODCloseFinalised", "EOD closeout finalised"
    EOM_CLOSE_FINALISED = "EOMCloseFinalised", "EOM closeout finalised"

    # Approvals lifecycle (every approval action emits one — feeds Reporting
    # without coupling Reporting to the approvals engine)
    APPROVAL_REQUESTED = "ApprovalRequested", "Approval requested"
    APPROVAL_CLAIMED = "ApprovalClaimed", "Approval claimed"
    APPROVAL_GRANTED = "ApprovalGranted", "Approval granted"
    APPROVAL_REJECTED = "ApprovalRejected", "Approval rejected"
    APPROVAL_RETURNED = "ApprovalReturned", "Approval returned to requester"
    APPROVAL_ESCALATED = "ApprovalEscalated", "Approval escalated"
    APPROVAL_SLA_BREACHED = "ApprovalSLABreached", "Approval SLA breached"