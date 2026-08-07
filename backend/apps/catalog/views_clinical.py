"""Catalog decision endpoints: safety screening, pricing, substitution.

These three answer questions asked *at the counter*, not questions about the
catalogue's contents — which is why they are their own views rather than more
CRUD on the master data.
"""

from __future__ import annotations

from typing import cast

from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog import dur, pricing, substitution
from apps.core.lookups import lookup_pk
from apps.iam.models import User


def _org(request: Request) -> int:
    raw = request.query_params.get("organization") or request.data.get("organization")
    if raw:
        return lookup_pk(raw)
    user = cast(User, request.user)
    if user.organization_id:
        return int(user.organization_id)
    raise ValidationError({"organization": "This query needs an organization."})


class ScreenBasketView(APIView):
    """Screen a basket for interactions, duplicate therapy and contraindications.

    Returns findings rather than a verdict. A pharmacist may dispense an
    interacting pair knowingly and often should; what they must not do is
    dispense it unknowingly.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        raw = request.data.get("products") or []
        if not raw:
            raise ValidationError({"products": "Give at least one product to screen."})
        conditions = request.data.get("conditions") or []
        return Response(
            dur.summary(
                product_ids=[lookup_pk(p) for p in raw],
                conditions=[str(c) for c in conditions],
            )
        )


class PriceBasketView(APIView):
    """Resolve what each line should be sold at, and say where the price came from."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        from apps.catalog.models import PriceList, Product

        org = _org(request)
        raw = request.data.get("lines") or []
        if not raw:
            raise ValidationError({"lines": "Give at least one line to price."})

        products = {
            p.pk: p
            for p in Product.objects.filter(pk__in=[lookup_pk(ln.get("product")) for ln in raw])
        }
        lines = []
        for entry in raw:
            product = products.get(lookup_pk(entry.get("product")))
            if product is None:
                raise ValidationError({"lines": f"Unknown product {entry.get('product')}."})
            lines.append({"product": product, "quantity": int(entry.get("quantity", 1))})

        return Response(
            {
                "organization": org,
                "lines": pricing.price_basket(
                    organization=org,
                    lines=lines,
                    list_type=request.data.get("list_type", PriceList.ListType.RETAIL),
                ),
            }
        )


class PricingCoverageView(APIView):
    """How much of what this pharmacy stocks is actually priced by a list."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        org = _org(request)
        return Response({"organization": org, **pricing.coverage(organization=org)})


class SubstitutesView(APIView):
    """What could be dispensed instead, of what is actually on the shelf."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        org = _org(request)
        raw = request.query_params.get("product")
        if not raw:
            raise ValidationError({"product": "Required."})
        return Response(substitution.suggest(product=lookup_pk(raw), organization=org))
