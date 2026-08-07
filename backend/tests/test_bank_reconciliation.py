"""Bank reconciliation: the bank's records against the ledger's.

The test that matters most is
`test_a_payment_that_left_the_bank_without_reaching_the_ledger_is_caught` — that
is the entire reason bank reconciliation exists, and the previous design (a
boolean an operator ticked on our own journal lines) could not detect it even in
principle.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from apps.finance.models import BankStatement, BankStatementLine, JournalLine
from apps.finance.reconciliation import (
    ReconciliationError,
    auto_match,
    close_reconciliation,
    explain_line,
    ignore_line,
    import_statement,
    ledger_balance,
    match_lines,
    parse_statement_csv,
    reconciliation_summary,
    suggestions_for,
    unmatch,
)
from apps.finance.services import create_bank_account, ensure_default_accounts, post_journal
from apps.iam.models import Organization

pytestmark = pytest.mark.django_db

START = date(2026, 6, 1)
END = date(2026, 6, 30)
D, C = JournalLine.Side.DEBIT, JournalLine.Side.CREDIT


@pytest.fixture
def org(db: None) -> Organization:
    organization = Organization.objects.create(name="Kimironko Pharmacy", type="RETAIL")
    ensure_default_accounts(organization)
    return organization


@pytest.fixture
def bank(org: Organization):
    return create_bank_account(
        organization=org,
        name="BK Current Account",
        kind="BANK",
        opening_balance=Decimal("0"),
        user=None,
    )


def _post(org: Organization, bank_gl, *, amount: str, when: date, description: str, out: bool):
    """A payment out of, or receipt into, the bank account."""
    accounts = ensure_default_accounts(org)
    value = Decimal(amount)
    lines = (
        [
            {"account": accounts["2100"], "side": D, "amount": value, "memo": ""},
            {"account": bank_gl, "side": C, "amount": value, "memo": ""},
        ]
        if out
        else [
            {"account": bank_gl, "side": D, "amount": value, "memo": ""},
            {"account": accounts["4100"], "side": C, "amount": value, "memo": ""},
        ]
    )
    return post_journal(organization=org, entry_date=when, description=description, lines=lines)


def _import(bank, rows, *, opening="0", closing=None):
    total = sum((Decimal(str(r["amount"])) for r in rows), Decimal("0"))
    return import_statement(
        bank_account=bank,
        rows=rows,
        start_date=START,
        end_date=END,
        opening_balance=Decimal(opening),
        closing_balance=Decimal(closing) if closing is not None else Decimal(opening) + total,
    )


def _row(day: int, amount: str, description: str = "", reference: str = "", **kw):
    return {
        "line_date": date(2026, 6, day),
        "description": description,
        "reference": reference,
        "amount": Decimal(amount),
        "balance": None,
        "external_id": kw.get("external_id", ""),
    }


# --------------------------------------------------------------------------- #
# Import
# --------------------------------------------------------------------------- #


def test_csv_with_a_signed_amount_column_is_read() -> None:
    rows = parse_statement_csv(
        "Date,Description,Reference,Amount,Balance\n"
        '01/06/2026,Opening transfer,TRF001,"1,200,000.00",1200000\n'
        "05/06/2026,Supplier payment,PAY99,(350000.00),850000\n"
    )
    assert len(rows) == 2
    assert rows[0]["amount"] == Decimal("1200000.00")
    # Parentheses mean negative on most bank exports.
    assert rows[1]["amount"] == Decimal("-350000.00")
    assert rows[1]["reference"] == "PAY99"


def test_csv_with_separate_debit_and_credit_columns_is_normalised() -> None:
    rows = parse_statement_csv(
        "Date,Narrative,Debit,Credit\n"
        "2026-06-03,Cash deposit,,500000\n"
        "2026-06-08,Bank charges,4500,\n"
    )
    assert rows[0]["amount"] == Decimal("500000.00")  # money in is positive
    assert rows[1]["amount"] == Decimal("-4500.00")  # money out is negative
    assert rows[1]["description"] == "Bank charges"


def test_a_statement_that_does_not_foot_is_refused(bank) -> None:
    """Opening plus movements must equal closing, or the file is incomplete."""
    with pytest.raises(ReconciliationError, match="does not foot"):
        import_statement(
            bank_account=bank,
            rows=[_row(5, "100000")],
            start_date=START,
            end_date=END,
            opening_balance=Decimal("0"),
            closing_balance=Decimal("999999"),
        )


def test_reimporting_the_same_period_does_not_duplicate_lines(bank) -> None:
    rows = [_row(5, "100000", "Deposit", external_id="TX1"), _row(6, "-25000", "Charge")]
    statement = _import(bank, rows)
    assert statement.lines.count() == 2

    again = _import(bank, rows)
    assert again.pk == statement.pk
    assert again.lines.count() == 2


# --------------------------------------------------------------------------- #
# The case the old design could not detect
# --------------------------------------------------------------------------- #


def test_a_payment_that_left_the_bank_without_reaching_the_ledger_is_caught(
    org: Organization, bank
) -> None:
    """The whole reason bank reconciliation exists.

    The bank shows a payment the books have never recorded. Ticking a boolean on
    our own journal lines — the previous design — could never surface this,
    because there was no journal line to tick.
    """
    _post(
        org, bank.gl_account, amount="400000", when=date(2026, 6, 3), description="Rent", out=True
    )

    statement = _import(
        bank,
        [
            _row(3, "-400000", "Rent"),
            _row(20, "-150000", "STANDING ORDER — insurance"),  # never in the books
        ],
    )
    auto_match(statement, user=None)

    summary = reconciliation_summary(statement)
    assert summary["is_reconciled"] is False
    assert summary["difference"] == "150000.00"
    assert "left the account without ever reaching the ledger" in summary["interpretation"]

    # And it cannot be signed off while that is true.
    with pytest.raises(ReconciliationError, match="Cannot sign off"):
        close_reconciliation(statement=statement, user=None)


# --------------------------------------------------------------------------- #
# Matching
# --------------------------------------------------------------------------- #


def test_auto_match_pairs_lines_on_amount_and_date(org: Organization, bank) -> None:
    _post(
        org,
        bank.gl_account,
        amount="250000",
        when=date(2026, 6, 4),
        description="Sale banking",
        out=False,
    )
    _post(
        org,
        bank.gl_account,
        amount="80000",
        when=date(2026, 6, 9),
        description="Supplier",
        out=True,
    )

    statement = _import(bank, [_row(4, "250000", "Deposit"), _row(11, "-80000", "Supplier")])
    result = auto_match(statement, user=None)

    assert result["matched"] == 2
    assert result["unmatched"] == 0
    assert statement.lines.filter(status=BankStatementLine.Status.MATCHED).count() == 2


def test_auto_match_refuses_to_guess_between_two_identical_payments(
    org: Organization, bank
) -> None:
    """Two identical payments on one day are genuinely ambiguous.

    Guessing would produce a reconciliation that looks complete while pointing at
    the wrong entry, so both are left for a human.
    """
    _post(
        org,
        bank.gl_account,
        amount="60000",
        when=date(2026, 6, 7),
        description="Supplier A",
        out=True,
    )
    _post(
        org,
        bank.gl_account,
        amount="60000",
        when=date(2026, 6, 7),
        description="Supplier B",
        out=True,
    )

    statement = _import(bank, [_row(7, "-60000", "Transfer")])
    result = auto_match(statement, user=None)

    assert result["matched"] == 0
    assert result["ambiguous"] == 1


def test_amounts_must_agree_exactly(org: Organization, bank) -> None:
    """ "Close enough" matching is how real differences get buried."""
    _post(
        org,
        bank.gl_account,
        amount="99000",
        when=date(2026, 6, 7),
        description="Supplier",
        out=True,
    )
    statement = _import(bank, [_row(7, "-100000", "Supplier")])

    assert auto_match(statement, user=None)["matched"] == 0


def test_a_manual_match_may_cover_several_ledger_lines(org: Organization, bank) -> None:
    """A payment run leaves the bank once but settles many bills in the ledger."""
    a = _post(
        org, bank.gl_account, amount="30000", when=date(2026, 6, 10), description="Bill A", out=True
    )
    b = _post(
        org, bank.gl_account, amount="70000", when=date(2026, 6, 10), description="Bill B", out=True
    )
    statement = _import(bank, [_row(10, "-100000", "Payment run")])
    line = statement.lines.first()
    assert line is not None

    ids = [
        a.lines.get(account=bank.gl_account).pk,
        b.lines.get(account=bank.gl_account).pk,
    ]
    match_lines(statement_line=line, journal_line_ids=ids, user=None)
    line.refresh_from_db()
    assert line.status == BankStatementLine.Status.MATCHED


def test_a_partial_match_is_refused(org: Organization, bank) -> None:
    """It would mark the bank line settled while leaving real money unaccounted for."""
    entry = _post(
        org, bank.gl_account, amount="30000", when=date(2026, 6, 10), description="Bill A", out=True
    )
    statement = _import(bank, [_row(10, "-100000", "Payment run")])
    line = statement.lines.first()
    assert line is not None

    with pytest.raises(ReconciliationError, match="partial match"):
        match_lines(
            statement_line=line,
            journal_line_ids=[entry.lines.get(account=bank.gl_account).pk],
            user=None,
        )


def test_a_ledger_line_cannot_be_matched_twice(org: Organization, bank) -> None:
    """Matching one payment against two bank lines would hide a duplicate."""
    entry = _post(
        org,
        bank.gl_account,
        amount="50000",
        when=date(2026, 6, 12),
        description="Supplier",
        out=True,
    )
    statement = _import(
        bank, [_row(12, "-50000", "One"), _row(13, "-50000", "Two")], closing="-100000"
    )
    first, second = list(statement.lines.all())
    journal_line = entry.lines.get(account=bank.gl_account)

    match_lines(statement_line=first, journal_line_ids=[journal_line.pk], user=None)
    with pytest.raises(ReconciliationError, match="already matched"):
        match_lines(statement_line=second, journal_line_ids=[journal_line.pk], user=None)


def test_unmatching_returns_both_sides_to_the_pool(org: Organization, bank) -> None:
    _post(
        org, bank.gl_account, amount="20000", when=date(2026, 6, 5), description="Sale", out=False
    )
    statement = _import(bank, [_row(5, "20000", "Deposit")])
    auto_match(statement, user=None)
    line = statement.lines.first()
    assert line is not None and line.status == BankStatementLine.Status.MATCHED

    unmatch(statement_line=line)
    line.refresh_from_db()
    assert line.status == BankStatementLine.Status.UNMATCHED
    assert line.matches.count() == 0


def test_suggestions_rank_a_matching_reference_highest(org: Organization, bank) -> None:
    _post(
        org,
        bank.gl_account,
        amount="45000",
        when=date(2026, 6, 6),
        description="INV-9001 settled",
        out=True,
    )
    _post(
        org,
        bank.gl_account,
        amount="45000",
        when=date(2026, 6, 8),
        description="Something else",
        out=True,
    )
    statement = _import(bank, [_row(6, "-45000", "Payment INV-9001", "INV-9001")], closing="-45000")

    rows = suggestions_for(statement)
    candidates = rows[0]["candidates"]
    assert len(candidates) == 2
    assert "INV-9001" in candidates[0]["description"]
    assert candidates[0]["confidence"] > candidates[1]["confidence"]


# --------------------------------------------------------------------------- #
# Explaining what the ledger never knew about
# --------------------------------------------------------------------------- #


def test_bank_charges_enter_the_books_only_from_the_statement(org: Organization, bank) -> None:
    """No internal document produces a bank charge — this is its only way in."""
    statement = _import(bank, [_row(30, "-4500", "MONTHLY SERVICE CHARGE")], closing="-4500")
    line = statement.lines.first()
    assert line is not None

    accounts = ensure_default_accounts(org)
    entry = explain_line(statement_line=line, account=accounts["6150"], user=None)

    line.refresh_from_db()
    assert line.status == BankStatementLine.Status.EXPLAINED
    charge = entry.lines.get(account=accounts["6150"])
    assert charge.side == D and charge.amount == Decimal("4500.00")
    # It posted to the bank account too, so the books now agree with the bank.
    assert ledger_balance(bank, as_of=END) == Decimal("-4500.00")


def test_interest_received_posts_the_other_way(org: Organization, bank) -> None:
    statement = _import(bank, [_row(30, "3000", "CREDIT INTEREST")], closing="3000")
    line = statement.lines.first()
    assert line is not None
    accounts = ensure_default_accounts(org)

    entry = explain_line(statement_line=line, account=accounts["4300"], user=None)
    assert entry.lines.get(account=accounts["4300"]).side == C
    assert ledger_balance(bank, as_of=END) == Decimal("3000.00")


def test_ignoring_a_line_requires_a_reason(org: Organization, bank) -> None:
    """A line dismissed without one is indistinguishable from one that was overlooked."""
    statement = _import(bank, [_row(15, "-1000", "Duplicate row")], closing="-1000")
    line = statement.lines.first()
    assert line is not None

    with pytest.raises(ReconciliationError, match="requires a reason"):
        ignore_line(statement_line=line, reason="  ")

    ignore_line(statement_line=line, reason="Duplicated by the bank's export.")
    line.refresh_from_db()
    assert line.status == BankStatementLine.Status.IGNORED
    assert line.note == "Duplicated by the bank's export."


# --------------------------------------------------------------------------- #
# The reconciliation statement
# --------------------------------------------------------------------------- #


def test_an_unpresented_payment_is_a_timing_difference_not_an_error(
    org: Organization, bank
) -> None:
    """A cheque written and posted but not yet presented belongs on the statement."""
    _post(
        org,
        bank.gl_account,
        amount="500000",
        when=date(2026, 6, 2),
        description="Banking",
        out=False,
    )
    # Written on the 28th, still not through the bank by month end.
    _post(
        org,
        bank.gl_account,
        amount="75000",
        when=date(2026, 6, 28),
        description="Cheque 118",
        out=True,
    )

    statement = _import(bank, [_row(2, "500000", "Banking")], closing="500000")
    auto_match(statement, user=None)

    summary = reconciliation_summary(statement)
    assert summary["balance_per_bank"] == "500000.00"
    assert summary["less_unpresented_payments"] == "75000.00"
    assert summary["expected_balance_per_books"] == "425000.00"
    assert summary["actual_balance_per_books"] == "425000.00"
    assert summary["difference"] == "0.00"
    assert summary["is_reconciled"] is True


def test_a_clean_period_can_be_signed_off(org: Organization, bank) -> None:
    _post(
        org,
        bank.gl_account,
        amount="120000",
        when=date(2026, 6, 4),
        description="Banking",
        out=False,
    )
    statement = _import(bank, [_row(4, "120000", "Banking")], closing="120000")
    auto_match(statement, user=None)

    close_reconciliation(statement=statement, user=None)
    statement.refresh_from_db()
    assert statement.status == BankStatement.Status.RECONCILED
    assert statement.reconciled_at is not None
    # The legacy per-line flag is kept in step so the cash book stays truthful.
    assert JournalLine.objects.filter(account=bank.gl_account, is_reconciled=True).count() == 1


def test_balances_that_agree_by_coincidence_are_not_a_reconciliation(
    org: Organization, bank
) -> None:
    """Two unexplained lines that happen to cancel out must not pass.

    The balances agree, but nothing accounts for either line — signing that off
    would certify an account nobody has actually checked.
    """
    statement = _import(
        bank, [_row(10, "90000", "Unknown credit"), _row(11, "-90000", "Unknown debit")]
    )
    auto_match(statement, user=None)

    summary = reconciliation_summary(statement)
    assert summary["difference"] == "0.00"
    assert summary["is_reconciled"] is False
    assert summary["unsettled_lines"] == 2
    assert "coincidence" in summary["interpretation"]

    with pytest.raises(ReconciliationError):
        close_reconciliation(statement=statement, user=None)
