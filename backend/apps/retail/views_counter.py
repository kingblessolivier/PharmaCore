"""Counter endpoints the till needs: scan, discount, and billing a clinical service.

Kept separate from the CRUD viewsets because these are *actions at the counter*
rather than record management, and they are the ones that have to be fast — a
scan resolves on every keystroke burst from the scanner.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, cast

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.catalog.models import Product
from apps.core.lookups import lookup_pk
from apps.iam.models import Organization, User
from apps.iam.permissions import HasPermission
from apps.iam.scoping import organizations_visible_to
from apps.retail import counter
from apps.retail import tax as vat
from apps.retail.counter import (
    active_promotions,
    apply_promotion,
    bill_clinical_service,
    clear_promotion,
    resolve_barcode,
)
from apps.retail.lines import build_line
from apps.retail.models import ClinicalServiceRecord, Sale

#: Organization types that do not serve the public over a counter. A depot
#: moves stock on B2B orders and a head office does not hold stock at all.
_NOT_A_SHOP = ("DEPOT", "HQ", "DISTRIBUTOR")


def _org(request: Request) -> Organization:
    user = cast(User, request.user)
    raw = request.query_params.get("organization") or request.data.get("organization")
    if raw and str(raw).isdigit():
        organization = Organization.objects.filter(pk=int(raw)).first()
    else:
        organization = user.organization
    if organization is None:
        raise ValidationError("An 'organization' is required.")
    if not (
        user.is_superuser
        or user.has_role("SYS_ADMIN")
        or organization in organizations_visible_to(user)
    ):
        raise PermissionDenied("You may not trade on behalf of that pharmacy.")

    # A depot is not a shop.
    #
    # The counter was gated on the `sale.create` permission alone, never on what
    # kind of organization was trading — so a depot with one permissive role got
    # a till and could ring up a walk-in customer. That is not a UI slip: a depot
    # sells cases to pharmacies on account and books wholesale revenue and trade
    # receivables, while a shop sells singles to the public for cash and books
    # retail revenue, VAT at the till and a drawer to reconcile. Letting one post
    # the other's transactions puts both sets of books wrong at once.
    if organization.type in _NOT_A_SHOP:
        raise PermissionDenied(
            f"{organization.name} is a {organization.get_type_display().lower()}, "
            "not a retail pharmacy. Bulk stock leaves a depot on a B2B order, "
            "not over a counter."
        )
    return organization


def _sale(request: Request, organization: Organization) -> Sale:
    sale = Sale.objects.filter(
        pk=lookup_pk(request.data.get("sale")), organization=organization
    ).first()
    if sale is None:
        raise ValidationError("A valid open 'sale' is required.")
    return sale


def _scan_payload(organization: Organization, result: counter.ScanResult) -> dict[str, Any]:
    """Everything the till needs to add one line, in one round trip.

    Shared by ``scan`` and ``search`` so the two entry points can never disagree
    about what a product costs or whether it is in stock.
    """
    from django.db.models import Sum

    from apps.catalog import pricing, substitution
    from apps.inventory.models import InventoryBatch

    resolved = pricing.resolve(product=result.product, organization=organization)
    on_hand = (
        InventoryBatch.objects.filter(organization=organization, product=result.product).aggregate(
            total=Sum("quantity_available")
        )["total"]
        or 0
    )
    return {
        "found": True,
        "code": result.barcode,
        "product": result.product.pk,
        "label": f"{result.product.generic_name} {result.product.strength}".strip(),
        # Scanning a carton must add the carton, not one tablet.
        "units": result.units,
        "packaging_level": result.packaging_level,
        # Resolved through any price list in force, falling back to the pharmacy's
        # own price. Reading `retail_price` alone meant a promotional list changed
        # nothing at the till.
        "unit_price": str(resolved.unit_price) if resolved.unit_price else "",
        "price_source": resolved.source,
        "price_list_name": resolved.price_list_name,
        "on_hand": int(on_hand),
        # An empty shelf is exactly when the catalogue is most useful.
        "substitutes": (
            substitution.suggest(product=result.product, organization=organization)
            if on_hand <= 0
            else None
        ),
        "requires_prescription": result.product.requires_prescription,
        "is_controlled": result.product.is_controlled_substance,
    }


def _sale_units(product: Any, base_price: Any) -> list[dict[str, Any]]:
    """The levels this product may be sold in, cheapest-per-base first.

    A unit priced in its own right keeps that price; otherwise the base price
    scales, which is what a pharmacy that has not priced packs separately means
    by "a box of a hundred".
    """
    from apps.retail.lines import price_for

    rows = []
    for unit in sorted(product.units.all(), key=lambda u: u.level):
        rows.append(
            {
                "id": unit.pk,
                "code": unit.code,
                "label": unit.name or unit.get_code_display(),
                "factor_to_base": str(unit.factor_to_base),
                "is_base": unit.is_base,
                "is_default": unit.is_sale_default,
                "unit_price": str(price_for(unit=unit, base_price=Decimal(str(base_price or 0)))),
            }
        )
    return rows


class CounterViewSet(viewsets.ViewSet):
    """Actions performed at the till."""

    permission_classes = [IsAuthenticated, HasPermission.require("sale.create")]

    @action(detail=False, methods=["get"])
    def scan(self, request: Request) -> Response:
        """Resolve a scanned barcode to a product and the quantity it represents.

        A scanner is a keyboard that types fast and presses Enter, so this has to
        answer in one round trip with everything the till needs to add a line.
        """
        organization = _org(request)
        code = request.query_params.get("code", "")
        result = resolve_barcode(organization=organization, code=code)
        if result is None:
            return Response(
                {"found": False, "code": code, "detail": f"No product matches {code!r}."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(_scan_payload(organization, result))

    @action(detail=False, methods=["get"])
    def search(self, request: Request) -> Response:
        """Find a product by typing its name, not by scanning it.

        The till could only resolve an exact barcode, so in a pharmacy without
        barcode labelling — which is most of them here — nothing could be sold at
        all. This is the other half of the counter's input, not a fallback.

        Returns an ``exact`` hit when the input came off a scanner, so the till
        can add the line without a second round trip and the scanner path is
        unchanged. Otherwise it returns ranked candidates for the cashier to pick.
        """
        organization = _org(request)
        query = (request.query_params.get("q") or request.query_params.get("code") or "").strip()

        exact = None
        if counter.looks_like_a_barcode(query):
            hit = resolve_barcode(organization=organization, code=query)
            if hit is not None:
                exact = _scan_payload(organization, hit)

        matches = counter.search_products(organization=organization, query=query)
        return Response(
            {
                "query": query,
                "exact": exact,
                "count": len(matches),
                "results": [
                    {
                        "product": m.product.pk,
                        "label": f"{m.product.generic_name} {m.product.strength}".strip(),
                        "brand_name": m.product.brand_name,
                        "dosage_form": m.product.dosage_form,
                        "pack_size": m.product.pack_size,
                        # The packaging levels this medicine may be sold in, so
                        # the counter can offer a box, a strip or a single
                        # tablet instead of guessing which the number meant.
                        "sale_units": _sale_units(m.product, m.unit_price),
                        "divisibility": m.product.divisibility,
                        "split_note": m.product.split_note,
                        "unit_price": str(m.unit_price) if m.unit_price else "",
                        "price_source": m.price_source,
                        "on_hand": m.on_hand,
                        "matched_on": m.matched_on,
                        "requires_prescription": m.product.requires_prescription,
                        "is_controlled": m.product.is_controlled_substance,
                    }
                    for m in matches
                ],
            }
        )

    @action(detail=False, methods=["get"], url_path="promotions")
    def promotions(self, request: Request) -> Response:
        """Coupons in force today at *this* pharmacy, so the till can offer them."""
        org = _org(request)
        return Response(
            [
                {
                    "code": p.code,
                    "name": p.name,
                    "promo_type": p.promo_type,
                    "discount_value": str(p.discount_value),
                    "min_spend": str(p.min_spend),
                    "valid_until": p.valid_until,
                    "remaining": (
                        max(p.max_redemptions - p.times_redeemed, 0) if p.max_redemptions else None
                    ),
                }
                for p in active_promotions(organization=org)
            ]
        )

    @action(detail=False, methods=["post"], url_path="apply-promotion")
    def apply_promotion_action(self, request: Request) -> Response:
        """Apply a coupon to an open basket, or say plainly why it does not apply."""
        organization = _org(request)
        sale = _sale(request, organization)
        try:
            outcome = apply_promotion(sale=sale, code=str(request.data.get("code", "")))
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        sale.refresh_from_db()
        return Response(
            {
                "applied": outcome.applied,
                "reason": outcome.reason,
                "discount": str(outcome.discount),
                "gross_total": str(sale.gross_total),
                "total": str(sale.total),
            }
        )

    @action(detail=False, methods=["post"], url_path="clear-promotion")
    def clear_promotion_action(self, request: Request) -> Response:
        organization = _org(request)
        sale = clear_promotion(sale=_sale(request, organization))
        return Response({"total": str(sale.total), "gross_total": str(sale.gross_total)})

    @action(detail=False, methods=["post"], url_path="bill-clinical-service")
    def bill_clinical(self, request: Request) -> Response:
        """Take payment for a clinical service and post it to the ledger.

        The fee used to be recorded on the encounter and never banked.
        """
        organization = _org(request)
        record = ClinicalServiceRecord.objects.filter(
            pk=lookup_pk(request.data.get("record")), organization=organization
        ).first()
        if record is None:
            raise ValidationError("A valid clinical 'record' is required.")
        billed = bill_clinical_service(record=record, user=cast(User, request.user))
        return Response(
            {"id": billed.pk, "is_paid": billed.is_paid, "fee": str(billed.fee_charged)}
        )


def counter_urls() -> Any:
    return CounterViewSet


class OfflineSyncViewSet(viewsets.ViewSet):
    """Replaying sales rung up while the connection was down.

    `docs/19-platform-architecture-decisions.md` §2 calls for an offline-first
    counter and nothing implemented it, so a dropped connection stopped the
    pharmacy trading. The till now completes the sale locally and queues it; this
    is where the queue drains.

    The whole sale arrives in one request — lines, tenders, dispensing details —
    because offline the basket was never on the server to begin with.
    """

    permission_classes = [IsAuthenticated, HasPermission.require("sale.create")]

    @action(detail=False, methods=["post"], url_path="sync")
    def sync(self, request: Request) -> Response:
        """Replay one queued sale. Safe to call repeatedly with the same key."""
        from decimal import Decimal

        from apps.retail.services import complete_sale

        organization = _org(request)
        data = request.data
        reference = str(data.get("client_reference", "")).strip()
        if not reference:
            raise ValidationError(
                "A 'client_reference' is required — without it a replay cannot be "
                "told apart from a second sale."
            )

        # Idempotency, but only for a sale that actually went through.
        #
        # Short-circuiting on *any* existing row is a trap: a replay that failed
        # (no pharmacist on shift, stock gone) leaves the row holding the key, so
        # every later retry reports success for a sale that never completed. The
        # till then drops it from its queue and the sale is silently lost — worse
        # than the double-sell this guard exists to prevent.
        existing = Sale.objects.filter(
            organization=organization, client_reference=reference
        ).first()
        if existing is not None and existing.status == Sale.Status.COMPLETED:
            return Response(
                {"sale": existing.pk, "sale_number": existing.sale_number, "replayed": True}
            )

        lines = data.get("items") or []
        if not lines:
            raise ValidationError("A queued sale must carry its lines.")

        if existing is not None:
            # A previous attempt got as far as creating the basket. Reuse it
            # rather than creating a second one under the same key.
            sale = existing
            sale.items.all().delete()
        else:
            sale = Sale.objects.create(
                organization=organization,
                client_reference=reference,
                status=Sale.Status.OPEN,
                cashier=cast(User, request.user),
            )
            # `sale_number` is unique with a blank default, so a second
            # unnumbered sale collides on the constraint. The counter assigns it
            # right after create for the same reason SaleViewSet does — the
            # number needs the primary key to exist first.
            sale.sale_number = f"SALE-{sale.pk:06d}"
            sale.save(update_fields=["sale_number"])
        for line in lines:
            build_line(
                sale=sale,
                product=Product.objects.get(pk=line["product"]),
                quantity=line["quantity"],
                unit_code=line.get("unit"),
                base_price=Decimal(str(line["unit_price"])),
                # The till may not name its own VAT rate. It used to take
                # whatever the client sent, so a rate could be posted by anyone
                # who could reach the endpoint, and an unregistered pharmacy
                # charged 18% because the screen had been built assuming it.
                tax_rate=vat.rate_for(
                    product=Product.objects.get(pk=line["product"]), organization=organization
                ),
            )

        try:
            complete_sale(
                sale=sale,
                payments=data.get("payments") or [],
                user=cast(User, request.user),
                dispensing=data.get("dispensing"),
            )
        except Exception as exc:
            # The basket is kept, still OPEN, so the queue entry can be reviewed
            # and retried once the reason is fixed — a sale that cannot be
            # replayed is money that left the shelf and needs a human. The lookup
            # above deliberately does not treat this row as a completed replay.
            sale.status = Sale.Status.OPEN
            sale.save(update_fields=["status", "updated_at"])
            raise ValidationError(
                {
                    "detail": str(exc),
                    "sale": str(sale.pk),
                    "client_reference": reference,
                    # A real boolean, not "true": the till branches on this to decide
                    # whether to keep the sale queued. DRF's stub types error details
                    # as string-ish, which is narrower than what it actually accepts.
                    "retryable": True,  # type: ignore[dict-item]
                }
            ) from exc

        sale.refresh_from_db()
        return Response(
            {"sale": sale.pk, "sale_number": sale.sale_number, "replayed": False},
            status=status.HTTP_201_CREATED,
        )
