"""Reconciling the bank's records against the ledger's.

The output that matters is :func:`reconciliation_summary`. It is the classic
four-line statement every accountant expects, and it is honest about the one
number that counts:

    balance per bank statement
      less  payments recorded but not yet on the statement (unpresented)
      add   receipts recorded but not yet on the statement (in transit)
      =     balance that *should* be in the books
      vs    the balance actually in the books
      =     the unexplained difference

If that last figure is not zero, the account is **not reconciled**, and this
module says so rather than rounding it away. An unexplained difference is the
signal — it is how a payment that left the account without ever reaching the
ledger gets found.

Bank charges and interest are a special case worth naming: no internal document
ever produces them, so they cannot be "matched" to anything. They enter the books
only by being posted *from* the statement, which is what :func:`explain_line`
does.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, cast

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.finance.services import JournalLineInput
from apps.iam.models import User

from .models import (
    Account,
    BankAccount,
    BankStatement,
    BankStatementLine,
    JournalEntry,
    JournalLine,
    ReconciliationMatch,
)
from .services import ensure_default_accounts, post_journal

ZERO = Decimal("0.00")
D, C = JournalLine.Side.DEBIT, JournalLine.Side.CREDIT

# How far apart a bank line and a ledger line may be dated and still be the same
# event. Cheques and transfers routinely clear a few days after they are posted.
MATCH_WINDOW_DAYS = 5


class ReconciliationError(Exception):
    """Raised when an import or a match would produce something incoherent."""


def _q(value: Any) -> Decimal:
    try:
        return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ReconciliationError(f"{value!r} is not a valid amount.") from exc


def _signed(line: JournalLine) -> Decimal:
    """A ledger line's effect on the cash account, positive for an increase."""
    return line.amount if line.side == D else -line.amount


# --------------------------------------------------------------------------- #
# Import
# --------------------------------------------------------------------------- #

_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%d %b %Y", "%d/%m/%y")


def _parse_date(raw: str) -> date:
    text = (raw or "").strip()
    for fmt in _DATE_FORMATS:
        try:
            return __import__("datetime").datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ReconciliationError(f"Could not read {raw!r} as a date.")


def _parse_amount(raw: str) -> Decimal:
    """Bank exports use thousands separators, currency prefixes and (parentheses)."""
    text = (raw or "").strip()
    if not text:
        return ZERO
    negative = text.startswith("(") and text.endswith(")")
    text = re.sub(r"[^0-9.\-]", "", text.strip("()"))
    if not text or text == "-":
        return ZERO
    value = _q(text)
    return -value if negative else value


def parse_statement_csv(text: str) -> list[dict[str, Any]]:
    """Read a bank CSV into normalised rows.

    Handles both shapes banks export: a single signed ``amount`` column, or
    separate ``debit``/``credit`` columns. The debit/credit pair is stated from
    the *bank's* perspective on some exports and ours on others, so the column
    names are read literally — money out of our account is a debit on our
    statement — and normalised to our sign convention here.
    """
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ReconciliationError("The file has no header row.")

    headers = {(h or "").strip().lower(): (h or "") for h in reader.fieldnames}

    def col(*names: str) -> str | None:
        for name in names:
            if name in headers:
                return headers[name]
        return None

    date_col = col("date", "transaction date", "value date", "posting date")
    if date_col is None:
        raise ReconciliationError("The file needs a 'date' column.")
    amount_col = col("amount", "value")
    debit_col = col("debit", "withdrawal", "money out", "paid out")
    credit_col = col("credit", "deposit", "money in", "paid in")
    if amount_col is None and debit_col is None and credit_col is None:
        raise ReconciliationError(
            "The file needs an 'amount' column, or 'debit' and 'credit' columns."
        )
    desc_col = col("description", "narrative", "details", "particulars", "memo")
    ref_col = col("reference", "ref", "transaction id", "cheque number")
    balance_col = col("balance", "running balance")
    id_col = col("id", "external id", "transaction id", "fitid")

    rows: list[dict[str, Any]] = []
    for raw in reader:
        if not any((v or "").strip() for v in raw.values()):
            continue  # blank padding row
        if amount_col is not None:
            amount = _parse_amount(raw.get(amount_col, ""))
        else:
            debit = _parse_amount(raw.get(debit_col, "")) if debit_col else ZERO
            credit = _parse_amount(raw.get(credit_col, "")) if credit_col else ZERO
            amount = abs(credit) - abs(debit)
        rows.append(
            {
                "line_date": _parse_date(raw.get(date_col, "")),
                "description": (raw.get(desc_col, "") or "").strip()[:255] if desc_col else "",
                "reference": (raw.get(ref_col, "") or "").strip()[:120] if ref_col else "",
                "amount": amount,
                "balance": _parse_amount(raw.get(balance_col, "")) if balance_col else None,
                "external_id": (raw.get(id_col, "") or "").strip()[:120] if id_col else "",
            }
        )
    if not rows:
        raise ReconciliationError("The file contained no transaction rows.")
    return rows


@transaction.atomic
def import_statement(
    *,
    bank_account: BankAccount,
    rows: list[dict[str, Any]],
    start_date: date,
    end_date: date,
    opening_balance: Decimal,
    closing_balance: Decimal,
    reference: str = "",
    source_filename: str = "",
    user: User | None = None,
) -> BankStatement:
    """Store one statement period.

    The import refuses a statement whose own arithmetic does not hold — opening
    plus the movements must equal closing. A statement that does not foot has
    been truncated, mis-parsed or edited, and reconciling the ledger against it
    would chase a difference that was never in the bank.

    Re-importing the same period tops up missing lines rather than duplicating
    them, keyed on the bank's own identifier where the export supplies one.
    """
    if end_date < start_date:
        raise ReconciliationError("The statement period ends before it starts.")

    opening, closing = _q(opening_balance), _q(closing_balance)
    movements = sum((_q(r["amount"]) for r in rows), ZERO)
    if _q(opening + movements) != closing:
        raise ReconciliationError(
            "The statement does not foot: opening "
            f"{opening} + movements {movements} = {_q(opening + movements)}, "
            f"but the closing balance is {closing}. Check the file is complete."
        )

    statement, created = BankStatement.objects.get_or_create(
        bank_account=bank_account,
        start_date=start_date,
        end_date=end_date,
        defaults={
            "reference": reference,
            "opening_balance": opening,
            "closing_balance": closing,
            "source_filename": source_filename,
            "imported_by": user,
        },
    )
    if not created and statement.status == BankStatement.Status.RECONCILED:
        raise ReconciliationError(
            "That period is already reconciled. Reopen it before importing again."
        )

    seen_ids = set(statement.lines.exclude(external_id="").values_list("external_id", flat=True))
    existing_fingerprints = {
        (line.line_date, line.amount, line.description)
        for line in statement.lines.filter(external_id="")
    }

    to_create: list[BankStatementLine] = []
    for row in rows:
        external_id = row.get("external_id") or ""
        if external_id and external_id in seen_ids:
            continue
        fingerprint = (row["line_date"], _q(row["amount"]), row.get("description", ""))
        if not external_id and fingerprint in existing_fingerprints:
            continue
        if external_id:
            seen_ids.add(external_id)
        else:
            existing_fingerprints.add(fingerprint)
        to_create.append(
            BankStatementLine(
                statement=statement,
                line_date=row["line_date"],
                description=row.get("description", ""),
                reference=row.get("reference", ""),
                amount=_q(row["amount"]),
                balance=_q(row["balance"]) if row.get("balance") is not None else None,
                external_id=external_id,
            )
        )
    BankStatementLine.objects.bulk_create(to_create)
    return statement


# --------------------------------------------------------------------------- #
# Matching
# --------------------------------------------------------------------------- #


def unmatched_ledger_lines(
    bank_account: BankAccount, *, up_to: date | None = None
) -> list[JournalLine]:
    """Ledger lines on this bank's account that no statement line has claimed."""
    qs = (
        JournalLine.objects.filter(account=bank_account.gl_account)
        .exclude(entry__status=JournalEntry.Status.REVERSED)
        .filter(reconciliation_matches__isnull=True)
        .select_related("entry")
    )
    if up_to is not None:
        qs = qs.filter(entry__entry_date__lte=up_to + timedelta(days=MATCH_WINDOW_DAYS))
    return list(qs.order_by("entry__entry_date", "id"))


def _reference_score(statement_line: BankStatementLine, journal_line: JournalLine) -> int:
    """How strongly the two texts corroborate each other, 0–30."""
    haystack = (
        f"{journal_line.entry.description} {journal_line.entry.entry_number} "
        f"{journal_line.memo}"
    ).lower()
    for token in (statement_line.reference, statement_line.description):
        token = (token or "").strip().lower()
        if len(token) >= 4 and token in haystack:
            return 30
    # A shared alphanumeric run of six or more (an invoice or cheque number) is
    # weaker evidence than a whole reference but much better than nothing.
    text = f"{statement_line.reference} {statement_line.description}".lower()
    tokens = set(re.findall(r"[a-z0-9]{6,}", text))
    if tokens & set(re.findall(r"[a-z0-9]{6,}", haystack)):
        return 20
    return 0


@dataclass
class Candidate:
    journal_line: JournalLine
    confidence: int


def candidates_for(
    statement_line: BankStatementLine, ledger_lines: list[JournalLine]
) -> list[Candidate]:
    """Ledger lines that could be this bank line, best first.

    Amount must agree exactly — a bank line and a ledger line for different
    amounts are two different events, and "close enough" matching is how real
    differences get buried.
    """
    out: list[Candidate] = []
    for line in ledger_lines:
        if _signed(line) != statement_line.amount:
            continue
        gap = abs((line.entry.entry_date - statement_line.line_date).days)
        if gap > MATCH_WINDOW_DAYS:
            continue
        confidence = 60
        if gap == 0:
            confidence += 10
        elif gap <= 2:
            confidence += 5
        confidence += _reference_score(statement_line, line)
        out.append(Candidate(journal_line=line, confidence=min(confidence, 100)))
    out.sort(key=lambda c: (-c.confidence, c.journal_line.entry.entry_date))
    return out


@transaction.atomic
def auto_match(statement: BankStatement, *, user: User | None = None) -> dict[str, int]:
    """Match what can be matched without judgement, and leave the rest.

    A bank line is only matched automatically when exactly **one** ledger line
    fits. Two identical payments on the same day are genuinely ambiguous, and
    guessing between them would produce a reconciliation that looks complete
    while pointing at the wrong entry — so they are left for a human.
    """
    ledger_lines = unmatched_ledger_lines(statement.bank_account, up_to=statement.end_date)
    by_id = {line.pk: line for line in ledger_lines}
    matched = ambiguous = 0

    for statement_line in statement.lines.filter(status=BankStatementLine.Status.UNMATCHED):
        available = [ln for ln in by_id.values() if ln.pk in by_id]
        options = candidates_for(statement_line, available)
        if not options:
            continue
        top = options[0].confidence
        if len([o for o in options if o.confidence == top]) > 1:
            ambiguous += 1
            continue
        chosen = options[0]
        ReconciliationMatch.objects.create(
            statement_line=statement_line,
            journal_line=chosen.journal_line,
            method=ReconciliationMatch.Method.AUTO,
            confidence=chosen.confidence,
            matched_by=user,
        )
        statement_line.status = BankStatementLine.Status.MATCHED
        statement_line.save(update_fields=["status"])
        by_id.pop(chosen.journal_line.pk, None)
        matched += 1

    if statement.status == BankStatement.Status.IMPORTED:
        statement.status = BankStatement.Status.RECONCILING
        statement.save(update_fields=["status"])

    return {
        "matched": matched,
        "ambiguous": ambiguous,
        "unmatched": statement.lines.filter(status=BankStatementLine.Status.UNMATCHED).count(),
    }


@transaction.atomic
def match_lines(
    *, statement_line: BankStatementLine, journal_line_ids: list[int], user: User | None = None
) -> BankStatementLine:
    """Match a bank line to one or more ledger lines by hand.

    The signed total of the ledger lines must equal the bank line. A part-match
    is not a match: it would mark the bank line settled while leaving real money
    unaccounted for.
    """
    bank_gl = statement_line.statement.bank_account.gl_account
    lines = list(
        JournalLine.objects.filter(pk__in=journal_line_ids, account=bank_gl).select_related("entry")
    )
    if len(lines) != len(set(journal_line_ids)):
        raise ReconciliationError(
            "Some of those ledger lines do not exist, or are not posted to this bank account."
        )
    claimed = set(
        ReconciliationMatch.objects.filter(journal_line__in=lines).values_list(
            "journal_line_id", flat=True
        )
    )
    already = [ln.pk for ln in lines if ln.pk in claimed]
    if already:
        raise ReconciliationError(
            f"Ledger line(s) {already} are already matched to another statement line."
        )

    total = sum((_signed(ln) for ln in lines), ZERO)
    if _q(total) != statement_line.amount:
        raise ReconciliationError(
            f"Those ledger lines total {_q(total)}, but the bank line is "
            f"{statement_line.amount}. A partial match would leave real money unaccounted for."
        )

    for line in lines:
        ReconciliationMatch.objects.create(
            statement_line=statement_line,
            journal_line=line,
            method=ReconciliationMatch.Method.MANUAL,
            matched_by=user,
        )
    statement_line.status = BankStatementLine.Status.MATCHED
    statement_line.save(update_fields=["status"])
    return statement_line


@transaction.atomic
def unmatch(*, statement_line: BankStatementLine) -> BankStatementLine:
    """Undo a match, returning both sides to the pool."""
    statement_line.matches.all().delete()
    statement_line.status = BankStatementLine.Status.UNMATCHED
    statement_line.save(update_fields=["status"])
    return statement_line


# --------------------------------------------------------------------------- #
# Explaining what the ledger never knew about
# --------------------------------------------------------------------------- #


@transaction.atomic
def explain_line(
    *,
    statement_line: BankStatementLine,
    account: Account,
    description: str = "",
    cost_centre: Any = None,
    user: User | None = None,
) -> JournalEntry:
    """Post a bank line the books had never heard of, and match it to itself.

    This is how **bank charges and interest** finally reach the ledger. No
    internal document produces them — they exist only on the statement — so
    without this they either sat unexplained forever or got quietly ticked off,
    which is how a business ends up not knowing what its banking costs.

        Money out:  Dr the chosen expense account   Cr the bank
        Money in:   Dr the bank                     Cr the chosen income account
    """
    statement = statement_line.statement
    bank_gl = statement.bank_account.gl_account
    amount = statement_line.amount
    if amount == 0:
        raise ReconciliationError("A zero-value line has nothing to post.")
    if statement_line.is_settled:
        raise ReconciliationError("That line is already settled.")

    outgoing = amount < 0
    value = abs(amount)
    lines = (
        [
            {
                "account": account,
                "side": D,
                "amount": value,
                "memo": statement_line.description[:200],
            },
            {"account": bank_gl, "side": C, "amount": value, "memo": "Per bank statement"},
        ]
        if outgoing
        else [
            {"account": bank_gl, "side": D, "amount": value, "memo": "Per bank statement"},
            {
                "account": account,
                "side": C,
                "amount": value,
                "memo": statement_line.description[:200],
            },
        ]
    )

    entry = post_journal(
        organization=statement.bank_account.organization,
        entry_date=statement_line.line_date,
        description=description or statement_line.description or "Posted from bank statement",
        lines=cast(list[JournalLineInput], lines),
        reference_type="bank_statement_line",
        reference_id=str(statement_line.pk),
        source_module=JournalEntry.Source.TREASURY,
        cost_centre=cost_centre,
        user=user,
    )

    bank_line = entry.lines.filter(account=bank_gl).first()
    if bank_line is not None:
        ReconciliationMatch.objects.get_or_create(
            statement_line=statement_line,
            journal_line=bank_line,
            defaults={"method": ReconciliationMatch.Method.MANUAL, "matched_by": user},
        )
    statement_line.status = BankStatementLine.Status.EXPLAINED
    statement_line.save(update_fields=["status"])
    return entry


@transaction.atomic
def ignore_line(*, statement_line: BankStatementLine, reason: str) -> BankStatementLine:
    """Set a line aside — but never silently.

    Ignoring is legitimate (a duplicate row in a bad export, a transfer that
    belongs to another account), and it must carry a reason, because a line
    dismissed without one is indistinguishable from one that was overlooked.
    """
    if not reason.strip():
        raise ReconciliationError("Ignoring a statement line requires a reason.")
    statement_line.status = BankStatementLine.Status.IGNORED
    statement_line.note = reason.strip()[:255]
    statement_line.save(update_fields=["status", "note"])
    return statement_line


# --------------------------------------------------------------------------- #
# The reconciliation statement
# --------------------------------------------------------------------------- #


def ledger_balance(bank_account: BankAccount, *, as_of: date) -> Decimal:
    """The books' balance on this account, inception to `as_of`."""
    lines = (
        JournalLine.objects.filter(account=bank_account.gl_account, entry__entry_date__lte=as_of)
        .exclude(entry__status=JournalEntry.Status.REVERSED)
        .only("amount", "side")
    )
    return _q(sum((_signed(line) for line in lines), ZERO))


def reconciliation_summary(statement: BankStatement) -> dict[str, Any]:
    """The four-line reconciliation, plus the difference it could not explain."""
    bank_account = statement.bank_account
    books = ledger_balance(bank_account, as_of=statement.end_date)

    # Ledger movements the bank has not reported by the statement date. These are
    # timing differences, not errors — a cheque written and posted but not yet
    # presented is exactly what this line of the statement is for.
    outstanding = [
        line
        for line in unmatched_ledger_lines(bank_account)
        if line.entry.entry_date <= statement.end_date
    ]
    unpresented = _q(
        sum((-_signed(ln) for ln in outstanding if _signed(ln) < 0), ZERO)
    )  # noqa: E501
    in_transit = _q(sum((_signed(ln) for ln in outstanding if _signed(ln) > 0), ZERO))

    expected_books = _q(statement.closing_balance - unpresented + in_transit)
    difference = _q(books - expected_books)

    lines = list(statement.lines.all())
    unsettled = [ln for ln in lines if not ln.is_settled]

    return {
        "statement_id": statement.pk,
        "bank_account": bank_account.name,
        "start": statement.start_date.isoformat(),
        "end": statement.end_date.isoformat(),
        "status": statement.status,
        "balance_per_bank": str(statement.closing_balance),
        "less_unpresented_payments": str(unpresented),
        "add_deposits_in_transit": str(in_transit),
        "expected_balance_per_books": str(expected_books),
        "actual_balance_per_books": str(books),
        "difference": str(difference),
        "is_reconciled": difference == 0 and not unsettled,
        "statement_lines": len(lines),
        "unsettled_lines": len(unsettled),
        "outstanding_ledger_lines": len(outstanding),
        "interpretation": _interpret(difference, len(unsettled)),
    }


def _interpret(difference: Decimal, unsettled: int) -> str:
    if difference != 0:
        return (
            f"The books and the bank differ by {difference} that nothing accounts for. "
            "Something has been posted twice, posted for the wrong amount, or has left "
            "the account without ever reaching the ledger."
        )
    if unsettled:
        return (
            f"{unsettled} statement line(s) are still unexplained. The balances agree, "
            "but until every line is matched or posted the agreement is a coincidence."
        )
    return "Every statement line is accounted for and the balances agree."


@transaction.atomic
def close_reconciliation(*, statement: BankStatement, user: User | None = None) -> BankStatement:
    """Sign the reconciliation off — only if it actually reconciles."""
    summary = reconciliation_summary(statement)
    if not summary["is_reconciled"]:
        raise ReconciliationError(f"Cannot sign off: {summary['interpretation']}")
    statement.status = BankStatement.Status.RECONCILED
    statement.reconciled_by = user
    statement.reconciled_at = timezone.now()
    statement.save(update_fields=["status", "reconciled_by", "reconciled_at"])

    # Keep the legacy per-line flag in step so the cash-book view stays truthful.
    JournalLine.objects.filter(reconciliation_matches__statement_line__statement=statement).update(
        is_reconciled=True,
        reconciled_at=timezone.now(),
        statement_reference=statement.reference or str(statement.pk),
    )
    return statement


def suggestions_for(statement: BankStatement, *, limit: int = 5) -> list[dict[str, Any]]:
    """Candidate ledger lines for each unmatched bank line, best first."""
    ledger_lines = unmatched_ledger_lines(statement.bank_account, up_to=statement.end_date)
    out: list[dict[str, Any]] = []
    for statement_line in statement.lines.filter(status=BankStatementLine.Status.UNMATCHED):
        options = candidates_for(statement_line, ledger_lines)[:limit]
        out.append(
            {
                "statement_line_id": statement_line.pk,
                "line_date": statement_line.line_date.isoformat(),
                "description": statement_line.description,
                "amount": str(statement_line.amount),
                "candidates": [
                    {
                        "journal_line_id": c.journal_line.pk,
                        "entry_number": c.journal_line.entry.entry_number,
                        "entry_date": c.journal_line.entry.entry_date.isoformat(),
                        "description": c.journal_line.entry.description,
                        "amount": str(_signed(c.journal_line)),
                        "confidence": c.confidence,
                    }
                    for c in options
                ],
            }
        )
    return out


def unexplained_report(bank_account: BankAccount, *, as_of: date) -> dict[str, Any]:
    """Everything still unaccounted for on this account, across all statements."""
    unsettled = BankStatementLine.objects.filter(
        statement__bank_account=bank_account, statement__end_date__lte=as_of
    ).exclude(
        status__in=[
            BankStatementLine.Status.MATCHED,
            BankStatementLine.Status.EXPLAINED,
            BankStatementLine.Status.IGNORED,
        ]
    )
    outstanding = [
        ln for ln in unmatched_ledger_lines(bank_account) if ln.entry.entry_date <= as_of
    ]
    return {
        "bank_account": bank_account.name,
        "as_of": as_of.isoformat(),
        "bank_lines_unexplained": [
            {
                "id": ln.pk,
                "date": ln.line_date.isoformat(),
                "description": ln.description,
                "amount": str(ln.amount),
            }
            for ln in unsettled.order_by("line_date")
        ],
        "ledger_lines_unpresented": [
            {
                "id": ln.pk,
                "date": ln.entry.entry_date.isoformat(),
                "entry_number": ln.entry.entry_number,
                "description": ln.entry.description,
                "amount": str(_signed(ln)),
            }
            for ln in outstanding
        ],
    }


def default_charge_account(bank_account: BankAccount) -> Account:
    """Where an unexplained outgoing bank line lands unless told otherwise."""
    accounts = ensure_default_accounts(bank_account.organization)
    return accounts["6150"]


def bank_accounts_needing_attention(organization: Any) -> list[dict[str, Any]]:
    """Accounts with an open reconciliation — what the close checklist reads."""
    rows: list[dict[str, Any]] = []
    for account in BankAccount.objects.filter(organization=organization, is_active=True):
        open_statements = account.statements.filter(
            ~Q(status=BankStatement.Status.RECONCILED)
        ).count()
        rows.append(
            {
                "bank_account_id": account.pk,
                "name": account.name,
                "kind": account.kind,
                "open_statements": open_statements,
                "last_reconciled": (
                    account.statements.filter(status=BankStatement.Status.RECONCILED)
                    .order_by("-end_date")
                    .values_list("end_date", flat=True)
                    .first()
                ),
            }
        )
    return rows
