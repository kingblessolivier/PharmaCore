"""Chart-ready figures for a module's home screen.

The module homes were a work queue and then a grid of cards that were really
navigation — a second copy of the menu, one click deeper. The menu is the menu;
a home screen should answer *how is this part of the business doing*.

Everything here is a real aggregate over the organizations the viewer can see.
Nothing is sampled, estimated or invented to fill a chart: a composition with no
data returns an empty list and the chart says so, which is more useful than a
convincing-looking placeholder.

Each module returns the same shape so the frontend renders them uniformly:

    {"tiles": [...], "donuts": [...], "bars": [...],
     "trend": [{"label": ..., "values": [...]}], "trend_series": [...]}

Donuts answer "what is this made of" — a question of composition, which is the
only thing a pie is good at. Bars answer "which is biggest". Trends answer "is
this getting better or worse". A figure that does not answer one of those three
is a tile, not a chart.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Count, DecimalField, F, Sum, Value
from django.utils import timezone

ZERO = Decimal("0.00")

#: The shape every module returns, so one component can render any of them.
EMPTY: dict[str, Any] = {"tiles": [], "donuts": [], "bars": [], "trend": [], "trend_series": []}


def _money(value: Any) -> float:
    return float(Decimal(str(value or 0)).quantize(Decimal("0.01")))


def _slices(rows: Any, label_key: str, value_key: str = "n") -> list[dict[str, Any]]:
    """Turn a values().annotate() result into donut slices, dropping the empties."""
    return [
        {"label": str(row[label_key] or "—").replace("_", " ").title(), "value": row[value_key]}
        for row in rows
        if row[value_key]
    ]


# ---------------------------------------------------------------------------
# Modules
# ---------------------------------------------------------------------------


def _retail(org_ids: list[int]) -> dict[str, Any]:
    from apps.retail.models import Payment, Sale

    today = timezone.localdate()
    start = today - timedelta(days=13)

    sales = (
        Sale.objects.filter(
            organization_id__in=org_ids,
            status=Sale.Status.COMPLETED,
            completed_at__date__gte=start,
        )
        .select_related("organization")
        .prefetch_related("items")
    )

    by_day: dict[Any, Decimal] = defaultdict(lambda: ZERO)
    for sale in sales:
        day = timezone.localtime(sale.completed_at).date() if sale.completed_at else today
        by_day[day] += Decimal(str(sale.total))

    # How customers actually pay — the mix decides whether the drawer balances,
    # what the mobile-money fees cost, and how much sits in receivables.
    tender = (
        Payment.objects.filter(sale__organization_id__in=org_ids)
        .values("method")
        .annotate(n=Count("id"))
    )

    return {
        "tiles": [
            {"label": "Sales, 14 days", "value": sales.count()},
            {
                "label": "Revenue, 14 days",
                "value": _money(sum((Decimal(str(s.total)) for s in sales), ZERO)),
                "money": True,
            },
        ],
        "donuts": [
            {
                "title": "How customers paid",
                "subtitle": "Every payment recorded",
                "slices": _slices(tender, "method"),
            }
        ],
        "bars": [],
        "trend_series": ["Revenue"],
        "trend": [
            {
                "label": (start + timedelta(days=i)).isoformat(),
                "values": [_money(by_day.get(start + timedelta(days=i)))],
            }
            for i in range(14)
        ],
    }


def _inventory(org_ids: list[int]) -> dict[str, Any]:
    from apps.inventory.models import InventoryBatch

    today = timezone.localdate()
    batches = InventoryBatch.objects.filter(organization_id__in=org_ids, quantity_available__gt=0)

    # Where the money is sitting, by how long it has left. The bands are the ones
    # the expiry forecast uses, so the two screens never disagree.
    bands = {"Expired": ZERO, "Within 30 days": ZERO, "31-90 days": ZERO, "Over 90 days": ZERO}
    for row in batches.values("expiry_date", "quantity_available", "wholesale_cost"):
        value = Decimal(str(row["wholesale_cost"] or 0)) * row["quantity_available"]
        days = (row["expiry_date"] - today).days
        key = (
            "Expired"
            if days < 0
            else "Within 30 days" if days <= 30 else "31-90 days" if days <= 90 else "Over 90 days"
        )
        bands[key] += value

    status = batches.values("status").annotate(n=Count("id"))
    total = sum(bands.values(), ZERO)

    return {
        "tiles": [
            {"label": "Batches on hand", "value": batches.count()},
            {"label": "Stock at cost", "value": _money(total), "money": True},
        ],
        "donuts": [
            {
                "title": "Stock value by shelf life",
                "subtitle": "What is sitting on the shelf, and how long it has",
                "slices": [{"label": k, "value": _money(v)} for k, v in bands.items() if v > 0],
                "money": True,
            },
            {
                "title": "Batches by state",
                "subtitle": "Quarantined and recalled stock cannot be sold",
                "slices": _slices(status, "status"),
            },
        ],
        "bars": [],
        "trend": [],
    }


def _distribution(org_ids: list[int]) -> dict[str, Any]:
    from apps.distribution.models import BackorderLine, StockOrder

    orders = StockOrder.objects.filter(depot_id__in=org_ids)
    status = orders.values("status").annotate(n=Count("id"))
    payment = orders.values("payment_status").annotate(n=Count("id"))

    # What retailers asked for and the depot could not supply — the demand that
    # should be driving the next import.
    unmet = (
        BackorderLine.objects.filter(depot_id__in=org_ids, status=BackorderLine.Status.OPEN)
        .values("product__generic_name")
        .annotate(n=Sum("quantity"))
        .order_by("-n")[:8]
    )

    return {
        "tiles": [
            {"label": "Orders received", "value": orders.count()},
            {
                "label": "Unmet demand",
                "value": sum(row["n"] or 0 for row in unmet),
                "hint": "units retailers could not get",
            },
        ],
        "donuts": [
            {
                "title": "Orders by state",
                "subtitle": "Where the trade is sitting",
                "slices": _slices(status, "status"),
            },
            {
                "title": "Settlement",
                "subtitle": "What has been paid for",
                "slices": _slices(payment, "payment_status"),
            },
        ],
        "bars": [
            {
                "title": "Most asked for and not supplied",
                "subtitle": "The strongest signal for what to import next",
                "data": [
                    {"label": row["product__generic_name"] or "—", "value": row["n"] or 0}
                    for row in unmet
                ],
            }
        ],
        "trend": [],
    }


def _procurement(org_ids: list[int]) -> dict[str, Any]:
    from apps.procurement.models import PurchaseOrder, PurchaseOrderLine, SupplierProfile

    orders = PurchaseOrder.objects.filter(organization_id__in=org_ids)
    status = orders.values("status").annotate(n=Count("id"))

    # `total_amount` is a Python property, so it cannot be summed in SQL. This
    # mirrors `PurchaseOrderLine.line_subtotal` exactly — order value net of line
    # discounts — which is the comparable figure across suppliers anyway, since
    # freight and header charges are negotiated per shipment rather than per supplier.
    spend = (
        PurchaseOrderLine.objects.filter(order__in=orders)
        .values("order__supplier__name")
        .annotate(
            n=Sum(
                F("unit_price")
                * (Value(Decimal("100")) - F("discount_pct"))
                / Value(Decimal("100"))
                * F("quantity_ordered"),
                output_field=DecimalField(max_digits=18, decimal_places=2),
            )
        )
        .order_by("-n")[:8]
    )
    standing = SupplierProfile.objects.values("standing").annotate(n=Count("id"))

    return {
        "tiles": [
            {"label": "Purchase orders", "value": orders.count()},
            {"label": "Suppliers", "value": SupplierProfile.objects.count()},
        ],
        "donuts": [
            {
                "title": "Orders by state",
                "subtitle": "What is still to be received",
                "slices": _slices(status, "status"),
            },
            {
                "title": "Suppliers by standing",
                "subtitle": "Suspended and blacklisted cannot receive orders",
                "slices": _slices(standing, "standing"),
            },
        ],
        "bars": [
            {
                "title": "Spend by supplier",
                "subtitle": "Where the buying budget goes",
                "money": True,
                "data": [
                    {"label": row["order__supplier__name"] or "—", "value": _money(row["n"])}
                    for row in spend
                ],
            }
        ],
        "trend": [],
    }


def _insurance(org_ids: list[int]) -> dict[str, Any]:
    from apps.insurance.models import Claim

    claims = Claim.objects.filter(organization_id__in=org_ids)
    status = claims.values("status").annotate(n=Count("id"))

    # Rejections are money already spent, so the reason is the useful breakdown.
    rejected = (
        claims.filter(status=Claim.Status.REJECTED)
        .exclude(rejection_reason="")
        .values("rejection_reason")
        .annotate(n=Count("id"))
    )
    by_scheme = claims.values("scheme__name").annotate(n=Sum("claimed_amount")).order_by("-n")[:8]
    outstanding = claims.aggregate(v=Sum("claimed_amount"))["v"] or 0

    return {
        "tiles": [
            {"label": "Claims", "value": claims.count()},
            {"label": "Claimed to date", "value": _money(outstanding), "money": True},
        ],
        "donuts": [
            {
                "title": "Claims by state",
                "subtitle": "What the schemes have done with them",
                "slices": _slices(status, "status"),
            },
            {
                "title": "Why claims were rejected",
                "subtitle": "Each reason has a different remedy",
                "slices": _slices(rejected, "rejection_reason"),
            },
        ],
        "bars": [
            {
                "title": "Claimed by scheme",
                "subtitle": "Who owes the pharmacy most",
                "money": True,
                "data": [
                    {"label": row["scheme__name"] or "—", "value": _money(row["n"])}
                    for row in by_scheme
                ],
            }
        ],
        "trend": [],
    }


def _people(org_ids: list[int]) -> dict[str, Any]:
    from apps.hr.models import Employee

    staff = Employee.objects.filter(organization_id__in=org_ids)
    status = staff.values("employment_status").annotate(n=Count("id"))
    kind = staff.values("employment_type").annotate(n=Count("id"))

    return {
        "tiles": [
            {"label": "Employees", "value": staff.count()},
            {
                "label": "Active",
                "value": staff.filter(employment_status="ACTIVE").count(),
            },
        ],
        "donuts": [
            {
                "title": "Headcount by status",
                "subtitle": "Who is currently working",
                "slices": _slices(status, "employment_status"),
            },
            {
                "title": "By contract type",
                "subtitle": "The shape of the workforce",
                "slices": _slices(kind, "employment_type"),
            },
        ],
        "bars": [],
        "trend": [],
    }


def _catalog(org_ids: list[int]) -> dict[str, Any]:
    from apps.catalog.models import Product
    from apps.inventory.models import PharmacyProduct

    listed = PharmacyProduct.objects.filter(organization_id__in=org_ids, is_active=True)
    products = Product.objects.filter(pk__in=listed.values_list("product_id", flat=True))
    form = products.values("dosage_form").annotate(n=Count("id"))
    controls = {
        "Prescription only": products.filter(requires_prescription=True).count(),
        "Controlled": products.filter(is_controlled_substance=True).count(),
        "Over the counter": products.filter(
            requires_prescription=False, is_controlled_substance=False
        ).count(),
    }

    return {
        "tiles": [
            # Distinct medicines, not shelf listings: the same product listed by
            # six branches is one medicine, and counting rows made "stocked"
            # exceed "in the catalogue", which cannot be true.
            {"label": "Medicines stocked", "value": products.count()},
            {"label": "In the catalogue", "value": Product.objects.count()},
        ],
        "donuts": [
            {
                "title": "How tightly controlled",
                "subtitle": "What may be sold without a prescription",
                "slices": [{"label": k, "value": v} for k, v in controls.items() if v],
            },
            {
                "title": "By dosage form",
                "subtitle": "The shape of what is stocked",
                "slices": _slices(form, "dosage_form"),
            },
        ],
        "bars": [],
        "trend": [],
    }


def _finance(org_ids: list[int]) -> dict[str, Any]:
    from apps.finance.models import (
        CustomerInvoice,
        JournalEntry,
        JournalLine,
        SupplierBill,
    )

    today = timezone.localdate()

    posted = JournalLine.objects.filter(
        entry__organization_id__in=org_ids, entry__status=JournalEntry.Status.POSTED
    )

    def _side_total(account_type: str, side: str) -> Decimal:
        value = posted.filter(account__account_type=account_type, side=side).aggregate(
            v=Sum("amount")
        )["v"]
        return Decimal(str(value or 0))

    # A trial balance in four numbers. Revenue is a credit balance and expenses a
    # debit balance, so each is netted the way its own side runs — reading both
    # as "sum of amount" would report a refund as extra income.
    revenue = _side_total("REVENUE", "CREDIT") - _side_total("REVENUE", "DEBIT")
    expenses = _side_total("EXPENSE", "DEBIT") - _side_total("EXPENSE", "CREDIT")

    # Where the money sits. Assets are what the business holds, liabilities what
    # it owes, equity the difference — the shape of the balance sheet, which is
    # the one composition the ledger can always answer once anything is posted.
    sits = {}
    for label, account_type, normal in (
        ("Assets", "ASSET", "DEBIT"),
        ("Liabilities", "LIABILITY", "CREDIT"),
        ("Equity", "EQUITY", "CREDIT"),
    ):
        other = "CREDIT" if normal == "DEBIT" else "DEBIT"
        balance = _side_total(account_type, normal) - _side_total(account_type, other)
        if balance > 0:
            sits[label] = _money(balance)

    # Performance over time — the question Finance actually exists to answer.
    # Twelve months of revenue, expenses and what is left, read off the same
    # posted lines as the totals above so the chart and the tiles agree.
    months: list[str] = []
    cursor = today.replace(day=1)
    for _ in range(12):
        months.append(cursor.isoformat()[:7])
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    months.reverse()

    monthly: dict[str, dict[str, Decimal]] = {m: {"REVENUE": ZERO, "EXPENSE": ZERO} for m in months}
    for row in posted.filter(
        account__account_type__in=("REVENUE", "EXPENSE"),
        entry__entry_date__gte=months[0] + "-01",
    ).values("entry__entry_date", "account__account_type", "side", "amount"):
        bucket = monthly.get(row["entry__entry_date"].isoformat()[:7])
        if bucket is None:
            continue
        kind = row["account__account_type"]
        amount = Decimal(str(row["amount"] or 0))
        # Each runs on its own side; the other side is a reversal or a refund.
        natural = "CREDIT" if kind == "REVENUE" else "DEBIT"
        bucket[kind] += amount if row["side"] == natural else -amount

    trend = [
        {
            "label": f"{month}-01",
            "values": [
                _money(monthly[month]["REVENUE"]),
                _money(monthly[month]["EXPENSE"]),
                _money(monthly[month]["REVENUE"] - monthly[month]["EXPENSE"]),
            ],
        }
        for month in months
    ]

    # How much of the ledger was typed by a person rather than produced by a
    # subsystem. A book that is mostly MANUAL is a book with a control problem,
    # so this is a governance figure, not decoration.
    produced = (
        JournalEntry.objects.filter(organization_id__in=org_ids, status=JournalEntry.Status.POSTED)
        .values("source_module")
        .annotate(n=Count("id"))
    )

    # The biggest movements, whichever side they fall on.
    movements = (
        posted.values("account__name", "account__account_type")
        .annotate(n=Sum("amount"))
        .filter(n__gt=0)
        .order_by("-n")[:8]
    )

    invoices = CustomerInvoice.objects.filter(organization_id__in=org_ids).exclude(
        status__in=[CustomerInvoice.Status.PAID, CustomerInvoice.Status.CANCELLED]
    )
    # Ageing, the way a credit controller reads it: not "how much is owed" but
    # "how long has it been owed", because that is what decides who gets chased.
    ageing = {"Not yet due": ZERO, "1-30 days": ZERO, "31-60 days": ZERO, "Over 60 days": ZERO}
    for invoice in invoices.values("due_date", "total_amount", "amount_paid"):
        owed = Decimal(str(invoice["total_amount"] or 0)) - Decimal(
            str(invoice["amount_paid"] or 0)
        )
        if owed <= 0:
            continue
        overdue_days = (today - invoice["due_date"]).days if invoice["due_date"] else 0
        key = (
            "Not yet due"
            if overdue_days <= 0
            else (
                "1-30 days"
                if overdue_days <= 30
                else "31-60 days" if overdue_days <= 60 else "Over 60 days"
            )
        )
        ageing[key] += owed

    bills = SupplierBill.objects.filter(organization_id__in=org_ids).exclude(
        status=SupplierBill.Status.PAID
    )
    payable = sum(
        (
            Decimal(str(b["total_amount"] or 0)) - Decimal(str(b["amount_paid"] or 0))
            for b in bills.values("total_amount", "amount_paid")
        ),
        ZERO,
    )
    receivable = sum(ageing.values(), ZERO)

    spend = (
        posted.filter(account__account_type="EXPENSE", side=JournalLine.Side.DEBIT)
        .values("account__name")
        .annotate(n=Sum("amount"))
        .filter(n__gt=0)
        .order_by("-n")[:8]
    )

    donuts: list[dict[str, Any]] = [
        {
            "title": "Where the money went",
            "subtitle": "Posted expenses by account",
            "slices": [
                {"label": row["account__name"] or "—", "value": _money(row["n"])} for row in spend
            ],
            "money": True,
        },
        {
            "title": "Where the money sits",
            "subtitle": "Assets against what is owed on them",
            "slices": [{"label": k, "value": v} for k, v in sits.items()],
            "money": True,
            # Assets plus liabilities is not a quantity of anything — the two
            # are opposite sides of the same balance. The ring shows the split;
            # putting their sum in the middle would invent a figure.
            "sums": False,
        },
        {
            "title": "What produced the entries",
            "subtitle": "A book that is mostly manual is a book to look at",
            "slices": _slices(produced, "source_module"),
        },
    ]
    # Only shown when somebody actually owes money — an empty ageing chart tells
    # a pharmacy with no credit customers nothing at all.
    if receivable > 0:
        donuts.append(
            {
                "title": "Money owed to us, by age",
                "subtitle": "How long it has been outstanding decides who is chased first",
                "slices": [{"label": k, "value": _money(v)} for k, v in ageing.items() if v > 0],
                "money": True,
            }
        )

    return {
        "tiles": [
            {"label": "Revenue posted", "value": _money(revenue), "money": True},
            {"label": "Expenses posted", "value": _money(expenses), "money": True},
            {"label": "Owed to us", "value": _money(receivable), "money": True},
            {"label": "Owed by us", "value": _money(payable), "money": True},
        ],
        "donuts": donuts,
        "bars": [
            {
                "title": "Largest movements in the ledger",
                "subtitle": "Total posted against each account",
                "money": True,
                "data": [
                    {
                        "label": row["account__name"] or "—",
                        "value": _money(row["n"]),
                        "note": str(row["account__account_type"] or "").title(),
                    }
                    for row in movements
                ],
            }
        ],
        "trend_series": ["Revenue", "Expenses", "Left over"],
        "trend": trend,
    }


def _admin(org_ids: list[int]) -> dict[str, Any]:
    """The control room: who is in the system, what it is made of, and what it is doing.

    Admin is the one module whose subject is the system itself, so this is
    deliberately the broadest of the nine — access, estate, compliance and
    activity, rather than one business process.
    """
    from apps.iam.models import AuditLog, Company, Department, License, Organization, User

    today = timezone.localdate()
    start = today - timedelta(days=13)

    users = User.objects.filter(organization_id__in=org_ids, is_active=True)
    roles = users.values("roles__code").annotate(n=Count("id"))
    orgs = Organization.objects.filter(pk__in=org_ids)
    licences = License.objects.filter(organization_id__in=org_ids)
    expiring = licences.filter(expiry_date__gte=today, expiry_date__lte=today + timedelta(days=60))
    audit = AuditLog.objects.filter(organization_id__in=org_ids)

    # Fourteen days of activity, split into the two reads that matter: people
    # arriving, and records changing. A quiet day on both is a system nobody is
    # using; a busy day on sign-ins alone is a system people log into and leave.
    recent = audit.filter(created_at__date__gte=start)
    by_day: dict[Any, dict[str, int]] = {
        start + timedelta(days=i): {"sign_ins": 0, "changes": 0} for i in range(14)
    }
    for row in recent.values("created_at", "action"):
        day = timezone.localtime(row["created_at"]).date()
        bucket = by_day.get(day)
        if bucket is None:
            continue
        if row["action"] in ("LOGIN", "LOGIN_FAILED"):
            bucket["sign_ins"] += 1
        elif row["action"] in ("CREATE", "UPDATE", "DELETE"):
            bucket["changes"] += 1

    # A failed sign-in rate is a security read, not a usage one, so it gets its
    # own tile rather than hiding inside the activity total.
    sign_in_attempts = audit.filter(action__in=("LOGIN", "LOGIN_FAILED")).count()
    failed = audit.filter(action="LOGIN_FAILED").count()

    busiest = (
        audit.exclude(user=None).values("user__username").annotate(n=Count("id")).order_by("-n")[:8]
    )
    where = (
        users.values("organization__name")
        .annotate(n=Count("id"))
        .filter(n__gt=0)
        .order_by("-n")[:8]
    )

    return {
        "tiles": [
            {"label": "Active users", "value": users.count()},
            {"label": "Organizations", "value": orgs.count()},
            {
                "label": "Companies",
                "value": Company.objects.filter(branches__in=orgs).distinct().count(),
            },
            {
                "label": "Departments",
                "value": Department.objects.filter(organization__in=orgs).count(),
            },
            {
                "label": "Licences expiring",
                "value": expiring.count(),
                "hint": "within 60 days",
            },
            {
                "label": "Failed sign-ins",
                "value": failed,
                "hint": f"of {sign_in_attempts} attempt(s)",
            },
        ],
        "donuts": [
            {
                "title": "People by role",
                "subtitle": "Who holds what — a role nobody holds is a gap",
                "slices": _slices(roles, "roles__code"),
            },
            {
                "title": "Organizations by type",
                "subtitle": "The shape of the group",
                "slices": _slices(orgs.values("type").annotate(n=Count("id")), "type"),
            },
            {
                "title": "What is being worked on",
                "subtitle": "Records changed, by kind",
                "slices": _slices(
                    audit.filter(action__in=("CREATE", "UPDATE", "DELETE"))
                    .exclude(entity_type="")
                    .values("entity_type")
                    .annotate(n=Count("id"))
                    .order_by("-n")[:8],
                    "entity_type",
                ),
            },
            {
                "title": "Licences by status",
                "subtitle": "An expired licence is a pharmacy that cannot legally trade",
                "slices": _slices(licences.values("status").annotate(n=Count("id")), "status"),
            },
        ],
        "bars": [
            {
                "title": "Where the people are",
                "subtitle": "Active accounts per organization",
                "data": [
                    {"label": row["organization__name"] or "—", "value": row["n"]} for row in where
                ],
            },
            {
                "title": "Busiest accounts",
                "subtitle": "Recorded actions per person — an audit read, not a league table",
                "data": [
                    {"label": row["user__username"] or "—", "value": row["n"]} for row in busiest
                ],
            },
        ],
        "trend_series": ["Sign-ins", "Records changed"],
        "trend": [
            {
                "label": day.isoformat(),
                "values": [counts["sign_ins"], counts["changes"]],
            }
            for day, counts in sorted(by_day.items())
        ],
    }


#: module -> (permission required, builder). Same gate as the work queues, so a
#: person is never shown a chart about work they cannot see.
_MODULES: dict[str, tuple[str, Callable[[list[int]], dict[str, Any]]]] = {
    "retail": ("sale.create", _retail),
    "inventory": ("inventory.view", _inventory),
    "distribution": ("distribution.view", _distribution),
    "procurement": ("procurement.view", _procurement),
    "insurance": ("insurance.view", _insurance),
    "finance": ("finance.view", _finance),
    "people": ("employee.view", _people),
    "catalog": ("catalog.view", _catalog),
    "admin": ("organization.manage", _admin),
}


def insights_for(user: Any, module: str) -> dict[str, Any]:
    """Chart-ready figures for one module, or empty if this person may not see it."""
    from apps.iam.scoping import organizations_visible_to

    entry = _MODULES.get(module)
    if entry is None:
        return EMPTY.copy()
    permission, build = entry
    if not user.has_permission(permission):
        return EMPTY.copy()
    org_ids = list(organizations_visible_to(user).values_list("id", flat=True))
    # Normalise against the full shape so a builder only states what it has. The
    # frontend renders every module through one component, and that component is
    # entitled to assume the keys exist — a module without a trend should not
    # have to remember to say `"trend_series": []`.
    return {**EMPTY, **build(org_ids)}
