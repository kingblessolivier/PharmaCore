"""The journal voucher, and the two defects behind it.

**A posting that says a human typed it, when nothing did.** ``source_module``
exists for one reason, stated in the model itself: it is "the one field that
lets an accountant tell a system-generated entry from something a human typed at
midnight". ``post_journal`` defaults it to ``MANUAL``, and 23 of the 33 call
sites — payroll, goods receipts, supplier invoices, customer receipts, tax
payments, insurance settlements — never passed one. Every automatic posting in
the ledger was filed as a manual journal, which makes the field worse than
absent: it is confidently wrong, and the money-flow map and the "where did this
month's cost come from" report both read it.

**A voucher that was a table with a heading.** The document had no totals check,
no amount in words, no reversal state, no source reference and no signature
block worth the name — and it rendered ``str(Decimal)``, so it printed
"1500.00" where a voucher says "1,500.00".

The first test is a structural one over the source, in the manner of the
frontend token gate: the defect is a *missing argument*, which no runtime test
of any single posting would catch, because each posting works fine.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import pytest
from apps.finance.documents import journal_voucher_document
from apps.finance.models import Account, JournalEntry, JournalLine
from apps.finance.services import post_journal
from apps.iam.models import Organization
from pypdf import PdfReader

pytestmark = pytest.mark.django_db

APPS = Path(__file__).resolve().parent.parent / "apps"


@pytest.fixture
def org() -> Organization:
    return Organization.objects.create(
        name="Fadhil Pharmacy", type="RETAIL", tin="12894798", district="Gatsibo"
    )


@pytest.fixture
def accounts(org: Organization) -> tuple[Account, Account]:
    cash = Account.objects.create(
        organization=org, code="1100", name="Cash on Hand", account_type="ASSET"
    )
    payable = Account.objects.create(
        organization=org, code="2100", name="Accounts Payable — Trade", account_type="LIABILITY"
    )
    return cash, payable


def _entry(org: Organization, accounts: tuple[Account, Account], amount: str) -> JournalEntry:
    cash, payable = accounts
    return post_journal(
        organization=org,
        description="Settlement paid for PO-00013",
        lines=[
            {"account": payable, "side": JournalLine.Side.DEBIT, "amount": Decimal(amount)},
            {"account": cash, "side": JournalLine.Side.CREDIT, "amount": Decimal(amount)},
        ],
        reference_type="stock_order",
        reference_id="13",
        source_module=JournalEntry.Source.TREASURY,
    )


class TestEverySystemPostingSaysWhereItCameFrom:
    """The gate. It reads the call sites, because that is where the bug lives."""

    @staticmethod
    def _scan(source: str, label: str = "<snippet>") -> list[tuple[str, int, str]]:
        """Every ``post_journal(...)`` call in one source, with its argument text.

        A balanced-paren walk rather than a regex, because the argument lists
        hold nested calls and dict literals — matching to the first ``)`` reads
        a fraction of the call and reports arguments missing that are plainly
        there. Deliberately not anchored to a trailing newline: a one-line call
        must be seen too, or the gate quietly stops covering it. Calls without
        an ``organization=`` argument are prose, not code — the phrase appears
        in a docstring in ``finance/reports.py``.
        """
        found = []
        for match in re.finditer(r"(?<![\w.])(?<!def )post_journal\(", source):
            index, depth = match.end(), 1
            while depth and index < len(source):
                if source[index] == "(":
                    depth += 1
                elif source[index] == ")":
                    depth -= 1
                index += 1
            body = source[match.end() : index]
            if "organization=" in body:
                found.append((label, source[: match.start()].count("\n") + 1, body))
        return found

    @classmethod
    def _calls(cls) -> list[tuple[str, int, str]]:
        return [
            call
            for path in APPS.rglob("*.py")
            for call in cls._scan(path.read_text(encoding="utf-8"), str(path.relative_to(APPS)))
        ]

    def test_the_scan_reads_what_it_claims_to(self) -> None:
        """Prove the scanner works before trusting what it reports.

        A scan that matches nothing and a codebase with nothing wrong produce
        the same green tick. This project has shipped three separate checks
        that were silently reading no input, so the scanner is exercised on
        cases with known answers first — including the one-line form, which an
        earlier version of this scan missed entirely.
        """
        multiline = "x = post_journal(\n    organization=org,\n    lines=[{'a': (1)}],\n)\n"
        assert len(self._scan(multiline)) == 1
        assert "lines=" in self._scan(multiline)[0][2], "balanced walk stopped at a nested paren"

        oneline = "post_journal(organization=org, lines=lines, source_module=X)"
        assert len(self._scan(oneline)) == 1, "a single-line call must not be skipped"

        assert self._scan("def post_journal(\n    organization=None,\n): ...") == []
        assert self._scan("# see post_journal() for the contract\n") == []

        calls = self._calls()
        assert len(calls) >= 20, f"only {len(calls)} post_journal call(s) found — scan is broken"
        assert any("payroll_run" in body for _, _, body in calls), "payroll posting not found"

    def test_no_posting_is_filed_as_manual_by_omission(self) -> None:
        silent = [
            f"{path}:{line}" for path, line, body in self._calls() if "source_module=" not in body
        ]
        assert not silent, (
            "These postings inherit source_module=MANUAL by leaving the argument out, "
            "so the ledger records a machine posting as something a person typed:\n  "
            + "\n  ".join(silent)
        )

    def test_the_source_module_is_named_not_spelled(self) -> None:
        """``source_module="SALES"`` type-checks as a plain string and drifts.

        It also hid a call site from the first audit I ran, which looked only
        for the enum form — so the argument was added a second time and the
        server would not start.
        """
        literals = [
            f"{path}:{line}"
            for path, line, body in self._calls()
            if re.search(r'source_module=\s*"', body)
        ]
        assert not literals, "Use JournalEntry.Source.X, not a bare string:\n  " + "\n  ".join(
            literals
        )


class TestAPostingThatMovesNothingIsRefused:
    def test_a_nil_entry_does_not_post(
        self, org: Organization, accounts: tuple[Account, Account]
    ) -> None:
        """A payroll run for an employee with no salary produced exactly this.

        Zero debits equal zero credits, so it passed the balance check and
        posted six lines of nothing, with an audit record and a voucher.
        """
        with pytest.raises(ValueError, match="posts nothing"):
            _entry(org, accounts, "0")

    def test_a_real_entry_still_posts(
        self, org: Organization, accounts: tuple[Account, Account]
    ) -> None:
        assert _entry(org, accounts, "7500").total_debit == Decimal("7500")


class TestTheVoucherIsAVoucher:
    @staticmethod
    def _text(entry: JournalEntry) -> str:
        """The rendered voucher as one run of words.

        Whitespace is collapsed because a PDF has no sentences — the extractor
        returns text broken at whatever column the line happened to wrap at.
        Asserting against the raw extraction made the *negative* test below pass
        for the wrong reason: "carries no source document" was absent from a
        voucher that plainly said it, because the phrase wrapped after "source".
        """
        document = journal_voucher_document(entry=entry)
        raw = "\n".join(page.extract_text() for page in PdfReader(document.file.path).pages)
        return " ".join(raw.split())

    def test_it_carries_what_an_auditor_asks_for(
        self, org: Organization, accounts: tuple[Account, Account]
    ) -> None:
        text = self._text(_entry(org, accounts, "7500"))

        # Money reads as money. `str(Decimal)` gave "7500.00".
        assert "7,500.00" in text
        # The check nobody should have to perform by eye.
        assert "Debits equal credits" in text
        # The line that cannot be altered with a pen after signing.
        assert "Seven thousand five hundred Rwandan francs" in text
        # What caused the posting, and the account split by code.
        assert "stock_order" in text
        assert "2100" in text and "1100" in text
        # The control the voucher exists to evidence: a second signature.
        assert "Checked by" in text and "Authorised by" in text
        assert "JOURNAL VOUCHER" in text

    def test_a_reversed_entry_says_so_on_its_face(
        self, org: Organization, accounts: tuple[Account, Account]
    ) -> None:
        """Otherwise a voucher for a cancelled posting reads as a live one."""
        original = _entry(org, accounts, "7500")
        original.status = JournalEntry.Status.REVERSED
        original.save(update_fields=["status"])

        text = self._text(original)
        assert "REVERSED" in text
        assert "must not be presented as a live posting" in text

    def test_the_footer_does_not_claim_to_be_sole_evidence_when_it_is_not(
        self, org: Organization, accounts: tuple[Account, Account]
    ) -> None:
        """The claim is only true of a journal with no source document.

        It keyed off ``source_module`` first, which meant a settlement posting
        printed "a manual journal carries no source document" directly beneath
        "Raised by: stock_order · 13".
        """
        assert "carries no source document" not in self._text(_entry(org, accounts, "7500"))

    def test_a_typed_journal_does_claim_it(
        self, org: Organization, accounts: tuple[Account, Account]
    ) -> None:
        cash, payable = accounts
        typed = post_journal(
            organization=org,
            description="Correction of misposted rent",
            lines=[
                {"account": payable, "side": JournalLine.Side.DEBIT, "amount": Decimal("40000")},
                {"account": cash, "side": JournalLine.Side.CREDIT, "amount": Decimal("40000")},
            ],
        )
        text = self._text(typed)
        assert "carries no source document" in text
        assert "Typed directly" in text
