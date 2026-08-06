"""Batch supplier settlement — payment runs (roadmap F7).

Paying bills one at a time means no single approval ever covers the total and
there is no file to hand the bank. A run fixes both: one approval (two above
the threshold), one file, and payments that post only after the money moved.
"""

from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal

import pytest
from apps.approvals.models import ApprovalRequest
from apps.approvals.services import claim, decide
from apps.catalog.models import Supplier
from apps.finance.models import JournalEntry, PaymentRun, SupplierBill
from apps.finance.services import (
    DUAL_APPROVAL_THRESHOLD,
    PaymentRunError,
    build_disbursement_file,
    create_payment_run,
    disburse_payment_run,
    lock_payment_run,
    record_supplier_bill,
    submit_payment_run,
)
from apps.iam.models import Organization, Role, User
from rest_framework.test import APIClient


@pytest.fixture
def org(db: None) -> Organization:
    return Organization.objects.create(name="Kigali Depot", type="DEPOT")


@pytest.fixture
def supplier(db: None) -> Supplier:
    return Supplier.objects.create(name="Global Pharma Imports", phone="250788000111")


@pytest.fixture
def accountant(org: Organization) -> User:
    user = User.objects.create_user(username="apclerk", password="x", organization=org)
    user.roles.add(Role.objects.get(code="ACCOUNTANT"))
    return user


@pytest.fixture
def finance_manager(org: Organization) -> User:
    user = User.objects.create_user(username="finmgr", password="x", organization=org)
    user.roles.add(Role.objects.get(code="ORG_ADMIN"))
    return user


@pytest.fixture
def director(org: Organization) -> User:
    user = User.objects.create_user(username="director", password="x", organization=org)
    user.roles.add(Role.objects.get(code="ORG_ADMIN"))
    return user


def _bill(org: Organization, supplier: Supplier, amount: str, number: str) -> SupplierBill:
    return record_supplier_bill(
        organization=org,
        supplier=supplier,
        bill_number=number,
        bill_date=date.today(),
        due_date=date.today(),
        total_amount=Decimal(amount),
        user=None,
    )


def _client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _approve(approval: ApprovalRequest, user: User) -> ApprovalRequest:
    claim(approval=approval, user=user)
    return decide(approval=approval, user=user, approve=True)


def _latest_approval(run: PaymentRun) -> ApprovalRequest:
    return ApprovalRequest.objects.filter(
        resource_type="finance.payment_run", resource_id=str(run.pk)
    ).latest("id")


# ---------------------------------------------------------------------------
# Building a run
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_run_totals_the_amount_still_due_on_each_bill(org, supplier, accountant) -> None:
    bills = [_bill(org, supplier, "300000", "B-1"), _bill(org, supplier, "200000", "B-2")]
    run = create_payment_run(organization=org, bills=bills, user=accountant)

    assert run.status == PaymentRun.Status.DRAFT
    assert run.run_number.startswith("PRUN-")
    assert run.total_amount == Decimal("500000.00")
    assert run.line_count == 2
    assert run.approvals_required == 1


@pytest.mark.django_db
def test_run_needs_at_least_one_bill(org, accountant) -> None:
    with pytest.raises(PaymentRunError, match="at least one bill"):
        create_payment_run(organization=org, bills=[], user=accountant)


@pytest.mark.django_db
def test_a_bill_cannot_sit_in_two_open_runs(org, supplier, accountant) -> None:
    """Otherwise both files would tell the bank to pay it."""
    bill = _bill(org, supplier, "100000", "B-1")
    create_payment_run(organization=org, bills=[bill], user=accountant)
    with pytest.raises(PaymentRunError, match="already in an open payment run"):
        create_payment_run(organization=org, bills=[bill], user=accountant)


@pytest.mark.django_db
def test_large_run_demands_two_signatures(org, supplier, accountant) -> None:
    amount = DUAL_APPROVAL_THRESHOLD + Decimal("1")
    run = create_payment_run(
        organization=org, bills=[_bill(org, supplier, str(amount), "B-BIG")], user=accountant
    )
    assert run.approvals_required == 2


# ---------------------------------------------------------------------------
# Approval
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_single_approval_approves_and_emits_the_file(
    org, supplier, accountant, finance_manager
) -> None:
    run = create_payment_run(
        organization=org, bills=[_bill(org, supplier, "400000", "B-1")], user=accountant
    )
    approval = submit_payment_run(run=run, user=accountant)
    run.refresh_from_db()
    assert run.status == PaymentRun.Status.AWAITING_APPROVAL

    _approve(approval, finance_manager)
    run.refresh_from_db()
    assert run.status == PaymentRun.Status.APPROVED
    assert run.approved_at is not None
    assert run.disbursement_file
    assert run.disbursement_filename.endswith("-bank.csv")


@pytest.mark.django_db
def test_first_of_two_approvals_does_not_release_the_money(
    org, supplier, accountant, finance_manager
) -> None:
    amount = DUAL_APPROVAL_THRESHOLD + Decimal("100000")
    run = create_payment_run(
        organization=org, bills=[_bill(org, supplier, str(amount), "B-BIG")], user=accountant
    )
    _approve(submit_payment_run(run=run, user=accountant), finance_manager)

    run.refresh_from_db()
    assert run.status == PaymentRun.Status.AWAITING_APPROVAL
    assert run.approvals_received == 1
    assert not run.disbursement_file


@pytest.mark.django_db
def test_second_approval_must_come_from_someone_else(
    org, supplier, accountant, finance_manager, director
) -> None:
    """The follow-up request is raised in the first approver's name, so the
    engine's no-self-approval rule makes a rubber stamp impossible."""
    from apps.approvals.services import ApprovalError

    amount = DUAL_APPROVAL_THRESHOLD + Decimal("100000")
    run = create_payment_run(
        organization=org, bills=[_bill(org, supplier, str(amount), "B-BIG")], user=accountant
    )
    _approve(submit_payment_run(run=run, user=accountant), finance_manager)

    second = _latest_approval(run)
    with pytest.raises(ApprovalError):
        claim(approval=second, user=finance_manager)

    _approve(second, director)
    run.refresh_from_db()
    assert run.status == PaymentRun.Status.APPROVED
    assert run.approvals_received == 2


# ---------------------------------------------------------------------------
# The disbursement file
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_momo_file_carries_msisdn_amount_and_idempotency_key(org, supplier, accountant) -> None:
    bill = _bill(org, supplier, "150000", "B-MOMO")
    run = create_payment_run(
        organization=org,
        bills=[bill],
        method=PaymentRun.Method.MOBILE_MONEY,
        user=accountant,
    )
    name, body = build_disbursement_file(run)

    assert name.endswith("-momo.csv")
    rows = list(csv.reader(io.StringIO(body)))
    assert rows[0] == ["msisdn", "amount", "reference", "idempotency_key"]
    line = run.lines.first()
    assert rows[1] == ["250788000111", "150000.00", "B-MOMO", f"{run.pk}:{bill.pk}"]
    assert line.idempotency_key == f"{run.pk}:{bill.pk}"


@pytest.mark.django_db
def test_bank_file_carries_account_details(org, supplier, accountant) -> None:
    run = create_payment_run(
        organization=org,
        bills=[_bill(org, supplier, "150000", "B-BANK")],
        method=PaymentRun.Method.BANK_TRANSFER,
        user=accountant,
    )
    _, body = build_disbursement_file(run)
    rows = list(csv.reader(io.StringIO(body)))
    assert rows[0] == ["account_number", "account_name", "amount", "reference", "idempotency_key"]
    assert rows[1][1] == "Global Pharma Imports"


# ---------------------------------------------------------------------------
# Disbursement
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_disbursement_settles_every_bill_and_posts_the_gl(
    org, supplier, accountant, finance_manager
) -> None:
    bills = [_bill(org, supplier, "300000", "B-1"), _bill(org, supplier, "200000", "B-2")]
    run = create_payment_run(organization=org, bills=bills, user=accountant)
    _approve(submit_payment_run(run=run, user=accountant), finance_manager)

    run.refresh_from_db()
    disburse_payment_run(run=run, user=accountant)

    run.refresh_from_db()
    assert run.status == PaymentRun.Status.DISBURSED
    for bill in bills:
        bill.refresh_from_db()
        assert bill.status == SupplierBill.Status.PAID
        assert bill.amount_due == Decimal("0.00")
    # Dr AP / Cr cash, one entry per bill payment.
    assert JournalEntry.objects.filter(reference_type="supplier_bill_payment").count() == 2


@pytest.mark.django_db
def test_re_disbursing_pays_nothing_twice(org, supplier, accountant, finance_manager) -> None:
    bill = _bill(org, supplier, "300000", "B-1")
    run = create_payment_run(organization=org, bills=[bill], user=accountant)
    _approve(submit_payment_run(run=run, user=accountant), finance_manager)

    run.refresh_from_db()
    disburse_payment_run(run=run, user=accountant)
    run.refresh_from_db()
    disburse_payment_run(run=run, user=accountant)

    bill.refresh_from_db()
    assert bill.amount_paid == Decimal("300000.00")
    assert bill.payments.count() == 1


@pytest.mark.django_db
def test_an_unapproved_run_cannot_disburse(org, supplier, accountant) -> None:
    run = create_payment_run(
        organization=org, bills=[_bill(org, supplier, "300000", "B-1")], user=accountant
    )
    with pytest.raises(PaymentRunError, match="approved run"):
        disburse_payment_run(run=run, user=accountant)


@pytest.mark.django_db
def test_locking_needs_a_disbursed_run(org, supplier, accountant) -> None:
    run = create_payment_run(
        organization=org, bills=[_bill(org, supplier, "300000", "B-1")], user=accountant
    )
    with pytest.raises(PaymentRunError, match="disbursed run"):
        lock_payment_run(run=run, user=accountant)


# ---------------------------------------------------------------------------
# API surface
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_api_round_trip_from_draft_to_locked(org, supplier, accountant, finance_manager) -> None:
    bill = _bill(org, supplier, "250000", "B-API")
    client = _client(finance_manager)

    created = client.post(
        "/api/finance/payment-runs/",
        {"organization": org.pk, "bills": [bill.pk], "method": "MOBILE_MONEY"},
        format="json",
    )
    assert created.status_code == 201, created.content
    run_id = created.json()["id"]
    assert created.json()["total_amount"] == "250000.00"

    submitted = client.post(f"/api/finance/payment-runs/{run_id}/submit/")
    assert submitted.status_code == 201
    _approve(_latest_approval(PaymentRun.objects.get(pk=run_id)), accountant)

    downloaded = client.get(f"/api/finance/payment-runs/{run_id}/disbursement-file/")
    assert downloaded.status_code == 200
    assert downloaded["Content-Type"] == "text/csv"
    assert b"msisdn" in downloaded.content

    disbursed = client.post(f"/api/finance/payment-runs/{run_id}/disburse/")
    assert disbursed.status_code == 200
    assert disbursed.json()["status"] == "DISBURSED"

    locked = client.post(f"/api/finance/payment-runs/{run_id}/lock/")
    assert locked.status_code == 200
    assert locked.json()["status"] == "LOCKED"


@pytest.mark.django_db
def test_file_download_refused_before_approval(org, supplier, accountant, finance_manager) -> None:
    run = create_payment_run(
        organization=org, bills=[_bill(org, supplier, "100000", "B-1")], user=accountant
    )
    resp = _client(finance_manager).get(f"/api/finance/payment-runs/{run.pk}/disbursement-file/")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_runs_are_scoped_to_visible_organizations(org, supplier, accountant) -> None:
    other = Organization.objects.create(name="Rival Depot", type="DEPOT")
    outsider = User.objects.create_user(username="outsider", password="x", organization=other)
    outsider.roles.add(Role.objects.get(code="ACCOUNTANT"))
    create_payment_run(
        organization=org, bills=[_bill(org, supplier, "100000", "B-1")], user=accountant
    )
    resp = _client(outsider).get("/api/finance/payment-runs/")
    assert resp.status_code == 200
    results = resp.json()
    rows = results["results"] if isinstance(results, dict) else results
    assert rows == []
