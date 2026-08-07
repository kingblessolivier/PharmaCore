"""Quarantine release, recall tracing, destruction and count integrity.

These four are where inventory being wrong reaches a patient or the ledger, and
each pins a defect that shipped: a recall that froze unrelated medicines, a
recall that never looked for the units that had already left, a destruction that
destroyed nothing, and a count that could post its variance twice.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from apps.catalog.models import Product
from apps.iam.models import Organization, User
from apps.inventory import counting, disposal, quality, recalls
from apps.inventory.models import (
    BatchRecall,
    InventoryBatch,
    QualityCheck,
    StockCount,
    StockCountItem,
    StockDisposal,
    StockMovement,
)

pytestmark = pytest.mark.django_db

TODAY = date.today()


@pytest.fixture
def org():
    return Organization.objects.create(name="Kigali Depot", type="DEPOT")


@pytest.fixture
def product():
    return Product.objects.create(generic_name="Amoxicillin", strength="500mg")


@pytest.fixture
def receiver(org):
    return User.objects.create_user(username="receiver", password="x", organization=org)


@pytest.fixture
def approver(org):
    return User.objects.create_user(username="approver", password="x", organization=org)


def batch(org, product, qty=100, *, number="B1", days=365, status=None, cost="1000"):
    return InventoryBatch.objects.create(
        organization=org,
        product=product,
        batch_number=number,
        expiry_date=TODAY + timedelta(days=days),
        quantity_available=qty,
        wholesale_cost=Decimal(cost),
        status=status or InventoryBatch.Status.ACTIVE,
    )


# ---------------------------------------------------------------------------
# I-A — quarantine release
# ---------------------------------------------------------------------------


def test_release_moves_quarantined_stock_into_saleable(org, product, receiver, approver):
    held = batch(org, product, status=InventoryBatch.Status.QUARANTINE)
    check = QualityCheck.objects.create(batch=held, inspector=receiver)

    outcome = quality.release(check=check, user=approver, notes="COA verified")

    held.refresh_from_db()
    assert held.status == InventoryBatch.Status.ACTIVE
    assert outcome.check.status == QualityCheck.Status.PASSED
    assert outcome.released_units == 100
    assert "COA verified" in outcome.check.inspection_notes


def test_the_receiver_cannot_release_their_own_delivery(org, product, receiver):
    """A single pair of eyes on both steps is the failure quarantine exists to catch."""
    held = batch(org, product, status=InventoryBatch.Status.QUARANTINE)
    check = QualityCheck.objects.create(batch=held, inspector=receiver)

    with pytest.raises(quality.QualityError, match="second pair of eyes"):
        quality.release(check=check, user=receiver)

    held.refresh_from_db()
    assert held.status == InventoryBatch.Status.QUARANTINE, "stock stays held"


def test_a_decided_check_cannot_be_decided_again(org, product, receiver, approver):
    held = batch(org, product, status=InventoryBatch.Status.QUARANTINE)
    check = QualityCheck.objects.create(batch=held, inspector=receiver)
    quality.reject(check=check, reason="Seal broken", user=approver)

    with pytest.raises(quality.QualityError, match="already"):
        quality.release(check=check, user=approver)


def test_a_rejection_must_say_why(org, product, receiver, approver):
    held = batch(org, product, status=InventoryBatch.Status.QUARANTINE)
    check = QualityCheck.objects.create(batch=held, inspector=receiver)
    with pytest.raises(quality.QualityError, match="say why"):
        quality.reject(check=check, reason="   ", user=approver)


def test_quarantine_queue_reports_age_and_expiry_risk(org, product, receiver):
    held = batch(org, product, days=30, status=InventoryBatch.Status.QUARANTINE)
    QualityCheck.objects.create(batch=held, inspector=receiver)

    rows = quality.quarantine_queue(organization=org)
    assert len(rows) == 1
    assert rows[0]["days_to_expiry"] == 30
    assert quality.summary(organization=org)["expiring_in_quarantine"] == 1


# ---------------------------------------------------------------------------
# I-B — recalls
# ---------------------------------------------------------------------------


def test_a_recall_does_not_freeze_a_different_medicine(org, receiver):
    """``batch_number`` is unique per (org, product) — the same string is reused.

    Freezing on the string alone withdraws unrelated medicine from sale, which is
    a patient-safety event of its own as well as a commercial loss.
    """
    recalled = Product.objects.create(generic_name="Paracetamol", strength="500mg")
    innocent = Product.objects.create(generic_name="Ibuprofen", strength="400mg")
    bad = batch(org, recalled, number="A123")
    good = batch(org, innocent, number="A123")

    recall = BatchRecall.objects.create(
        recall_reference="RC-1", product=recalled, batch_number="A123", reason="Contamination"
    )
    recalls.freeze(recall=recall, user=receiver)

    bad.refresh_from_db()
    good.refresh_from_db()
    assert bad.status == InventoryBatch.Status.RECALLED
    assert good.status == InventoryBatch.Status.ACTIVE, "a different product must be untouched"


def test_a_recall_traces_stock_that_already_left(org, product, receiver):
    """The dangerous units are the ones that moved — those are what a trace finds."""
    from apps.distribution.models import (
        GoodsReceivedNote,
        GRNLine,
        InTransitStock,
        OrderItem,
        StockOrder,
    )

    pharmacy = Organization.objects.create(name="Gasabo Pharmacy", type="RETAIL")
    batch(org, product, 40, number="TRACE-1")

    order = StockOrder.objects.create(depot=org, retail=pharmacy, order_number="PO-T1")
    item = OrderItem.objects.create(order=order, product=product, quantity_ordered=10)
    InTransitStock.objects.create(
        order=order,
        source_org=org,
        destination_org=pharmacy,
        product=product,
        batch_number="TRACE-1",
        expiry_date=TODAY + timedelta(days=365),
        quantity=25,
    )
    grn = GoodsReceivedNote.objects.create(grn_number="GRN-T1", order=order, retail=pharmacy)
    GRNLine.objects.create(
        grn=grn,
        order_item=item,
        product=product,
        batch_number="TRACE-1",
        expiry_date=TODAY + timedelta(days=365),
        quantity_expected=30,
        quantity_received=30,
    )

    trace = recalls.trace_batch(product=product, batch_number="TRACE-1")

    assert trace.units_still_held == 40
    assert trace.units_in_transit == 25
    holders = {h.organization_name: h for h in trace.holders}
    assert holders["Gasabo Pharmacy"].received_units == 30
    assert holders["Kigali Depot"].on_hand_units == 40


def test_a_recall_finds_the_patients_who_were_dispensed_it(org, product, receiver):
    """A Class I recall has to reach people, not just shelves."""
    from apps.retail.models import Dispensing, Sale, SaleBatchAllocation, SaleItem

    pharmacy = Organization.objects.create(name="Nyarugenge Pharmacy", type="RETAIL")
    dispensed = batch(pharmacy, product, 5, number="PT-1")
    sale = Sale.objects.create(organization=pharmacy, sale_number="SALE-1")
    item = SaleItem.objects.create(
        sale=sale, product=product, quantity=2, unit_price=Decimal("1000")
    )
    SaleBatchAllocation.objects.create(sale_item=item, batch=dispensed, quantity=2)
    Dispensing.objects.create(
        sale=sale, patient_name="J. Uwase", patient_id_number="1199", prescriber_name="Dr K."
    )

    trace = recalls.trace_batch(product=product, batch_number="PT-1")

    assert trace.reached_patients is True
    assert trace.units_dispensed == 2
    assert trace.patients[0]["patient_name"] == "J. Uwase"
    assert trace.patients[0]["contactable"] is True


def test_a_recall_cannot_be_closed_while_stock_is_still_held(org, product, receiver):
    batch(org, product, 10, number="OPEN-1")
    recall = BatchRecall.objects.create(
        recall_reference="RC-2", product=product, batch_number="OPEN-1", reason="Defect"
    )
    recalls.freeze(recall=recall, user=receiver)

    with pytest.raises(recalls.RecallError, match="still hold stock"):
        recalls.close(recall=recall, user=receiver)


# ---------------------------------------------------------------------------
# I-C — destruction
# ---------------------------------------------------------------------------


@pytest.fixture
def disposal_record(org, receiver):
    return StockDisposal.objects.create(
        organization=org,
        disposal_no="DSP-1",
        primary_witness=receiver,
        secondary_witness_name="A. Mukamana",
        reason=StockDisposal.Reason.EXPIRED,
    )


def test_destruction_removes_stock_and_writes_it_off(org, product, receiver, disposal_record):
    """Previously this set a status: the stock stayed sellable and the loss never landed."""
    expired = batch(
        org, product, 30, number="EXP-1", days=-10, status=InventoryBatch.Status.EXPIRED
    )
    disposal.add_line(disposal=disposal_record, batch=expired, quantity=30)

    outcome = disposal.confirm_destruction(disposal=disposal_record, user=receiver)

    expired.refresh_from_db()
    assert expired.quantity_available == 0, "the units are gone"
    assert outcome.units_destroyed == 30
    assert outcome.value_written_off == Decimal("30000.00")
    assert StockMovement.objects.filter(
        batch=expired, movement_type=StockMovement.Type.WASTAGE
    ).exists(), "the stock ledger must explain the change"


def test_confirming_destruction_twice_cannot_destroy_the_same_units(
    org, product, receiver, disposal_record
):
    expired = batch(org, product, 30, number="EXP-2", days=-5, status=InventoryBatch.Status.EXPIRED)
    disposal.add_line(disposal=disposal_record, batch=expired, quantity=30)
    disposal.confirm_destruction(disposal=disposal_record, user=receiver)

    with pytest.raises(disposal.DisposalError, match="already been carried out"):
        disposal.confirm_destruction(disposal=disposal_record, user=receiver)

    expired.refresh_from_db()
    assert expired.quantity_available == 0, "not negative — the units left exactly once"


def test_saleable_stock_cannot_be_destroyed(org, product, receiver, disposal_record):
    """Withdraw it from sale first, so the decision is on record."""
    good = batch(org, product, 30, number="GOOD-1")
    disposal.add_line(disposal=disposal_record, batch=good, quantity=30)

    with pytest.raises(disposal.DisposalError, match="withdraw it from sale"):
        disposal.confirm_destruction(disposal=disposal_record, user=receiver)


def test_destruction_needs_two_witnesses(org, product, receiver):
    lone = StockDisposal.objects.create(
        organization=org, disposal_no="DSP-2", primary_witness=receiver, secondary_witness_name=""
    )
    expired = batch(org, product, 5, number="EXP-3", days=-1, status=InventoryBatch.Status.EXPIRED)
    disposal.add_line(disposal=lone, batch=expired, quantity=5)

    with pytest.raises(disposal.DisposalError, match="second witness"):
        disposal.confirm_destruction(disposal=lone, user=receiver)


def test_a_disposal_with_no_lines_destroys_nothing(org, receiver, disposal_record):
    with pytest.raises(disposal.DisposalError, match="Nothing is listed"):
        disposal.confirm_destruction(disposal=disposal_record, user=receiver)


def test_destruction_candidates_include_expired_stock_still_marked_active(org, product):
    batch(org, product, 10, number="STALE", days=-30)  # ACTIVE but past expiry
    rows = disposal.destruction_candidates(organization=org)
    assert [r["batch_number"] for r in rows] == ["STALE"]
    assert rows[0]["is_expired"] is True


# ---------------------------------------------------------------------------
# I-D — count integrity
# ---------------------------------------------------------------------------


def _count_with_variance(org, product, receiver, *, variance=-5):
    counted = batch(org, product, 100, number="CNT-1")
    count = StockCount.objects.create(organization=org, reference_no="SC-1", counter_user=receiver)
    StockCountItem.objects.create(
        stock_count=count,
        batch=counted,
        system_qty=100,
        counted_qty=100 + variance,
        variance_qty=variance,
    )
    return count, counted


def test_a_count_can_only_be_approved_once(org, product, receiver, approver):
    """Approving twice adjusted stock twice and posted the variance twice."""
    count, counted = _count_with_variance(org, product, receiver)

    counting.approve(count=count, user=approver)
    counted.refresh_from_db()
    assert counted.quantity_available == 95

    with pytest.raises(counting.CountError, match="already approved"):
        counting.approve(count=count, user=approver)

    counted.refresh_from_db()
    assert counted.quantity_available == 95, "not 90 — the variance posted exactly once"


def test_the_counter_cannot_approve_their_own_count(org, product, receiver):
    count, counted = _count_with_variance(org, product, receiver)

    with pytest.raises(counting.CountError, match="cannot approve their own"):
        counting.approve(count=count, user=receiver)

    counted.refresh_from_db()
    assert counted.quantity_available == 100, "nothing moved"


def test_variance_report_shows_what_approval_would_post(org, product, receiver):
    count, _ = _count_with_variance(org, product, receiver, variance=-5)
    report = counting.variance_report(count=count)

    assert report["lines_with_variance"] == 1
    assert report["units_lost"] == 5
    assert report["net_value"] == "-5000.00"
    assert report["accuracy_pct"] == 0.0
