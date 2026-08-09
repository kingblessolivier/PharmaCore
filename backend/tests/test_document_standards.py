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

    def test_it_names_itself_an_invoice_and_a_tax_invoice(
        self, issuer: Organization, customer: Organization
    ) -> None:
        """Both, and for different readers.

        The heading is INVOICE, as the supplied layout has it. The statutory
        designation still has to appear somewhere, because a buyer's auditor
        looks for the words "tax invoice" before allowing an input-VAT claim.
        """
        html = self._render(issuer, customer)
        assert "INVOICE" in html
        assert "tax invoice for VAT purposes" in html

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
        assert "Sub total" in html
        assert "5,000,000.00" in html
        assert "VAT 18%" in html
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


class TestDocumentsAreBlackOnWhite:
    """No colour anywhere.

    A document has to survive a cheap laser printer, a fax, a photocopy and a
    scan back into a compliance file, and every one of those turns a colour
    into an unreadable grey. Structure is carried by rules and weight instead,
    which is how printed commercial forms have always done it — and it is why
    a warning here is bold and underlined rather than red.
    """

    def test_the_shared_stylesheet_uses_only_black(self) -> None:
        css = (TEMPLATE_DIR / "base.html").read_text(encoding="utf-8")
        css = css[css.index("<style>") : css.index("</style>")]
        colours = {c.lower() for c in re.findall(r"#[0-9a-fA-F]{3,6}", css)}
        assert colours <= {
            "#000",
            "#000000",
            "#fff",
            "#ffffff",
        }, f"colour would not survive a photocopier: {sorted(colours)}"

    @pytest.mark.parametrize(
        "template",
        sorted(p.name for p in TEMPLATE_DIR.glob("*.html") if p.name != "base.html"),
    )
    def test_no_document_introduces_a_colour(self, template: str) -> None:
        markup = (TEMPLATE_DIR / template).read_text(encoding="utf-8")
        colours = {c.lower() for c in re.findall(r"#[0-9a-fA-F]{3,6}", markup)}
        assert colours <= {
            "#000",
            "#000000",
            "#fff",
            "#ffffff",
        }, f"{template} introduces {sorted(colours)}"


class TestThePurchaseOrderMatchesTheForm:
    def _render(self, issuer: Organization) -> str:
        return render_to_string(
            "documents/purchase_order.html",
            {
                "organization": issuer,
                "doc_number": "PO-2026-00042",
                "doc_type_label": "Purchase Order",
                "generated_at": timezone.now(),
                "po_number": "PO-2026-00042",
                "order_date": date(2026, 8, 9),
                "seller_name": "Ecomed Ltd",
                "seller_contact": "Jean Bosco",
                "seller_phone": "0788111222",
                "seller_tin": "109876543",
                "buyer_name": issuer.name,
                "buyer_contact": "A. Uwase",
                "deliver_to_address": "Main store, Gatsibo",
                "requisition_number": "REQ-2026-00125",
                "ship_via": "Volcano bus",
                "incoterm": "DAP",
                "payment_terms_days": 30,
                "subtotal": "2,250,000.00",
                "tax_total": "405,000.00",
                "freight_amount": "0.00",
                "other_charges": "0.00",
                "discount_amount": "0.00",
                "total": "2,655,000.00",
                "currency": "RWF",
                "notes": "Deliver before noon.",
                "lines": [
                    {
                        "item_number": "AMOX-500",
                        "name": "Amoxicillin 500mg",
                        "qty": "15",
                        "unit_label": "Carton of 24 boxes",
                        "base_quantity": "36,000",
                        "base_unit": "tablets",
                        "price": "150,000.00",
                        "total": "2,250,000.00",
                    }
                ],
            },
        )

    @pytest.mark.parametrize(
        "element",
        [
            "PURCHASE ORDER",
            "PO-2026-00042",
            "Vendor",
            "Ship to",
            "Requisition #",
            "Ship via",
            "F.O.B.",
            "Shipping terms",
            "Item #",
            "AMOX-500",
            "Carton of 24 boxes",
            "Comments or special instructions",
            "Subtotal",
            "Shipping",
            "Other",
            "Total (RWF)",
            "please contact",
        ],
    )
    def test_the_form_carries_every_block(self, issuer: Organization, element: str) -> None:
        assert element in self._render(issuer)

    def test_ship_via_is_not_the_incoterm(self, issuer: Organization) -> None:
        """Two different facts that were one field.

        The incoterm says who bears the risk and where it passes. A supplier
        reading "DAP" still does not know whether to book a courier, put it on
        a bus, or wait for our own truck — which is the one instruction about
        carriage a purchase order has to give.
        """
        html = self._render(issuer)
        assert "DAP" in html
        assert "Volcano bus" in html

    def test_the_grid_continues_past_the_last_item(self, issuer: Organization) -> None:
        # A printed order form rules its lines to the bottom so the totals sit
        # in the same place on every copy, and so there is no blank gap under
        # the last line for somebody to add one.
        html = self._render(issuer)
        assert html.count('class="blank"') > 0

    def test_a_full_order_draws_no_filler(self, issuer: Organization) -> None:
        from django.template import Context, Template

        rendered = Template(
            "{% load documents %}{% for _ in lines|blank_rows:12 %}.{% endfor %}"
        ).render(Context({"lines": list(range(12))}))
        assert rendered == ""


class TestTotalsBlocksUseTheFullPageWidth:
    """A layout test, because a text test passed while the page was broken.

    The totals block was rendering every figure — the text was in the PDF —
    but squeezed into a strip down the left of the page with the money column
    clipped to nothing. Asserting the figures are *present* said it was fine.
    Only their position tells the truth.

    The cause was `rowspan`: this renderer emits the text of a spanned cell but
    cannot compute the column widths around it.
    """

    @staticmethod
    def _positions(template: str, context: dict, tokens: set[str]) -> tuple[dict, float]:
        import io

        from pypdf import PdfReader

        page = PdfReader(io.BytesIO(render_pdf(render_to_string(template, context)))).pages[0]
        hits: dict[str, float] = {}

        def visit(text, cm, tm, font, size):  # noqa: ANN001, ANN202
            stripped = text.strip()
            if stripped in tokens:
                hits.setdefault(stripped, cm[4] + tm[4])

        page.extract_text(visitor_text=visit)
        return hits, float(page.mediabox.width)

    def test_no_template_uses_rowspan(self) -> None:
        offenders = [
            path.name
            for path in TEMPLATE_DIR.glob("*.html")
            if re.search(r"<t[dh][^>]*\browspan\s*=", path.read_text(encoding="utf-8"))
        ]
        assert offenders == [], (
            "rowspan collapses the column widths in xhtml2pdf — continue a cell "
            f"with suppressed borders instead. Found in: {offenders}"
        )

    def test_the_purchase_order_totals_reach_the_right_margin(self, issuer: Organization) -> None:
        tokens = {"Deliver before noon.", "Subtotal", "45,000.00", "58,100.00"}
        hits, width = self._positions(
            "documents/purchase_order.html",
            {
                "organization": issuer,
                "doc_number": "PO-1",
                "doc_type_label": "Purchase Order",
                "generated_at": timezone.now(),
                "po_number": "PO-1",
                "order_date": date(2026, 8, 9),
                "seller_name": "Ecomed Ltd",
                "buyer_name": issuer.name,
                "subtotal": "45,000.00",
                "tax_total": "8,100.00",
                "freight_amount": "5,000.00",
                "other_charges": "0.00",
                "discount_amount": "0.00",
                "total": "58,100.00",
                "currency": "RWF",
                "notes": "Deliver before noon.",
                "lines": [],
            },
            tokens,
        )
        missing = tokens - set(hits)
        assert not missing, f"figures never reached the page: {sorted(missing)}"
        assert hits["Deliver before noon."] < width * 0.2, "comments belong on the left"
        assert (
            hits["58,100.00"] > width * 0.65
        ), "the money column collapsed to the left — the table is not using the page"

    def test_the_invoice_totals_reach_the_right_margin(self, issuer: Organization) -> None:
        tokens = {"Sub total", "2,227.00", "Balance due"}
        hits, width = self._positions(
            "documents/tax_invoice.html",
            {
                "organization": issuer,
                "doc_number": "INV-1",
                "doc_type_label": "Invoice",
                "generated_at": timezone.now(),
                "invoice_number": "INV-1",
                "buyer_name": "A Customer",
                "subtotal": "2,227.00",
                "tax_total": "111.35",
                "total": "2,338.35",
                "vat_bands": [],
                "currency": "RWF",
                "lines": [],
            },
            tokens,
        )
        missing = tokens - set(hits)
        assert not missing, f"figures never reached the page: {sorted(missing)}"
        assert hits["2,227.00"] > width * 0.65

    def test_a_caller_omitting_figures_cannot_collapse_the_column(
        self, issuer: Organization
    ) -> None:
        """The B2B order's context, which is thinner than procurement's.

        Both use this template. One passed `total` alone, so Subtotal, Tax,
        Shipping and Other rendered empty — and an empty cell lets the renderer
        size the column from nothing and squeeze it to a sliver. Each figure
        now falls back to a dash, which holds the column open.
        """
        tokens = {"dmkn", "Subtotal", "7,500.00"}
        hits, width = self._positions(
            "documents/purchase_order.html",
            {
                "organization": issuer,
                "doc_number": "PO-1",
                "doc_type_label": "Purchase Order",
                "generated_at": timezone.now(),
                "po_number": "PO-00014",
                "buyer_name": issuer.name,
                "seller_name": "A Depot",
                "notes": "dmkn",
                "total": "7,500.00",
                "currency": "RWF",
                "lines": [],
            },
            tokens,
        )
        assert not tokens - set(hits), f"missing: {sorted(tokens - set(hits))}"
        assert hits["dmkn"] < width * 0.2
        assert hits["7,500.00"] > width * 0.65
