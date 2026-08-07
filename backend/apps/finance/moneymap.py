"""The money map: every event in the business that makes or costs money, and the
posting that carries it into the ledger.

Finance is only meaningful if it hears about everything that moves money. That is
an auditable claim rather than a slogan, so this module states it as data: each
source declares its direction, its GL treatment, and the callable that posts it.

Two things fall out of writing it down:

* ``tests/test_money_map.py`` walks the registry and fails if a declared source
  has no importable posting path. A future feature that moves money and forgets
  the ledger breaks the build instead of quietly under-reporting costs.
* ``coverage()`` feeds the Finance home, so a gap is visible on a screen someone
  looks at weekly rather than discovered during the year-end audit.

Nine of these were broken or missing before the redesign — see
docs/development/finance-redesign-plan.md §1a.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from importlib import import_module
from typing import Any

from django.db.models import Count

from apps.iam.models import Organization

from .models import JournalEntry


class Direction:
    IN = "INFLOW"
    OUT = "OUTFLOW"
    INTERNAL = "INTERNAL"


@dataclass(frozen=True)
class MoneySource:
    key: str
    label: str
    direction: str
    module: str
    trigger: str
    treatment: str
    posting: str
    reference_types: tuple[str, ...]
    note: str = ""

    def resolve(self) -> Callable[..., Any] | None:
        """The posting callable, or None if this source has no wired path."""
        if not self.posting:
            return None
        module_path, _, attr = self.posting.rpartition(".")
        try:
            return getattr(import_module(module_path), attr)
        except (ImportError, AttributeError):
            return None

    @property
    def is_wired(self) -> bool:
        return self.resolve() is not None


MONEY_SOURCES: tuple[MoneySource, ...] = (
    # ---------------------------------------------------------------- inflows
    MoneySource(
        key="pos_sale",
        label="Retail POS sale",
        direction=Direction.IN,
        module=JournalEntry.Source.SALES,
        trigger="A sale is completed at the till",
        treatment=(
            "Dr Cash / MoMo / Card-in-transit per tender · Cr Revenue · Cr VAT Output; "
            "and Dr COGS / Cr Inventory at the FEFO batch cost"
        ),
        posting="apps.finance.services.post_sale_journal",
        reference_types=("sale", "sale_cogs"),
        note="Split tenders land in their own accounts — card money is not cash until it settles.",
    ),
    MoneySource(
        key="card_settlement",
        label="Card settlement",
        direction=Direction.IN,
        module=JournalEntry.Source.TREASURY,
        trigger="The acquirer pays the day's card takings, net of its fee",
        treatment="Dr Bank · Dr Card charges · Cr Card settlement in transit",
        posting="apps.finance.operations.settle_card_batch",
        reference_types=("card_settlement",),
    ),
    MoneySource(
        key="customer_invoice",
        label="B2B customer invoice",
        direction=Direction.IN,
        module=JournalEntry.Source.SALES,
        trigger="A wholesale invoice is raised on a credit customer",
        treatment="Dr Accounts receivable · Cr Revenue · Cr VAT Output",
        posting="apps.finance.services.record_customer_invoice",
        reference_types=("customer_invoice", "customer_invoice_cancel"),
    ),
    MoneySource(
        key="customer_receipt",
        label="Customer receipt",
        direction=Direction.IN,
        module=JournalEntry.Source.TREASURY,
        trigger="A credit customer pays",
        treatment="Dr Cash / Bank / MoMo · Cr Accounts receivable",
        posting="apps.finance.services.record_customer_receipt",
        reference_types=("customer_receipt",),
    ),
    # --------------------------------------------------------------- outflows
    MoneySource(
        key="goods_receipt",
        label="Goods receipt (GRN)",
        direction=Direction.OUT,
        module=JournalEntry.Source.PROCUREMENT,
        trigger="Stock is received against a purchase order",
        treatment="Dr Inventory on hand · Cr Goods received not invoiced",
        posting="apps.procurement.services.post_goods_receipt",
        reference_types=("goods_receipt",),
    ),
    MoneySource(
        key="supplier_invoice",
        label="Supplier invoice",
        direction=Direction.OUT,
        module=JournalEntry.Source.PROCUREMENT,
        trigger="A supplier invoice passes three-way match and is approved",
        treatment="Dr GRNI · Dr price variance to COGS · Dr VAT Input · Cr Accounts payable",
        posting="apps.procurement.services.post_supplier_invoice",
        reference_types=("supplier_invoice", "procurement.supplier_invoice", "supplier_note"),
    ),
    MoneySource(
        key="supplier_payment",
        label="Supplier payment",
        direction=Direction.OUT,
        module=JournalEntry.Source.TREASURY,
        trigger="A bill is paid, individually or in a payment run",
        treatment="Dr Accounts payable · Cr Bank / MoMo / Cash",
        posting="apps.finance.services.record_supplier_bill_payment",
        reference_types=("supplier_bill", "supplier_bill_payment"),
    ),
    MoneySource(
        key="payroll",
        label="Payroll & statutory",
        direction=Direction.OUT,
        module=JournalEntry.Source.PAYROLL,
        trigger="A payroll run is posted",
        treatment=(
            "Dr Salaries & employer contributions · Cr Net pay · Cr RSSB / RAMA / PAYE / CBHI"
        ),
        posting="apps.finance.services.post_payroll_journal",
        reference_types=("payroll_run", "payroll_employer", "payroll_record"),
    ),
    MoneySource(
        key="stock_count",
        label="Stock count variance",
        direction=Direction.OUT,
        module=JournalEntry.Source.INVENTORY,
        trigger="A physical count differs from the system quantity",
        treatment="Dr Inventory adjustments · Cr Inventory (or the reverse on a gain)",
        posting="apps.finance.services.post_inventory_adjustment",
        reference_types=("stock_count",),
    ),
    MoneySource(
        key="stock_writeoff",
        label="Stock disposal & write-off",
        direction=Direction.OUT,
        module=JournalEntry.Source.INVENTORY,
        trigger="Stock is destroyed, expired or written off — including recalled batches",
        treatment="Dr Shrinkage expense · Cr Inventory at batch cost",
        posting="apps.finance.services.post_writeoff",
        reference_types=("stock_writeoff", "stock_disposal"),
        note=(
            "A batch recall carries no value of its own — it is a freeze order. Its cost "
            "reaches the ledger when the frozen stock is disposed of through this path."
        ),
    ),
    MoneySource(
        key="expiry_provision",
        label="Expiry & slow-moving provision",
        direction=Direction.OUT,
        module=JournalEntry.Source.CLOSE,
        trigger="Month end, against the current expiry profile",
        treatment="Dr Shrinkage expense · Cr Provision for expiring stock (IAS 2)",
        posting="apps.finance.operations.post_expiry_provision",
        reference_types=("expiry_provision",),
    ),
    MoneySource(
        key="depreciation",
        label="Depreciation",
        direction=Direction.OUT,
        module=JournalEntry.Source.CLOSE,
        trigger="Month end, across the fixed asset register",
        treatment="Dr Depreciation expense · Cr Accumulated depreciation",
        posting="apps.finance.operations.run_depreciation",
        reference_types=("depreciation",),
    ),
    MoneySource(
        key="asset_disposal",
        label="Fixed asset disposal",
        direction=Direction.IN,
        module=JournalEntry.Source.TREASURY,
        trigger="An asset is sold or scrapped",
        treatment="Dr Cash · Dr Accumulated depreciation · Cr Asset cost · gain or loss to P&L",
        posting="apps.finance.services.dispose_fixed_asset",
        reference_types=("fixed_asset_dispose",),
    ),
    MoneySource(
        key="till_variance",
        label="Till over / short",
        direction=Direction.OUT,
        module=JournalEntry.Source.TREASURY,
        trigger="A cash drawer is closed and counted",
        treatment="Dr Cash over/short · Cr Cash (or the reverse on an overage)",
        posting="apps.finance.operations.post_drawer_variance",
        reference_types=("drawer_variance",),
    ),
    MoneySource(
        key="tax_payment",
        label="Tax payment to RRA",
        direction=Direction.OUT,
        module=JournalEntry.Source.TAX,
        trigger="VAT, PAYE or corporate tax is paid",
        treatment="Dr the statutory liability · Cr Bank",
        posting="apps.finance.services.record_tax_payment",
        reference_types=("tax_payment", "tax_record"),
    ),
    # -------------------------------------------------------------- internal
    MoneySource(
        key="stock_transfer",
        label="Inter-branch stock transfer",
        direction=Direction.INTERNAL,
        module=JournalEntry.Source.INVENTORY,
        trigger="Stock moves between two organizations in the same group",
        treatment="Nets to nil at group level — eliminated in consolidation",
        posting="apps.finance.services.post_payment_journal",
        reference_types=("stock_order", "shipment", "grn"),
        note=(
            "Group revenue must not count a sale from the depot to its own branch. "
            "The individual entities post correctly; the elimination at group level "
            "is still outstanding (redesign plan D7)."
        ),
    ),
)


SOURCES_BY_KEY: dict[str, MoneySource] = {s.key: s for s in MONEY_SOURCES}


def coverage() -> list[dict[str, Any]]:
    """Every declared source and whether its posting path resolves."""
    return [
        {
            "key": s.key,
            "label": s.label,
            "direction": s.direction,
            "module": s.module,
            "trigger": s.trigger,
            "treatment": s.treatment,
            "posting": s.posting,
            "reference_types": list(s.reference_types),
            "note": s.note,
            "wired": s.is_wired,
        }
        for s in MONEY_SOURCES
    ]


def posting_activity(organization: Organization, *, start: date, end: date) -> list[dict[str, Any]]:
    """The money map with real posting counts for a period.

    A source that is wired but has posted nothing all month is the interesting
    case: it is either genuinely idle or quietly broken, and only someone who
    knows the business can tell which. Showing the count lets them.
    """
    counts = dict(
        JournalEntry.objects.filter(
            organization=organization, entry_date__gte=start, entry_date__lte=end
        )
        .exclude(status=JournalEntry.Status.REVERSED)
        .values_list("reference_type")
        .annotate(n=Count("id"))
    )

    rows = []
    for source in coverage():
        postings = sum(counts.get(rt, 0) for rt in source["reference_types"])
        rows.append({**source, "postings": postings, "is_idle": source["wired"] and postings == 0})
    return rows


def summary(organization: Organization, *, start: date, end: date) -> dict[str, Any]:
    rows = posting_activity(organization, start=start, end=end)
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "total_sources": len(rows),
        "wired": sum(1 for r in rows if r["wired"]),
        "unwired": [r["key"] for r in rows if not r["wired"]],
        "idle": [r["key"] for r in rows if r["is_idle"]],
        "rows": rows,
    }
