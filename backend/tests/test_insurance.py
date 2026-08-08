"""Insurance: eligibility, the co-payment split, claims and reconciliation.

The split is where this subsystem earns its keep or loses money quietly, so most
of these are arithmetic: the patient's share plus the insurer's share must equal
the basket, every time, including when percentages do not divide cleanly.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from apps.catalog.models import Product
from apps.iam.models import Organization
from apps.insurance import claims as claim_service
from apps.insurance import eligibility as elig
from apps.insurance import reconciliation as recon
from apps.insurance.models import (
    Claim,
    InsuranceScheme,
    MemberPolicy,
    RemittanceAdvice,
    SchemeFormulary,
)
from django.utils import timezone

pytestmark = pytest.mark.django_db


def today() -> date:
    """The same clock the product reads, at the moment it is asked.

    This was `TODAY = date.today()` evaluated once at module import, which is
    wrong twice over: it is the operating system's date rather than Django's
    (the two differ on a UTC server — see D22), and it freezes. The suite takes
    five minutes, so a run starting at 23:59 asserted against yesterday while the
    code under test had already moved on, and `days_to_expiry == 30` came back
    29. That is a real failure of the test, not of the product.
    """
    return timezone.localdate()


@pytest.fixture
def org():
    return Organization.objects.create(name="Kigali Pharmacy", type="RETAIL")


@pytest.fixture
def cbhi(org):
    """CBHI as it actually works: 10% co-pay, RWF 200 flat facility fee."""
    return InsuranceScheme.objects.create(
        organization=org,
        code="CBHI",
        name="CBHI / Mutuelle de Santé",
        kind=InsuranceScheme.Kind.CBHI,
        default_copay_pct=Decimal("10.00"),
        consultation_fee=Decimal("200.00"),
        claim_window_days=30,
    )


@pytest.fixture
def product():
    return Product.objects.create(generic_name="Amoxicillin", strength="500mg")


@pytest.fixture
def member(cbhi):
    return MemberPolicy.objects.create(
        scheme=cbhi,
        member_number="CBHI-001",
        full_name="J. Uwase",
        valid_from=today() - timedelta(days=30),
        valid_to=today() + timedelta(days=300),
    )


def cover(scheme, product, **kwargs):
    return SchemeFormulary.objects.create(scheme=scheme, product=product, **kwargs)


# ---------------------------------------------------------------------------
# Eligibility
# ---------------------------------------------------------------------------


def test_a_valid_card_is_eligible(member):
    verdict = elig.check_eligibility(member_number="CBHI-001")
    assert verdict.is_eligible
    assert verdict.copay_pct == Decimal("10.00")
    assert verdict.consultation_fee == Decimal("200.00")


def test_an_expired_card_is_refused_before_dispensing(member):
    """Found at claim time this is a debt already incurred; found here it is not."""
    member.valid_to = today() - timedelta(days=1)
    member.save()
    verdict = elig.check_eligibility(member_number="CBHI-001")
    assert verdict.is_eligible is False
    assert "expired" in verdict.reason.lower()


def test_a_suspended_membership_is_refused(member):
    member.status = MemberPolicy.Status.SUSPENDED
    member.save()
    assert elig.check_eligibility(member_number="CBHI-001").is_eligible is False


def test_an_unknown_card_is_refused_not_crashed():
    verdict = elig.check_eligibility(member_number="NOPE")
    assert verdict.is_eligible is False
    assert verdict.policy is None


# ---------------------------------------------------------------------------
# The co-payment split
# ---------------------------------------------------------------------------


def test_cbhi_splits_ten_percent_to_the_patient(member, cbhi, product):
    cover(cbhi, product)
    split = elig.split_basket(
        policy=member,
        lines=[{"product": product, "quantity": 10, "unit_price": Decimal("1000")}],
    )
    assert split.gross == Decimal("10000.00")
    # 10% of 10,000 = 1,000, plus the RWF 200 facility fee the insurer never covers.
    assert split.patient_total == Decimal("1200.00")
    assert split.insurer_total == Decimal("9000.00")
    assert split.reconciles()


def test_ubudehe_category_one_pays_nothing(cbhi, product):
    """The rate belongs to the member, not the scheme — the poorest are fully covered."""
    subsidised = MemberPolicy.objects.create(
        scheme=cbhi,
        member_number="CBHI-UB1",
        full_name="Poorest Household",
        ubudehe_category=1,
        copay_pct_override=Decimal("0.00"),
        valid_from=today() - timedelta(days=10),
        valid_to=today() + timedelta(days=300),
    )
    cover(cbhi, product)
    split = elig.split_basket(
        policy=subsidised,
        lines=[{"product": product, "quantity": 10, "unit_price": Decimal("1000")}],
        include_consultation_fee=False,
    )
    assert split.patient_total == Decimal("0.00")
    assert split.insurer_total == Decimal("10000.00")
    assert split.reconciles()


def test_a_product_not_on_the_formulary_is_the_patients_in_full(member, product):
    """Silence must never mean coverage — the rejection would arrive weeks later."""
    split = elig.split_basket(
        policy=member,
        lines=[{"product": product, "quantity": 5, "unit_price": Decimal("2000")}],
        include_consultation_fee=False,
    )
    assert split.patient_total == Decimal("10000.00")
    assert split.insurer_total == Decimal("0.00")
    assert len(split.uncovered_lines) == 1
    assert split.reconciles()


def test_a_price_ceiling_puts_the_excess_on_the_patient(member, cbhi, product):
    cover(cbhi, product, max_price_per_unit=Decimal("800"))
    split = elig.split_basket(
        policy=member,
        lines=[{"product": product, "quantity": 10, "unit_price": Decimal("1000")}],
        include_consultation_fee=False,
    )
    # Scheme considers 8,000. Patient: 10% of that (800) + the 2,000 excess.
    assert split.insurer_total == Decimal("7200.00")
    assert split.patient_total == Decimal("2800.00")
    assert split.reconciles()


def test_the_split_never_loses_a_franc_to_rounding(member, cbhi, product):
    """Percentages rounded per line drift from the total; the patient absorbs it once."""
    cover(cbhi, product)
    other = Product.objects.create(generic_name="Ibuprofen", strength="400mg")
    cover(cbhi, other)
    split = elig.split_basket(
        policy=member,
        lines=[
            {"product": product, "quantity": 3, "unit_price": Decimal("333.33")},
            {"product": other, "quantity": 7, "unit_price": Decimal("111.11")},
        ],
        include_consultation_fee=False,
    )
    assert split.reconciles(), "the basket must divide exactly"
    assert split.patient_total + split.insurer_total == split.gross


def test_quote_is_read_only(member, cbhi, product):
    """A quote that created claims would leave one behind on every changed mind."""
    cover(cbhi, product)
    before = Claim.objects.count()
    body = elig.quote(
        member_number="CBHI-001",
        lines=[{"product": product, "quantity": 2, "unit_price": Decimal("500")}],
    )
    assert body["eligible"] is True
    assert Claim.objects.count() == before


# ---------------------------------------------------------------------------
# Claims
# ---------------------------------------------------------------------------


def _insured_sale(org, product, qty=10, price="1000"):
    from apps.retail.models import Sale, SaleItem
    from django.utils import timezone

    sale = Sale.objects.create(
        organization=org,
        sale_number=f"SALE-{Sale.objects.count() + 1:04d}",
        status=Sale.Status.COMPLETED,
        completed_at=timezone.now(),
    )
    SaleItem.objects.create(sale=sale, product=product, quantity=qty, unit_price=Decimal(price))
    return sale


def test_a_claim_is_built_from_the_sale_split(org, member, cbhi, product):
    cover(cbhi, product)
    sale = _insured_sale(org, product)
    outcome = claim_service.build_from_sale(sale=sale, policy=member)

    assert outcome.claim.claim_number.startswith("CLM-")
    assert outcome.claimed == Decimal("9000.00")
    assert outcome.claim.lines.count() == 1


def test_a_sale_cannot_be_claimed_twice(org, member, cbhi, product):
    """Duplicates are the most common rejection; the cheapest fix is not sending one."""
    cover(cbhi, product)
    sale = _insured_sale(org, product)
    claim_service.build_from_sale(sale=sale, policy=member)

    with pytest.raises(claim_service.ClaimError, match="already on claim"):
        claim_service.build_from_sale(sale=sale, policy=member)


def test_a_claim_past_its_window_is_refused(org, member, cbhi, product):
    cover(cbhi, product)
    sale = _insured_sale(org, product)
    outcome = claim_service.build_from_sale(sale=sale, policy=member)
    claim = outcome.claim
    claim.service_date = today() - timedelta(days=45)  # window is 30 days
    claim.save()

    with pytest.raises(claim_service.ClaimError, match="claim window"):
        claim_service.submit(claim=claim)


def test_a_claim_with_nothing_covered_cannot_be_submitted(org, member, product):
    """Not on the formulary: the patient already paid it all, there is nothing to claim."""
    sale = _insured_sale(org, product)
    outcome = claim_service.build_from_sale(sale=sale, policy=member)
    with pytest.raises(claim_service.ClaimError, match="nothing to claim"):
        claim_service.submit(claim=outcome.claim)


def test_a_rejection_must_carry_a_reason_code(org, member, cbhi, product):
    cover(cbhi, product)
    claim = claim_service.build_from_sale(sale=_insured_sale(org, product), policy=member).claim
    claim_service.submit(claim=claim)

    with pytest.raises(claim_service.ClaimError, match="reason code"):
        claim_service.adjudicate(claim=claim, accepted=False, reason="")


def test_an_insurer_cannot_settle_more_than_was_claimed(org, member, cbhi, product):
    cover(cbhi, product)
    claim = claim_service.build_from_sale(sale=_insured_sale(org, product), policy=member).claim
    claim_service.submit(claim=claim)

    with pytest.raises(claim_service.ClaimError, match="overpayment"):
        claim_service.adjudicate(
            claim=claim, accepted=True, paid_amount=claim.claimed_amount + Decimal("1")
        )


def test_a_short_payment_leaves_the_claim_part_paid(org, member, cbhi, product):
    cover(cbhi, product)
    claim = claim_service.build_from_sale(sale=_insured_sale(org, product), policy=member).claim
    claim_service.submit(claim=claim)
    claim_service.adjudicate(claim=claim, accepted=True, paid_amount=Decimal("7000"))

    claim.refresh_from_db()
    assert claim.status == Claim.Status.PART_PAID
    assert claim.outstanding == Decimal("2000.00")


def test_a_reversed_claim_is_kept_not_deleted(org, member, cbhi, product):
    """A vanished claim leaves the insurer's records and ours disagreeing."""
    cover(cbhi, product)
    claim = claim_service.build_from_sale(sale=_insured_sale(org, product), policy=member).claim
    claim_service.submit(claim=claim)
    claim_service.reverse(claim=claim, reason="Script never collected")

    claim.refresh_from_db()
    assert claim.status == Claim.Status.REVERSED
    assert claim.outstanding == Decimal("0.00")
    assert Claim.objects.filter(pk=claim.pk).exists()


def test_a_settled_claim_cannot_be_reversed(org, member, cbhi, product):
    cover(cbhi, product)
    claim = claim_service.build_from_sale(sale=_insured_sale(org, product), policy=member).claim
    claim_service.submit(claim=claim)
    claim_service.adjudicate(claim=claim, accepted=True)

    with pytest.raises(claim_service.ClaimError, match="credit note"):
        claim_service.reverse(claim=claim, reason="too late")


def test_the_work_queue_ranks_by_how_close_the_window_is(org, member, cbhi, product):
    cover(cbhi, product)
    urgent = claim_service.build_from_sale(sale=_insured_sale(org, product), policy=member).claim
    urgent.service_date = today() - timedelta(days=28)
    urgent.save()
    relaxed = claim_service.build_from_sale(sale=_insured_sale(org, product), policy=member).claim

    rows = claim_service.work_queue(organization=org)
    assert rows[0]["claim"] == urgent.pk
    assert rows[0]["days_left"] < rows[-1]["days_left"]
    assert relaxed.pk in {r["claim"] for r in rows}


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------


def test_a_remittance_that_does_not_foot_is_refused(org, member, cbhi, product):
    """If the insurer's total disagrees with its own lines, posting buries it."""
    cover(cbhi, product)
    claim = claim_service.build_from_sale(sale=_insured_sale(org, product), policy=member).claim
    claim_service.submit(claim=claim)

    advice = RemittanceAdvice.objects.create(
        organization=org,
        scheme=cbhi,
        reference="RA-1",
        advice_date=today(),
        total_advised=Decimal("9000"),
    )
    recon.add_line(advice=advice, claim=claim, amount_paid=Decimal("7000"))

    with pytest.raises(recon.ReconciliationError, match="has to be explained"):
        recon.post(advice=advice)


def test_posting_a_remittance_settles_its_claims(org, member, cbhi, product):
    cover(cbhi, product)
    claim = claim_service.build_from_sale(sale=_insured_sale(org, product), policy=member).claim
    claim_service.submit(claim=claim)

    advice = RemittanceAdvice.objects.create(
        organization=org,
        scheme=cbhi,
        reference="RA-2",
        advice_date=today(),
        total_advised=Decimal("7000"),
    )
    recon.add_line(
        advice=advice, claim=claim, amount_paid=Decimal("7000"), denial_reason="Tariff capped"
    )
    outcome = recon.post(advice=advice)

    claim.refresh_from_db()
    assert outcome.claims_settled == 1
    assert outcome.short_paid == Decimal("2000.00")
    assert claim.status == Claim.Status.PART_PAID
    assert claim.paid_amount == Decimal("7000.00")


def test_a_claim_from_another_scheme_cannot_be_matched(org, member, cbhi, product):
    cover(cbhi, product)
    claim = claim_service.build_from_sale(sale=_insured_sale(org, product), policy=member).claim
    claim_service.submit(claim=claim)

    other = InsuranceScheme.objects.create(organization=org, code="MMI", name="Military")
    advice = RemittanceAdvice.objects.create(
        organization=org, scheme=other, reference="RA-3", advice_date=today()
    )
    with pytest.raises(recon.ReconciliationError, match="is against"):
        recon.add_line(advice=advice, claim=claim, amount_paid=Decimal("100"))
