"""Insurance API — transport only; every state change lives in the services."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, cast

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView

from apps.core.lookups import lookup_pk
from apps.iam.models import User
from apps.iam.scoping import organizations_visible_to
from apps.insurance import claims as claim_service
from apps.insurance import eligibility as eligibility_service
from apps.insurance import reconciliation as recon_service
from apps.insurance.models import (
    Claim,
    InsuranceScheme,
    MemberPolicy,
    RemittanceAdvice,
    SchemeFormulary,
)
from apps.insurance.serializers import (
    ClaimSerializer,
    InsuranceSchemeSerializer,
    MemberPolicySerializer,
    RemittanceAdviceSerializer,
    SchemeFormularySerializer,
)


def _org(request: Request) -> int:
    raw = request.query_params.get("organization") or request.data.get("organization")
    if not raw:
        user = cast(User, request.user)
        if user.organization_id:
            return int(user.organization_id)
        raise ValidationError({"organization": "This query needs an organization."})
    return lookup_pk(raw)


class InsuranceSchemeViewSet(viewsets.ModelViewSet):
    serializer_class = InsuranceSchemeSerializer
    permission_classes = [IsAuthenticated]
    queryset = InsuranceScheme.objects.all()

    def get_queryset(self) -> QuerySet[InsuranceScheme]:
        user = cast(User, self.request.user)
        return InsuranceScheme.objects.filter(
            organization__in=organizations_visible_to(user)
        ).order_by("name")


class MemberPolicyViewSet(viewsets.ModelViewSet):
    serializer_class = MemberPolicySerializer
    permission_classes = [IsAuthenticated]
    queryset = MemberPolicy.objects.select_related("scheme").all()

    def get_queryset(self) -> QuerySet[MemberPolicy]:
        user = cast(User, self.request.user)
        qs = MemberPolicy.objects.select_related("scheme").filter(
            scheme__organization__in=organizations_visible_to(user)
        )
        scheme = self.request.query_params.get("scheme")
        if scheme:
            qs = qs.filter(scheme_id=lookup_pk(scheme))
        search = self.request.query_params.get("q")
        if search:
            qs = qs.filter(member_number__icontains=search)
        return qs


class SchemeFormularyViewSet(viewsets.ModelViewSet):
    serializer_class = SchemeFormularySerializer
    permission_classes = [IsAuthenticated]
    queryset = SchemeFormulary.objects.select_related("scheme", "product").all()

    def get_queryset(self) -> QuerySet[SchemeFormulary]:
        user = cast(User, self.request.user)
        qs = SchemeFormulary.objects.select_related("scheme", "product").filter(
            scheme__organization__in=organizations_visible_to(user)
        )
        scheme = self.request.query_params.get("scheme")
        if scheme:
            qs = qs.filter(scheme_id=lookup_pk(scheme))
        return qs


class EligibilityView(APIView):
    """Is this card good, and what does this basket split into?

    Read-only by design: a quote that created claims would leave one behind every
    time a customer changed their mind at the counter.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        member_number = request.data.get("member_number", "")
        if not member_number:
            raise ValidationError({"member_number": "Required."})

        raw_lines = request.data.get("lines") or []
        if not raw_lines:
            verdict = eligibility_service.check_eligibility(member_number=member_number)
            return Response(
                {
                    "eligible": verdict.is_eligible,
                    "reason": verdict.reason,
                    "policy": verdict.policy.pk if verdict.policy else None,
                    "member_name": verdict.policy.full_name if verdict.policy else "",
                    "scheme_name": verdict.scheme.name if verdict.scheme else "",
                    "copay_pct": str(verdict.copay_pct),
                }
            )

        from apps.catalog.models import Product

        products = {
            p.pk: p
            for p in Product.objects.filter(
                pk__in=[lookup_pk(ln.get("product")) for ln in raw_lines]
            )
        }
        lines = []
        for raw in raw_lines:
            product = products.get(lookup_pk(raw.get("product")))
            if product is None:
                raise ValidationError({"lines": f"Unknown product {raw.get('product')}."})
            lines.append(
                {
                    "product": product,
                    "quantity": Decimal(str(raw.get("quantity", 0))),
                    "unit_price": Decimal(str(raw.get("unit_price", "0"))),
                }
            )
        return Response(eligibility_service.quote(member_number=member_number, lines=lines))


class ClaimViewSet(viewsets.ReadOnlyModelViewSet):
    """Claims are built from sales and moved by the service — never edited directly."""

    serializer_class = ClaimSerializer
    permission_classes = [IsAuthenticated]
    queryset = Claim.objects.select_related("scheme", "policy", "sale").all()

    def get_queryset(self) -> QuerySet[Claim]:
        user = cast(User, self.request.user)
        qs = (
            Claim.objects.select_related("scheme", "policy", "sale")
            .prefetch_related("lines")
            .filter(organization__in=organizations_visible_to(user))
        )
        status = self.request.query_params.get("status")
        if status:
            valid = {c.value for c in Claim.Status}
            if status not in valid:
                raise ValidationError({"status": f"Must be one of {sorted(valid)}."})
            qs = qs.filter(status=status)
        scheme = self.request.query_params.get("scheme")
        if scheme:
            qs = qs.filter(scheme_id=lookup_pk(scheme))
        return qs

    @action(detail=False, methods=["post"])
    def build(self, request: Request) -> Response:
        """Raise a draft claim for a completed insured sale."""
        from apps.retail.models import Sale

        sale = get_object_or_404(Sale, pk=lookup_pk(request.data.get("sale")))
        policy = get_object_or_404(MemberPolicy, pk=lookup_pk(request.data.get("policy")))
        try:
            outcome = claim_service.build_from_sale(
                sale=sale, policy=policy, user=cast(User, request.user)
            )
        except claim_service.ClaimError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(
            {
                **ClaimSerializer(outcome.claim).data,
                "lines_built": outcome.lines,
            },
            status=201,
        )

    @action(detail=True, methods=["post"])
    def submit(self, request: Request, pk: str | None = None) -> Response:
        try:
            claim = claim_service.submit(claim=self.get_object(), user=cast(User, request.user))
        except claim_service.ClaimError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(ClaimSerializer(claim).data)

    @action(detail=True, methods=["post"])
    def adjudicate(self, request: Request, pk: str | None = None) -> Response:
        raw = request.data.get("paid_amount")
        try:
            claim = claim_service.adjudicate(
                claim=self.get_object(),
                accepted=bool(request.data.get("accepted", True)),
                paid_amount=Decimal(str(raw)) if raw is not None else None,
                reason=request.data.get("reason", ""),
                notes=request.data.get("notes", ""),
                user=cast(User, request.user),
            )
        except claim_service.ClaimError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(ClaimSerializer(claim).data)

    @action(detail=True, methods=["post"])
    def reverse_claim(self, request: Request, pk: str | None = None) -> Response:
        try:
            claim = claim_service.reverse(
                claim=self.get_object(),
                reason=request.data.get("reason", ""),
                user=cast(User, request.user),
            )
        except claim_service.ClaimError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(ClaimSerializer(claim).data)

    @action(detail=False, methods=["get"])
    def queue(self, request: Request) -> Response:
        """Claims needing action, closest to their window deadline first."""
        org = _org(request)
        return Response({"organization": org, "rows": claim_service.work_queue(organization=org)})

    @action(detail=False, methods=["get"])
    def exposure(self, request: Request) -> Response:
        """What each payer owes, aged."""
        org = _org(request)
        return Response(
            {"organization": org, "rows": claim_service.insurer_exposure(organization=org)}
        )


class RemittanceAdviceViewSet(viewsets.ModelViewSet):
    serializer_class = RemittanceAdviceSerializer
    permission_classes = [IsAuthenticated]
    queryset = RemittanceAdvice.objects.select_related("scheme").all()

    def get_queryset(self) -> QuerySet[RemittanceAdvice]:
        user = cast(User, self.request.user)
        return (
            RemittanceAdvice.objects.select_related("scheme")
            .prefetch_related("lines__claim")
            .filter(organization__in=organizations_visible_to(user))
        )

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        serializer.save()

    @action(detail=True, methods=["post"])
    def add_line(self, request: Request, pk: str | None = None) -> Response:
        claim = get_object_or_404(Claim, pk=lookup_pk(request.data.get("claim")))
        try:
            line = recon_service.add_line(
                advice=self.get_object(),
                claim=claim,
                amount_paid=Decimal(str(request.data.get("amount_paid", "0"))),
                denial_reason=request.data.get("denial_reason", ""),
            )
        except recon_service.ReconciliationError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(
            {"line": line.pk, "claim": claim.pk, "amount_paid": str(line.amount_paid)}, status=201
        )

    @action(detail=True, methods=["post"])
    def post_advice(self, request: Request, pk: str | None = None) -> Response:
        try:
            outcome = recon_service.post(advice=self.get_object(), user=cast(User, request.user))
        except recon_service.ReconciliationError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(
            {
                **RemittanceAdviceSerializer(outcome.advice).data,
                "claims_settled": outcome.claims_settled,
                "total_posted": str(outcome.total_posted),
                "short_paid": str(outcome.short_paid),
            }
        )

    @action(detail=True, methods=["get"])
    def suggestions(self, request: Request, pk: str | None = None) -> Response:
        return Response({"rows": recon_service.suggest_matches(advice=self.get_object())})


class InsuranceOverviewView(APIView):
    """What needs attention across schemes, claims and reconciliation."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        org = _org(request)
        return Response(
            {
                "organization": org,
                "claims": claim_service.summary(organization=org),
                "reconciliation": recon_service.summary(organization=org),
                "exposure": claim_service.insurer_exposure(organization=org),
            }
        )
