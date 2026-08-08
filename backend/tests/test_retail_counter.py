"""What the till records beyond taking the money.

Four things `complete_sale` never did: the statutory controlled-drugs register,
EBM fiscalisation, promotions, and using up a prescription's refill. Each is now
done by the till at the moment of sale rather than by a person remembering
afterwards — which is the only way any of them stays true.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from apps.catalog.models import Product, ProductBarcode
from apps.finance.models import TaxRecord
from apps.finance.services import ensure_default_accounts, tenant_settings_for
from apps.iam.models import Organization, Role, User
from apps.inventory.models import InventoryBatch
from apps.retail.counter import (
    PrescriptionError,
    consume_prescription,
    evaluate_promotion,
    fiscalise_sale,
    record_controlled_dispensing,
    resolve_barcode,
)
from apps.retail.models import (
    ControlledSubstanceRegister,
    Dispensing,
    POSPromotion,
    Prescription,
    Sale,
    SaleItem,
)
from apps.retail.services import complete_sale

pytestmark = pytest.mark.django_db

TODAY = date(2026, 6, 15)


@pytest.fixture
def org(db: None) -> Organization:
    organization = Organization.objects.create(name="Kicukiro Pharmacy", type="RETAIL")
    ensure_default_accounts(organization)
    return organization


@pytest.fixture
def pharmacist(org: Organization) -> User:
    user = User.objects.create_user(
        username="pharm", password="x", organization=org, is_superuser=True
    )
    return user


def _product(**kw) -> Product:
    defaults = {"generic_name": f"Drug {Product.objects.count() + 1}", "strength": "500mg"}
    defaults.update(kw)
    return Product.objects.create(**defaults)


def _stock(org: Organization, product: Product, qty: int = 100) -> InventoryBatch:
    return InventoryBatch.objects.create(
        organization=org,
        product=product,
        batch_number=f"B{InventoryBatch.objects.count() + 1}",
        quantity_available=qty,
        expiry_date=date.today() + timedelta(days=365),
        wholesale_cost=Decimal("500"),
    )


def _stock_on_hand(org: Organization, product: Product) -> int:
    from django.db.models import Sum

    return int(
        InventoryBatch.objects.filter(organization=org, product=product).aggregate(
            t=Sum("quantity_available")
        )["t"]
        or 0
    )


def _sale(org: Organization, product: Product, qty: int = 2, price: str = "1000") -> Sale:
    sale = Sale.objects.create(organization=org, status=Sale.Status.OPEN)
    SaleItem.objects.create(sale=sale, product=product, quantity=qty, unit_price=Decimal(price))
    return sale


# --------------------------------------------------------------------------- #
# R1 — barcode scanning
# --------------------------------------------------------------------------- #


def test_a_scanned_code_resolves_to_a_product(org: Organization) -> None:
    product = _product()
    ProductBarcode.objects.create(product=product, barcode="5901234123457")

    result = resolve_barcode(organization=org, code="5901234123457")
    assert result is not None
    assert result.product == product
    assert result.units == 1


def test_scanning_a_carton_adds_the_whole_carton(org: Organization) -> None:
    """A carton barcode means a carton. Adding one unit undercharges by the case."""
    product = _product()
    ProductBarcode.objects.create(
        product=product, barcode="CARTON-24", packaging_level="CASE", units_per_level=24
    )

    result = resolve_barcode(organization=org, code="CARTON-24")
    assert result is not None
    assert result.units == 24


def test_an_unknown_code_resolves_to_nothing_rather_than_guessing(org: Organization) -> None:
    assert resolve_barcode(organization=org, code="0000000000000") is None
    assert resolve_barcode(organization=org, code="   ") is None


# --------------------------------------------------------------------------- #
# R5 — promotions are applied, with a reason on every path
# --------------------------------------------------------------------------- #


def _promo(**kw) -> POSPromotion:
    defaults = {
        "code": "SAVE10",
        "name": "Ten percent off",
        "promo_type": POSPromotion.PromoType.PERCENT_DISCOUNT,
        "discount_value": Decimal("10"),
        "valid_from": date(2026, 6, 1),
        "valid_until": date(2026, 6, 30),
    }
    defaults.update(kw)
    return POSPromotion.objects.create(**defaults)


def test_a_percentage_promotion_discounts_the_basket(org: Organization) -> None:
    _promo()
    sale = _sale(org, _product(), qty=2, price="1000")  # 2,000

    outcome = evaluate_promotion(sale=sale, code="SAVE10", on=TODAY)
    assert outcome.applied is True
    assert outcome.discount == Decimal("200.00")


def test_a_flat_promotion_takes_a_fixed_amount(org: Organization) -> None:
    _promo(
        code="OFF500",
        promo_type=POSPromotion.PromoType.FLAT_DISCOUNT,
        discount_value=Decimal("500"),
    )
    sale = _sale(org, _product(), qty=2, price="1000")

    assert evaluate_promotion(sale=sale, code="OFF500", on=TODAY).discount == Decimal("500.00")


def test_bogo_gives_one_free_for_every_two(org: Organization) -> None:
    _promo(code="BOGO", promo_type=POSPromotion.PromoType.BOGO, discount_value=Decimal("0"))
    sale = _sale(org, _product(), qty=5, price="1000")  # two free

    assert evaluate_promotion(sale=sale, code="BOGO", on=TODAY).discount == Decimal("2000.00")


def test_an_expired_code_says_when_it_expired(org: Organization) -> None:
    """A till that silently ignores a code produces an argument at the counter."""
    _promo(valid_until=date(2026, 6, 10))
    sale = _sale(org, _product())

    outcome = evaluate_promotion(sale=sale, code="SAVE10", on=TODAY)
    assert outcome.applied is False
    assert "expired on 2026-06-10" in outcome.reason


def test_a_code_below_its_minimum_spend_says_how_much_more(org: Organization) -> None:
    _promo(min_spend=Decimal("5000"))
    sale = _sale(org, _product(), qty=2, price="1000")  # 2,000

    outcome = evaluate_promotion(sale=sale, code="SAVE10", on=TODAY)
    assert outcome.applied is False
    assert "Spend 3000.00 more" in outcome.reason


def test_an_unknown_code_is_named_in_the_reason(org: Organization) -> None:
    sale = _sale(org, _product())
    assert "NOPE" in evaluate_promotion(sale=sale, code="NOPE", on=TODAY).reason


def test_a_discount_never_exceeds_the_basket(org: Organization) -> None:
    """A promotion is a price reduction, not a refund."""
    _promo(
        code="HUGE",
        promo_type=POSPromotion.PromoType.FLAT_DISCOUNT,
        discount_value=Decimal("999999"),
    )
    sale = _sale(org, _product(), qty=1, price="1000")

    assert evaluate_promotion(sale=sale, code="HUGE", on=TODAY).discount == Decimal("1000.00")


# --------------------------------------------------------------------------- #
# R4 — the controlled register is written by the till
# --------------------------------------------------------------------------- #


def test_dispensing_a_controlled_drug_writes_the_register(
    org: Organization, pharmacist: User
) -> None:
    """It was a separate screen someone typed into, so it always drifted."""
    product = _product(is_controlled_substance=True, requires_prescription=True)
    _stock(org, product, qty=100)
    sale = _sale(org, product, qty=10)

    complete_sale(
        sale=sale,
        payments=[{"method": "CASH", "amount": sale.total}],
        user=pharmacist,
        dispensing={"patient_name": "A. Uwase", "prescriber_name": "Dr Habimana"},
    )

    entry = ControlledSubstanceRegister.objects.get(organization=org, product=product)
    assert entry.quantity == 10
    assert entry.running_balance == 90  # opened at stock on hand, less what went out
    assert entry.patient_name == "A. Uwase"
    assert entry.prescriber_name == "Dr Habimana"
    assert entry.logged_by == pharmacist


def test_an_uncontrolled_sale_writes_no_register_entry(org: Organization, pharmacist: User) -> None:
    product = _product()
    _stock(org, product)
    sale = _sale(org, product)

    complete_sale(sale=sale, payments=[{"method": "CASH", "amount": sale.total}], user=pharmacist)
    assert ControlledSubstanceRegister.objects.count() == 0


def test_the_register_is_not_written_twice_for_one_sale(
    org: Organization, pharmacist: User
) -> None:
    """A retried completion must not double-log a narcotic."""
    product = _product(is_controlled_substance=True)
    _stock(org, product)
    sale = _sale(org, product, qty=5)
    complete_sale(
        sale=sale,
        payments=[{"method": "CASH", "amount": sale.total}],
        user=pharmacist,
        dispensing={"patient_name": "P", "prescriber_name": "D"},
    )

    record_controlled_dispensing(sale=sale, user=pharmacist)
    assert ControlledSubstanceRegister.objects.filter(product=product).count() == 1


# --------------------------------------------------------------------------- #
# R6 — EBM fiscalisation
# --------------------------------------------------------------------------- #


def test_a_completed_sale_is_fiscalised(org: Organization, pharmacist: User) -> None:
    """Rwandan retail must fiscalise. Nothing called the TaxRecord model before."""
    settings = tenant_settings_for(org)
    settings.ebm_sdc_id = "SDC0001"
    settings.ebm_mrc_number = "MRC0001"
    settings.save(update_fields=["ebm_sdc_id", "ebm_mrc_number"])

    product = _product()
    _stock(org, product)
    sale = _sale(org, product, qty=2, price="1180")

    complete_sale(sale=sale, payments=[{"method": "CASH", "amount": sale.total}], user=pharmacist)

    record = TaxRecord.objects.get(organization=org, receipt_number=sale.sale_number)
    assert record.sdc_id == "SDC0001"
    assert record.mrc_number == "MRC0001"
    assert record.qr_code_payload.startswith("https://ebm.rra.gov.rw/verify/")


def test_an_unregistered_till_still_sells_but_records_no_qr(
    org: Organization, pharmacist: User
) -> None:
    """Refusing to sell because a device is unconfigured would close the shop.

    But a QR that resolves to nothing is worse than none — it looks fiscalised.
    """
    product = _product()
    _stock(org, product)
    sale = _sale(org, product)

    complete_sale(sale=sale, payments=[{"method": "CASH", "amount": sale.total}], user=pharmacist)

    record = TaxRecord.objects.get(organization=org, receipt_number=sale.sale_number)
    assert record.sdc_id == "UNREGISTERED"
    assert record.qr_code_payload == ""


def test_a_sale_is_fiscalised_once(org: Organization, pharmacist: User) -> None:
    product = _product()
    _stock(org, product)
    sale = _sale(org, product)
    complete_sale(sale=sale, payments=[{"method": "CASH", "amount": sale.total}], user=pharmacist)

    fiscalise_sale(sale=sale, user=pharmacist)
    assert TaxRecord.objects.filter(receipt_number=sale.sale_number).count() == 1


# --------------------------------------------------------------------------- #
# R7 — dispensing uses up a prescription
# --------------------------------------------------------------------------- #


def _prescription(org: Organization, **kw) -> Prescription:
    defaults = {
        "organization": org,
        "prescription_number": f"RX-{Prescription.objects.count() + 1:04d}",
        "patient_name": "A. Uwase",
        "prescriber_name": "Dr Habimana",
        "issue_date": date(2026, 6, 1),
        "expiry_date": date(2026, 12, 31),
        "refills_allowed": 3,
    }
    defaults.update(kw)
    return Prescription.objects.create(**defaults)


def test_filling_a_prescription_uses_a_refill(org: Organization, pharmacist: User) -> None:
    """It was free text before, so a prescription could be filled forever."""
    prescription = _prescription(org)
    sale = _sale(org, _product())

    consume_prescription(sale=sale, prescription=prescription, user=pharmacist)
    prescription.refresh_from_db()
    assert prescription.refills_used == 1
    assert prescription.status == Prescription.Status.ACTIVE
    dispensing = Dispensing.objects.filter(sale=sale).first()
    assert dispensing is None or dispensing.prescription == prescription


def test_the_last_fill_completes_the_prescription(org: Organization, pharmacist: User) -> None:
    prescription = _prescription(org, refills_allowed=1)
    consume_prescription(sale=_sale(org, _product()), prescription=prescription)

    prescription.refresh_from_db()
    assert prescription.status == Prescription.Status.FULFILLED


def test_an_exhausted_prescription_cannot_be_filled_again(org: Organization) -> None:
    prescription = _prescription(org, refills_allowed=1, refills_used=1)
    with pytest.raises(PrescriptionError, match="have been used"):
        consume_prescription(sale=_sale(org, _product()), prescription=prescription)


def test_another_pharmacys_prescription_is_refused(org: Organization) -> None:
    other = Organization.objects.create(name="Remera Pharmacy", type="RETAIL")
    prescription = _prescription(other)
    with pytest.raises(PrescriptionError, match="another pharmacy"):
        consume_prescription(sale=_sale(org, _product()), prescription=prescription)


# --------------------------------------------------------------------------- #
# Model completeness — the gaps found when auditing what the screens sit on.
#
# The promotion engine had nowhere to write its answer, clinical income was
# billed and never banked, coupons could be redeemed for ever, and a
# prescription did not record what was prescribed.
# --------------------------------------------------------------------------- #


def test_a_promotion_actually_reduces_what_the_customer_pays(org: Organization) -> None:
    """`Sale` had no discount field, so the engine's answer was thrown away."""
    from apps.retail.counter import apply_promotion

    _promo()
    sale = _sale(org, _product(), qty=2, price="1000")
    assert sale.total == Decimal("2000.00")

    outcome = apply_promotion(sale=sale, code="SAVE10", on=TODAY)
    sale.refresh_from_db()

    assert outcome.applied is True
    assert sale.discount_amount == Decimal("200.00")
    assert sale.gross_total == Decimal("2000.00")
    assert sale.total == Decimal("1800.00")  # what is actually charged


def test_a_discount_can_be_taken_back_off(org: Organization) -> None:
    from apps.retail.counter import apply_promotion, clear_promotion

    _promo()
    sale = _sale(org, _product(), qty=2, price="1000")
    apply_promotion(sale=sale, code="SAVE10", on=TODAY)
    clear_promotion(sale=sale)
    sale.refresh_from_db()

    assert sale.promotion is None
    assert sale.total == Decimal("2000.00")


def test_a_coupon_past_its_redemption_limit_is_refused(org: Organization) -> None:
    """A coupon posted online with no cap gets redeemed by the whole city."""
    from apps.retail.counter import apply_promotion

    _promo(max_redemptions=1, times_redeemed=1)
    sale = _sale(org, _product(), qty=2, price="1000")

    outcome = apply_promotion(sale=sale, code="SAVE10", on=TODAY)
    assert outcome.applied is False
    assert "reached its limit" in outcome.reason


def test_redemption_is_counted_at_completion_not_application(
    org: Organization, pharmacist: User
) -> None:
    """An abandoned basket must not burn one of a limited coupon's uses."""
    from apps.retail.counter import apply_promotion

    promo = _promo(max_redemptions=5)
    product = _product()
    _stock(org, product)
    sale = _sale(org, product, qty=2, price="1000")

    apply_promotion(sale=sale, code="SAVE10", on=TODAY)
    promo.refresh_from_db()
    assert promo.times_redeemed == 0  # applied, not yet used

    sale.refresh_from_db()
    complete_sale(sale=sale, payments=[{"method": "CASH", "amount": sale.total}], user=pharmacist)
    promo.refresh_from_db()
    assert promo.times_redeemed == 1


def test_a_clinical_service_fee_reaches_the_ledger(org: Organization, pharmacist: User) -> None:
    """It was billed on the encounter and never banked — 4300 sat empty."""
    from apps.finance.models import Account, JournalLine
    from apps.retail.counter import bill_clinical_service
    from apps.retail.models import ClinicalService, ClinicalServiceRecord

    service = ClinicalService.objects.create(
        service_code="VAC-01", name="Influenza vaccination", fee_amount=Decimal("8000")
    )
    record = ClinicalServiceRecord.objects.create(
        organization=org,
        service=service,
        patient_name="J. Mukamana",
        fee_charged=Decimal("8000"),
    )

    bill_clinical_service(record=record, user=pharmacist)
    record.refresh_from_db()
    assert record.is_paid is True

    revenue = Account.objects.get(organization=org, code="4300")
    posted = JournalLine.objects.filter(account=revenue, side=JournalLine.Side.CREDIT)
    assert posted.count() == 1
    assert posted.first().amount == Decimal("8000.00")


def test_a_clinical_service_is_billed_once(org: Organization, pharmacist: User) -> None:
    from apps.retail.counter import bill_clinical_service
    from apps.retail.models import ClinicalService, ClinicalServiceRecord

    service = ClinicalService.objects.create(
        service_code="BP-01", name="Blood pressure check", fee_amount=Decimal("2000")
    )
    record = ClinicalServiceRecord.objects.create(
        organization=org, service=service, patient_name="P", fee_charged=Decimal("2000")
    )
    bill_clinical_service(record=record, user=pharmacist)
    bill_clinical_service(record=record, user=pharmacist)

    from apps.finance.models import JournalEntry

    assert JournalEntry.objects.filter(reference_type="clinical_service").count() == 1


def test_a_prescription_records_what_was_prescribed(org: Organization) -> None:
    """Without line items nothing can check that what was dispensed matches."""
    from apps.retail.models import PrescriptionItem

    prescription = _prescription(org)
    product = _product()
    item = PrescriptionItem.objects.create(
        prescription=prescription,
        product=product,
        quantity_prescribed=30,
        dosage_instructions="1 tablet three times daily after food",
    )

    assert item.outstanding == 30
    assert item.is_fully_dispensed is False

    item.quantity_dispensed = 10  # a part-fill
    item.save(update_fields=["quantity_dispensed"])
    assert item.outstanding == 20
    assert item.is_fully_dispensed is False

    item.quantity_dispensed = 30
    item.save(update_fields=["quantity_dispensed"])
    assert item.is_fully_dispensed is True
    assert item.outstanding == 0


def test_a_discounted_sale_still_balances_and_gets_the_vat_right(
    org: Organization, pharmacist: User
) -> None:
    """Netting the discount into `total` broke the ledger until this was fixed.

    The till debited the discounted amount and credited full revenue, so **any**
    discounted sale failed to post. And the VAT has to follow the consideration
    actually received: charging it on the pre-discount amount overstates output
    VAT on every promotion, and that number gets filed.
    """
    from apps.finance.models import Account, JournalEntry, JournalLine
    from apps.retail.counter import apply_promotion

    _promo(code="TEN", discount_value=Decimal("10"))
    product = _product(tax_class="B")
    _stock(org, product)

    # 2 × 1,180 VAT-inclusive = 2,360 gross; 10% = 236 discount.
    sale = Sale.objects.create(organization=org, status=Sale.Status.OPEN)
    SaleItem.objects.create(
        sale=sale, product=product, quantity=2, unit_price=Decimal("1180"), tax_rate=Decimal("18")
    )
    apply_promotion(sale=sale, code="TEN", on=TODAY)
    sale.refresh_from_db()
    assert sale.total == Decimal("2124.00")

    complete_sale(sale=sale, payments=[{"method": "CASH", "amount": sale.total}], user=pharmacist)

    entry = JournalEntry.objects.get(
        organization=org, reference_type="sale", reference_id=str(sale.pk)
    )
    debits = sum(
        (ln.amount for ln in entry.lines.all() if ln.side == JournalLine.Side.DEBIT), Decimal("0")
    )
    credits = sum(
        (ln.amount for ln in entry.lines.all() if ln.side == JournalLine.Side.CREDIT), Decimal("0")
    )
    assert debits == credits  # the whole point

    # The discount given away is visible, not a quiet reduction in the top line.
    discounts = Account.objects.get(organization=org, code="4900")
    assert entry.lines.filter(account=discounts, side=JournalLine.Side.DEBIT).exists()

    # VAT is on 2,124, not on 2,360.
    vat_line = entry.lines.get(account__code="2300")
    assert vat_line.amount == Decimal("324.00")


# --------------------------------------------------------------------------- #
# Offline replay — both bugs here were found by a live walkthrough, not by the
# unit tests, so they are pinned.
# --------------------------------------------------------------------------- #


def test_a_failed_replay_never_reports_success(org: Organization) -> None:
    """The worst bug in this feature, and the one hardest to notice.

    A replay that cannot complete used to leave a Sale row holding the
    idempotency key. Every later retry then short-circuited on that row and
    returned `replayed: true` for a sale that never happened — so the till
    dropped it from its queue and the sale vanished. Silently losing a sale is
    worse than the double-sell the key exists to prevent.
    """
    from apps.retail.models import Sale
    from rest_framework.test import APIClient

    # A prescription-only product completed by a non-pharmacist always fails.
    product = _product(requires_prescription=True)
    _stock(org, product)
    cashier = User.objects.create_user(username="till", password="x", organization=org)
    # A till operator is a cashier: they may ring up a sale (`sale.create`) but
    # not dispense a prescription-only item, which is what makes this replay fail.
    cashier.roles.add(Role.objects.get(code="CASHIER"))

    client = APIClient()
    client.force_authenticate(user=cashier)
    payload = {
        "organization": org.pk,
        "client_reference": "abc-123",
        "items": [{"product": product.pk, "quantity": 1, "unit_price": "500"}],
        "payments": [{"method": "CASH", "amount": "500"}],
    }

    responses = [client.post("/api/retail/offline/sync/", payload, format="json") for _ in range(3)]

    assert [r.status_code for r in responses] == [400, 400, 400]
    # Never a phantom success.
    assert not any(r.data.get("replayed") for r in responses if isinstance(r.data, dict))
    # One basket kept for review, not three.
    assert Sale.objects.filter(organization=org, client_reference="abc-123").count() == 1
    # And nothing left the shelf.
    assert _stock_on_hand(org, product) == 100


def test_a_successful_replay_sells_the_goods_once(org: Organization, pharmacist: User) -> None:
    from rest_framework.test import APIClient

    product = _product()
    _stock(org, product, qty=50)

    client = APIClient()
    client.force_authenticate(user=pharmacist)
    payload = {
        "organization": org.pk,
        "client_reference": "xyz-789",
        "items": [{"product": product.pk, "quantity": 3, "unit_price": "1000"}],
        "payments": [{"method": "CASH", "amount": "3000"}],
    }

    first = client.post("/api/retail/offline/sync/", payload, format="json")
    second = client.post("/api/retail/offline/sync/", payload, format="json")
    third = client.post("/api/retail/offline/sync/", payload, format="json")

    assert first.status_code == 201 and first.data["replayed"] is False
    assert second.data["replayed"] is True and third.data["replayed"] is True
    assert first.data["sale"] == second.data["sale"] == third.data["sale"]
    assert _stock_on_hand(org, product) == 47  # once, not three times


def test_an_offline_sale_is_numbered(org: Organization, pharmacist: User) -> None:
    """`sale_number` is unique with a blank default, so two unnumbered sales
    collide on the constraint — which is exactly what happened live."""
    from apps.retail.models import Sale
    from rest_framework.test import APIClient

    product = _product()
    _stock(org, product, qty=50)
    client = APIClient()
    client.force_authenticate(user=pharmacist)

    for reference in ("one", "two"):
        response = client.post(
            "/api/retail/offline/sync/",
            {
                "organization": org.pk,
                "client_reference": reference,
                "items": [{"product": product.pk, "quantity": 1, "unit_price": "100"}],
                "payments": [{"method": "CASH", "amount": "100"}],
            },
            format="json",
        )
        assert response.status_code == 201, response.data

    numbers = set(
        Sale.objects.filter(organization=org, client_reference__in=["one", "two"]).values_list(
            "sale_number", flat=True
        )
    )
    assert "" not in numbers
    assert len(numbers) == 2


def test_the_scan_endpoint_resolves_a_carton(org: Organization, pharmacist: User) -> None:
    """The happy path 500'd live because `PharmacyProduct` was imported from the
    wrong app — the earlier walkthrough only scanned an unknown code, which
    returns before that line."""
    from rest_framework.test import APIClient

    product = _product()
    _stock(org, product, qty=100)
    ProductBarcode.objects.create(
        product=product, barcode="CASE-12", packaging_level="CASE", units_per_level=12
    )

    client = APIClient()
    client.force_authenticate(user=pharmacist)
    response = client.get(f"/api/retail/counter/scan/?organization={org.pk}&code=CASE-12")

    assert response.status_code == 200, response.data
    assert response.data["units"] == 12
    assert response.data["on_hand"] == 100
