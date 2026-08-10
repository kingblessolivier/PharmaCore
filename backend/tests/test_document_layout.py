"""Do the columns of a generated document actually fit?

Every existing document test asserts that text is *present* in the PDF. All of
them passed on a journal voucher whose Debit and Credit columns were ten points
apart, printing "7,5060.00" where two figures overlapped — and on a goods
receipt whose "Delivered by" and "Received by" headings were stamped on top of
each other. Presence is not layout. A document can contain every required word
and still be unreadable, and unreadable is the same as wrong on a form somebody
signs.

The cause is one behaviour of this renderer:

    **xhtml2pdf collapses a column containing an empty cell to zero width**, and
    drags the neighbouring columns in with it.

A ledger produces empty cells by nature — a debit line has no credit, a credit
line has no debit — so on a journal voucher this is not an edge case, it is the
normal shape of the data. The same collapse merged "Delivered by" and "Received
by" on every goods receipt where the driver's name had not been typed in.

I first blamed declared column widths summing to 100%. That is a real constraint
of this renderer and it is worth staying inside — a table's declared widths plus
its cell padding cannot exceed the frame, which is what the static check at the
bottom of this file enforces — but it was **not** the cause here. A seven-column
table declaring 100% renders correctly. The same table with one empty cell in a
middle column does not. `TestEmptyCellsAreFilled` holds that measurement.

The fix lives in `renderer.fill_empty_cells`, so no template has to know.

The rest of this file measures. It reads back the position and font of every
text run in the rendered PDF, computes each string's real width from the font
metrics reportlab shipped it with, and fails when two runs on one line overlap
or when anything crosses the right margin.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

import pytest
from apps.documents.renderer import render_pdf
from django.template.loader import render_to_string
from pypdf import PdfReader
from reportlab.pdfbase.pdfmetrics import stringWidth  # type: ignore[import-untyped]

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "apps/documents/templates/documents"

#: A4 portrait, less the 1.3cm margins base.html sets.
PAGE_WIDTH = 595.3
MARGIN = 36.9
RIGHT_EDGE = PAGE_WIDTH - MARGIN


class Run:
    """One positioned string, with the width it really occupies."""

    def __init__(self, x: float, y: float, text: str, font: str, size: float) -> None:
        self.x, self.y, self.text = x, y, text
        try:
            self.width = stringWidth(text, font, size)
        except Exception:
            # An embedded subset name reportlab cannot resolve. Helvetica is the
            # family every document template uses, so it is the right fallback
            # and errs narrow rather than raising.
            self.width = stringWidth(text, "Helvetica", size)

    @property
    def right(self) -> float:
        return self.x + self.width

    def __repr__(self) -> str:
        return f"{self.text!r}@{self.x:.1f}..{self.right:.1f}"


def runs_on(pdf_bytes: bytes, page: int = 0) -> list[Run]:
    """Every text run on a page, positioned in page coordinates.

    The visitor's `tm` alone is relative to the graphics state this renderer
    resets per block — read on its own it reports every run at x=0, which is
    how a first attempt at this test concluded the layout was perfect.
    """
    import io

    found: list[Run] = []

    def visit(text: str, cm: Any, tm: Any, font: str, size: float) -> None:
        stripped = text.strip()
        if not stripped:
            return
        x = cm[0] * tm[4] + cm[2] * tm[5] + cm[4]
        y = cm[1] * tm[4] + cm[3] * tm[5] + cm[5]
        found.append(Run(x, y, stripped, font, size))

    PdfReader(io.BytesIO(pdf_bytes)).pages[page].extract_text(visitor_text=visit)
    return found


def overlaps(runs: list[Run], tolerance: float = 0.5) -> list[str]:
    """Pairs of runs sharing a line whose boxes intersect.

    Lines are grouped to the nearest point: the renderer places a row's cells at
    the same baseline, and floating-point drift between them is well under 1pt.
    """
    lines: dict[int, list[Run]] = {}
    for run in runs:
        lines.setdefault(round(run.y), []).append(run)

    problems = []
    for y, line in sorted(lines.items()):
        ordered = sorted(line, key=lambda r: r.x)
        for left, right in zip(ordered, ordered[1:], strict=False):
            # Runs starting at the identical x are one paragraph's consecutive
            # pieces — "Issued by", the pharmacy's name, ", TIN …" — which the
            # renderer emits as separate strings sharing the block's origin and
            # advancing internally. They are not two columns, and reading them
            # as such made this test report the footer of every document as
            # broken while the columns it was written for passed.
            if abs(left.x - right.x) < 0.1:
                continue
            if left.right - right.x > tolerance:
                problems.append(
                    f"y={y}: {left!r} runs into {right!r} (overlap {left.right - right.x:.1f}pt)"
                )
    return problems


def past_margin(runs: list[Run]) -> list[str]:
    return [
        f"{r!r} ends {r.right - RIGHT_EDGE:.1f}pt past the right margin"
        for r in runs
        if r.right > RIGHT_EDGE + 0.5
    ]


def render(template: str, context: dict[str, Any]) -> bytes:
    return render_pdf(render_to_string(f"documents/{template}", context))


# --------------------------------------------------------------------------- #
# The measurement itself, proven before it is trusted
# --------------------------------------------------------------------------- #


class TestEmptyCellsAreFilled:
    """The actual cause, pinned where it was found.

    xhtml2pdf collapses a column holding an empty cell to zero width and drags
    its neighbours in. A ledger produces empty cells by nature — a debit line
    has no credit — so this is the normal shape of the data, not an edge case.
    """

    def test_an_empty_cell_is_given_something_to_hold(self) -> None:
        from apps.documents.renderer import fill_empty_cells

        assert fill_empty_cells("<td></td>") == "<td>&nbsp;</td>"
        assert fill_empty_cells('<td class="right"></td>') == '<td class="right">&nbsp;</td>'
        assert fill_empty_cells("<td>\n   </td>") == "<td>&nbsp;</td>"
        assert fill_empty_cells("<th></th>") == "<th>&nbsp;</th>"

    def test_a_cell_with_content_is_left_alone(self) -> None:
        from apps.documents.renderer import fill_empty_cells

        assert fill_empty_cells("<td>7,500.00</td>") == "<td>7,500.00</td>"
        assert fill_empty_cells("<td>&nbsp;</td>") == "<td>&nbsp;</td>"
        assert fill_empty_cells("<td><b>x</b></td>") == "<td><b>x</b></td>"
        # Not a table cell. `<template>` is the trap a lazy `<t.>` pattern hits.
        assert fill_empty_cells("<title></title>") == "<title></title>"

    def test_one_empty_cell_really_does_wreck_the_table(self) -> None:
        """The measurement that overturned my first diagnosis.

        I had blamed declared widths summing to 100%. A seven-column table at
        100% renders correctly; the same table with a single empty cell in a
        middle column does not. This is the difference, measured.
        """
        style = (
            "<style>table{width:100%;border-collapse:collapse}"
            "th,td{border:0.5pt solid #000;padding:4pt 5pt;font-size:8.5pt}</style>"
        )
        head = (
            '<tr><th style="width:4%">#</th><th style="width:9%">AC</th>'
            '<th style="width:22%">Account</th><th style="width:9%">CC</th>'
            '<th style="width:13%">Memo</th><th style="width:14%">Debit</th>'
            '<th style="width:14%">Credit</th></tr>'
        )
        row = (
            "<tr><td>2</td><td>1100</td><td>Cash</td><td>KGL</td>"
            "<td>Paid</td>{cell}<td>1.00</td></tr>"
        )

        def gap(cell: str) -> float:
            body = (
                f"<html><head>{style}</head><body>"
                f"<table>{head}{row.format(cell=cell)}</table></body></html>"
            )
            found = sorted(
                (r for r in runs_on(render_pdf(body)) if r.text in ("Debit", "Credit")),
                key=lambda r: r.x,
            )
            return found[1].x - found[0].x

        # `render_pdf` fills the cell on the way in, so the broken case has to
        # be built by hand to be observed at all.
        assert gap("<td>&nbsp;</td>") > 60, "a filled cell must leave the columns their width"
        assert gap("<td></td>") > 60, "render_pdf should have filled this one itself"


class TestTheRulerWorks:
    """A layout test that cannot detect a collision is worse than none."""

    def test_it_finds_a_collision_that_is_there(self) -> None:
        a = Run(100.0, 500.0, "Debit", "Helvetica", 8)
        b = Run(110.0, 500.0, "Credit", "Helvetica", 8)
        assert a.width > 10, "Helvetica metrics did not load"
        assert overlaps([a, b]), "two strings 10pt apart must be reported as overlapping"

    def test_it_leaves_a_clean_line_alone(self) -> None:
        a = Run(100.0, 500.0, "Debit", "Helvetica", 8)
        b = Run(200.0, 500.0, "Credit", "Helvetica", 8)
        assert overlaps([a, b]) == []

    def test_runs_on_different_lines_never_collide(self) -> None:
        a = Run(100.0, 500.0, "Debit", "Helvetica", 8)
        b = Run(100.0, 480.0, "Credit", "Helvetica", 8)
        assert overlaps([a, b]) == []

    def test_it_finds_text_past_the_margin(self) -> None:
        assert past_margin([Run(RIGHT_EDGE - 2, 500.0, "7,500.00", "Helvetica", 9)])
        assert past_margin([Run(100.0, 500.0, "7,500.00", "Helvetica", 9)]) == []


# --------------------------------------------------------------------------- #
# The documents
# --------------------------------------------------------------------------- #

ISSUER = {
    "name": "Kigali Central Pharmacy",
    "tin": "400500600",
    "district": "Kicukiro",
    "phone": "0788000000",
    "email": "pharmacy@example.rw",
}

BASE = {"organization": ISSUER, "doc_number": "XX-2026-00001", "generated_at": date(2026, 8, 10)}

VOUCHER = {
    **BASE,
    "doc_type_label": "Journal voucher",
    "entry_number": "JE-1-000011",
    "entry_date": date(2026, 8, 7),
    "description": "Settlement paid for PO-00013",
    "source": "Treasury & banking",
    "origin": "stock_order · 13",
    "is_manual": False,
    "currency": "RWF",
    "line_count": 2,
    "balanced": True,
    "difference": "0.00",
    "total_debit": "1,234,567.00",
    "total_credit": "1,234,567.00",
    "total_words": "One million two hundred and thirty-four thousand five hundred and sixty-seven",
    "status": "Posted",
    "is_reversed": False,
    "reverses": "",
    "reversed_by": "",
    "posted_by": "Nsengimana Olivier",
    # A datetime, as `entry.created_at` is: the template prints the time it
    # was entered, and Django refuses a time specifier on a bare date.
    "posted_at": datetime(2026, 8, 7, 19, 36),
    "lines": [
        {
            "code": "2100",
            "name": "Accounts Payable — Trade",
            "cost_centre": "KGL-01",
            "memo": "Settlement",
            "debit": "1,234,567.00",
            "credit": "",
        },
        {
            "code": "1100",
            "name": "Cash on Hand",
            "cost_centre": "KGL-01",
            "memo": "Paid by transfer",
            "debit": "",
            "credit": "1,234,567.00",
        },
    ],
}

RECEIPT = {
    **BASE,
    "doc_type_label": "Goods receipt note",
    "grn_number": "GRN-00015",
    "received_at": date(2026, 8, 10),
    "supplier_name": "Kigali Central Depot",
    "supplier_address": "Nyarugenge",
    "supplier_tin": "100200300",
    "retail_name": "Kigali Central Pharmacy",
    "order_number": "PO-00007",
    "has_discrepancy": True,
    "show_values": True,
    "currency": "RWF",
    "total": "1,234,567.00",
    "received_by_name": "Nsengimana Olivier",
    "delivered_by_name": "Jean Habimana",
    "remarks": "Two cartons crushed in transit.",
    "lines": [
        {
            "name": "Amoxicillin 500mg capsules",
            "batch": "BN-2026-0041",
            "expiry": date(2027, 12, 31),
            "unit_label": "Carton of 100",
            "base_quantity": 12000,
            "base_unit": "capsules",
            "expected": 120,
            "received": 118,
            "damaged": 2,
            "value": "1,234,567.00",
        }
    ],
}

DOCUMENTS = [
    ("journal_voucher.html", VOUCHER),
    ("grn.html", RECEIPT),
]


@pytest.mark.parametrize("template,context", DOCUMENTS, ids=[d[0] for d in DOCUMENTS])
class TestColumnsFit:
    def test_nothing_overlaps_anything(self, template: str, context: dict[str, Any]) -> None:
        """The defect: two columns printed on top of each other.

        Wide values are used deliberately — "1,234,567.00" rather than "0.00".
        A money column crushed to ten points still looks fine holding a zero,
        which is why the development database, full of small numbers, hid this
        until a real figure was posted.
        """
        problems = overlaps(runs_on(render(template, context)))
        assert not problems, f"{template} prints text on top of other text:\n  " + "\n  ".join(
            problems
        )

    def test_nothing_runs_off_the_page(self, template: str, context: dict[str, Any]) -> None:
        problems = past_margin(runs_on(render(template, context)))
        assert not problems, f"{template} overflows the page:\n  " + "\n  ".join(problems)


class TestTheDeclaredWidthsLeaveRoomForPadding:
    """The same rule, checked statically, so it reads as a rule.

    The measurement above is the real test. This one names the cause, and
    catches a template whose table this suite does not yet render.
    """

    #: 5pt of padding on each side of a cell, as a share of the 521.5pt of page
    #: between base.html's margins.
    PADDING_SHARE = 10.0 / (PAGE_WIDTH - 2 * MARGIN) * 100

    #: Only the ruled tables pay for padding. `.parties` and `.head` set
    #: `padding: 0` (or a right-hand gutter only) and are free to declare a
    #: straight 50/50 — which most documents do, correctly.
    PADDED = ("lines", "sig")

    @classmethod
    def _sizing_rows(cls) -> list[tuple[str, int, float]]:
        """(template, column count, declared total) for each ruled table."""
        import re

        rows = []
        for path in sorted(TEMPLATE_DIR.glob("*.html")):
            source = path.read_text(encoding="utf-8")
            for table in re.finditer(
                r'<table[^>]*class="([^"]*)"[^>]*>(.*?)</table>', source, re.S
            ):
                if not any(name in table.group(1).split() for name in cls.PADDED):
                    continue
                for row in re.findall(r"<tr[^>]*>(.*?)</tr>", table.group(2), re.S):
                    widths = [float(w) for w in re.findall(r"width:\s*([\d.]+)%", row)]
                    if widths:
                        rows.append((path.name, len(re.findall(r"<t[hd]", row)), sum(widths)))
                        break  # the first row with widths sizes the table
        return rows

    def test_the_scan_finds_the_ruled_tables(self) -> None:
        rows = self._sizing_rows()
        assert len(rows) >= 5, f"only {len(rows)} sized table(s) found — the scan is broken"
        assert any(name == "journal_voucher.html" for name, _, _ in rows)

    def test_no_table_declares_more_width_than_exists(self) -> None:
        problems = [
            f"{name}: {columns} columns declaring {total:.0f}% need "
            f"{total + self.PADDING_SHARE * columns:.0f}% once padding is counted — "
            "the last columns will be crushed"
            for name, columns, total in self._sizing_rows()
            if total + self.PADDING_SHARE * columns > 100
        ]
        assert not problems, "\n  " + "\n  ".join(problems)

    def test_the_rule_is_the_one_that_was_broken(self) -> None:
        """Seven columns at 100% is the journal voucher as it shipped."""
        assert sum([4, 10, 31, 11, 18, 13, 13]) + self.PADDING_SHARE * 7 > 100
        # The purchase order, which rendered correctly, is inside the budget.
        assert sum([14, 8, 15, 14, 15]) + self.PADDING_SHARE * 6 < 100
