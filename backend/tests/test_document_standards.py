"""What a generated document must and must not contain.

Two classes of failure are covered, and the first one shipped:

* **Developer commentary printed on the document.** Django's ``{# … #}`` is a
  single-line comment. A multi-line one is not a comment at all — it is
  literal text — so six explanatory notes were being printed at the top of
  every document this system issued, above the pharmacy's own name.

* **A tax invoice that is not a tax invoice.** The statutory minimum is short
  and was half met: no customer TIN (so a VAT-registered buyer could not
  reclaim), no units, and a single "Total" where the law requires the taxable
  amount and the VAT stated separately, broken down by rate.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from apps.documents import invoicing
from apps.documents.renderer import render_pdf
from apps.iam.models import Organization
from django.template.loader import render_to_string
from django.utils import timezone

pytestmark = pytest.mark.django_db

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "apps/documents/templates/documents"


@pytest.fixture
def issuer() -> Organization:
    return Organization.objects.create(
        name="Fadhil Pharmacy",
        type="RETAIL",
        tin="12894798",
        rwanda_fda_license_no="1298",
        district="Gatsibo",
        phone="0786856578",
        email="pharmacy@example.rw",
    )


class TestCommentsNeverReachThePage:
    def test_no_template_uses_a_multiline_hash_comment(self) -> None:
        """The bug, pinned at its source.

        ``{# … #}`` spanning lines is not a comment. Anyone writing one is
        writing body text, and it will be printed on documents sent to
        suppliers and the tax authority.
        """
        offenders = {
            path.name: len(bad)
            for path in TEMPLATE_DIR.glob("*.html")
            if (
                bad := [
                    match
                    for match in re.findall(r"\{#.*?#\}", path.read_text(encoding="utf-8"), re.S)
                    if "\n" in match
                ]
            )
        }
        assert offenders == {}, (
            "Multi-line {# #} renders as visible text. Use {% comment %}. " f"Found: {offenders}"
        )

    @pytest.mark.parametrize(
        "template",
        sorted(p.name for p in TEMPLATE_DIR.glob("*.html") if p.name != "base.html"),
    )
    def test_every_document_renders_without_template_syntax(
        self, template: str, issuer: Organization
    ) -> None:
        html = render_to_string(
            f"documents/{template}",
            {
                "organization": issuer,
                "doc_number": "SPEC-1",
                "doc_type_label": "Specimen",
                "generated_at": timezone.now(),
                "lines": [],
                "subtotal": "0.00",
                "tax_total": "0.00",
                "total": "0.00",
            },
        )
        assert "{#" not in html
        assert "{%" not in html
        assert render_pdf(html), f"{template} produced no page"


class TestAmountsInWords:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (0, "Zero francs only"),
            (1, "One francs only"),
            (15, "Fifteen francs only"),
            (42, "Forty-two francs only"),
            (100, "One hundred francs only"),
            (118, "One hundred and eighteen francs only"),
            (1_500, "One thousand five hundred francs only"),
            (6_200_000, "Six million two hundred thousand francs only"),
        ],
    )
    def test_it_spells_the_amount(self, value: int, expected: str) -> None:
        # The convention exists to make tampering obvious: altering a digit is
        # easy, altering a digit and the words is not.
        assert invoicing.in_words(value) == expected

    def test_cents_are_spelled_too(self) -> None:
        assert "fifty cents" in invoicing.in_words(Decimal("10.50"))

    def test_a_credit_says_so(self) -> None:
        assert invoicing.in_words(Decimal("-100")).startswith("Minus")


class TestVatIsBrokenDownByRate:
    def test_two_rates_are_never_summed_into_one(self) -> None:
        """The requirement the old single "Total" line broke.

        A buyer reclaims against the standard-rated portion only, so an
        invoice mixing an 18% line and an exempt line into one VAT figure
        tells them nothing they can act on.
        """
        bands = invoicing.vat_bands(
            [
                {"tax_class": "B", "net": Decimal("5000000"), "tax_amount": Decimal("900000")},
                {"tax_class": "A", "net": Decimal("300000"), "tax_amount": Decimal("0")},
            ]
        )
        assert bands == [
            {"rate": "18%", "taxable": "5,000,000.00", "amount": "900,000.00"},
            {"rate": "0%", "taxable": "300,000.00", "amount": "0.00"},
        ]

    def test_lines_at_the_same_rate_are_added_together(self) -> None:
        bands = invoicing.vat_bands(
            [
                {"tax_class": "B", "net": Decimal("100"), "tax_amount": Decimal("18")},
                {"tax_class": "B", "net": Decimal("200"), "tax_amount": Decimal("36")},
            ]
        )
        assert len(bands) == 1
        assert bands[0] == {"rate": "18%", "taxable": "300.00", "amount": "54.00"}

    def test_the_rate_is_derived_when_only_a_tax_class_is_given(self) -> None:
        bands = invoicing.vat_bands([{"tax_class": "B", "net": Decimal("1000")}])
        assert bands[0]["rate"] == "18%"
        assert bands[0]["amount"] == "180.00"


class TestTheTaxInvoiceCarriesWhatTheLawWants:
    def _render(self, issuer: Organization, buyer: Organization) -> str:
        context = invoicing.invoice_context(
            seller=issuer,
            buyer=buyer,
            lines=[
                {
                    "name": "Paracetamol 500mg",
                    "tax_class": "B",
                    "net": Decimal("5000000"),
                    "tax_amount": Decimal("900000"),
                    "qty": "2",
                    "unit_label": "Carton of 24 boxes",
                    "base_quantity": "4,800",
                    "base_unit": "tablets",
                    "price": "2,500,000.00",
                    "total": "5,000,000.00",
                }
            ],
            subtotal=Decimal("5000000"),
            tax_total=Decimal("900000"),
            total=Decimal("5900000"),
            invoice_number="INV-2026-00042",
            invoice_date=date(2026, 8, 9),
            due_date=date(2026, 9, 8),
        )
        context.update(
            organization=issuer,
            doc_number="INV-2026-00042",
            doc_type_label="Tax Invoice",
            generated_at=timezone.now(),
        )
        return render_to_string("documents/tax_invoice.html", context)

    @pytest.fixture
    def customer(self) -> Organization:
        return Organization.objects.create(
            name="Kigali Central Pharmacy", type="RETAIL", tin="99887766", district="Nyarugenge"
        )

    def test_it_names_itself_a_tax_invoice(
        self, issuer: Organization, customer: Organization
    ) -> None:
        assert "TAX INVOICE" in self._render(issuer, customer)

    def test_both_parties_carry_a_tin(self, issuer: Organization, customer: Organization) -> None:
        # Without the customer's TIN a VAT-registered buyer cannot reclaim the
        # input VAT, which makes the document worthless to them.
        html = self._render(issuer, customer)
        assert "12894798" in html, "supplier TIN"
        assert "99887766" in html, "customer TIN"

    def test_a_missing_customer_tin_is_flagged_not_left_blank(self, issuer: Organization) -> None:
        anonymous = Organization.objects.create(name="Walk-in Buyer", type="RETAIL")
        assert "TIN not on record" in self._render(issuer, anonymous)

    def test_the_unit_travels_with_the_quantity(
        self, issuer: Organization, customer: Organization
    ) -> None:
        html = self._render(issuer, customer)
        assert "Carton of 24 boxes" in html
        assert "4,800 tablets in total" in html

    def test_taxable_and_vat_are_stated_separately(
        self, issuer: Organization, customer: Organization
    ) -> None:
        html = self._render(issuer, customer)
        assert "Total excluding VAT" in html
        assert "5,000,000.00" in html
        assert "VAT at 18%" in html
        assert "900,000.00" in html
        assert "5,900,000.00" in html

    def test_it_states_when_payment_is_due(
        self, issuer: Organization, customer: Organization
    ) -> None:
        assert "08 Sep 2026" in self._render(issuer, customer)

    def test_it_spells_the_total_out(self, issuer: Organization, customer: Organization) -> None:
        assert "Five million nine hundred thousand francs only" in self._render(issuer, customer)

    def test_the_pharmacy_heads_it_not_the_software(
        self, issuer: Organization, customer: Organization
    ) -> None:
        html = self._render(issuer, customer)
        assert html.index("Fadhil Pharmacy") < html.index("PharmaCore by Medlink")


class TestHandoverDocumentsCanBeSigned:
    """A goods receipt nobody signed is a list, not evidence.

    The receipt and the delivery note are two halves of one act: custody
    passing from a driver to a storekeeper. Both carried the lines and neither
    carried the handover — no supplier, no order reference, no remarks, and
    nowhere for the two people present to put their names.
    """

    def _grn(self, issuer: Organization) -> str:
        return render_to_string(
            "documents/grn.html",
            {
                "organization": issuer,
                "doc_number": "GRN-2026-00007",
                "grn_number": "GRN-2026-00007",
                "doc_type_label": "Goods Receipt Note",
                "generated_at": timezone.now(),
                "supplier_name": "Kigali Central Depot",
                "supplier_phone": "0788123456",
                "order_number": "PO-00042",
                "received_at": date(2026, 8, 9),
                "has_discrepancy": True,
                "delivered_by_name": "J. Habimana",
                "received_by_name": "A. Uwase",
                "remarks": "Two cartons showed crushed corners.",
                "show_values": True,
                "total": "1,530,000.00",
                "lines": [
                    {
                        "name": "Amoxicillin 500mg",
                        "batch": "LOT-991",
                        "expiry": date(2027, 6, 1),
                        "unit_label": "Carton of 24 boxes",
                        "base_quantity": "4,800",
                        "base_unit": "tablets",
                        "expected": 12,
                        "received": 10,
                        "damaged": 1,
                        "value": "1,200,000.00",
                    }
                ],
            },
        )

    def test_it_names_itself_and_says_what_it_is_for(self, issuer: Organization) -> None:
        html = self._grn(issuer)
        assert "GOODS RECEIPT NOTE" in html
        assert "when goods are received" in html

    def test_it_records_who_it_came_from_and_against_what(self, issuer: Organization) -> None:
        html = self._grn(issuer)
        assert "Kigali Central Depot" in html
        assert "0788123456" in html
        assert "PO-00042" in html

    def test_both_parties_have_somewhere_to_sign(self, issuer: Organization) -> None:
        html = self._grn(issuer)
        assert "Delivered by" in html
        assert "Received by" in html
        assert "Name in print" in html
        assert "Signature" in html
        assert "J. Habimana" in html
        assert "A. Uwase" in html

    def test_a_short_delivery_is_marked_not_left_to_be_compared(self, issuer: Organization) -> None:
        # Twelve expected, ten received. The reason the document exists is to
        # surface that, not to print two columns and hope somebody subtracts.
        html = self._grn(issuer)
        row = re.search(r"<tr[^>]*>(?:(?!</tr>).)*Amoxicillin.*?</tr>", html, re.S)
        assert row is not None
        assert "warn" in row.group(0), "the short quantity must be flagged on the line"
        assert "DISCREPANCIES: YES" in html

    def test_batch_and_expiry_are_on_every_line(self, issuer: Organization) -> None:
        # Traceability to the lot is the whole basis of a recall; a medicines
        # receipt without it cannot support one.
        html = self._grn(issuer)
        assert "LOT-991" in html
        assert "06/2027" in html

    def test_the_unit_travels_with_the_quantity(self, issuer: Organization) -> None:
        html = self._grn(issuer)
        assert "Carton of 24 boxes" in html
        assert "4,800 tablets in total" in html

    def test_there_is_room_for_remarks(self, issuer: Organization) -> None:
        assert "crushed corners" in self._grn(issuer)

    def test_the_delivery_note_can_also_be_signed(self, issuer: Organization) -> None:
        # The other half of the same handover: the driver carries it, the
        # storekeeper signs it, and the signed copy is the proof of delivery.
        html = render_to_string(
            "documents/delivery_note.html",
            {
                "organization": issuer,
                "doc_number": "DN-1",
                "doc_type_label": "Delivery Note",
                "generated_at": timezone.now(),
                "from_name": "Kigali Central Depot",
                "to_name": "Fadhil Pharmacy",
                "driver": "J. Habimana",
                "vehicle": "RAD 123 X",
                "cold_chain": True,
                "lines": [],
            },
        )
        assert "DELIVERY NOTE" in html
        assert "Name in print" in html
        assert "Received by" in html
        assert "COLD CHAIN CONSIGNMENT" in html


class TestEveryPageIsIdentifiable:
    def test_the_footer_repeats_with_a_page_count(self, issuer: Organization) -> None:
        """A reader must be able to see that page 4 of 10 is missing.

        Rendered as a repeating frame rather than once at the end, so a
        document that runs to several sheets is still a record when the sheets
        are separated.
        """
        html = render_to_string(
            "documents/grn.html",
            {
                "organization": issuer,
                "doc_number": "GRN-1",
                "doc_type_label": "Goods Receipt Note",
                "generated_at": timezone.now(),
                "lines": [{"name": f"Item {i}", "expected": 1, "received": 1} for i in range(90)],
            },
        )
        assert "pdf:pagenumber" in html
        assert "pdf:pagecount" in html
        assert "Fadhil Pharmacy" in html
        pdf = render_pdf(html)
        assert pdf.decode("latin-1", "ignore").count("/Type /Page") > 1, "should span pages"
