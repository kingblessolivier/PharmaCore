"""Procurement API — supplier master, requisitions, RFQs, purchase orders,
imports & landed cost, goods receipts, and supplier invoices (3-way match).

Every queryset is tenant-scoped through ``organizations_visible_to`` (HQ sees its
branches, a branch sees itself); every write is audited; every state transition
goes through ``apps.procurement.services`` so the API can never take a shortcut a
management command couldn't.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, cast

from django.db.models import Count, Q, QuerySet
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView

from apps.catalog.models import Supplier
from apps.core.lookups import lookup_pk
from apps.iam.audit import record_audit
from apps.iam.models import Organization, User
from apps.iam.scoping import organizations_visible_to
from apps.procurement import services
from apps.procurement.models import (
    GoodsReceipt,
    ImportConsignment,
    LandedCostComponent,
    NumberSequence,
    PurchaseOrder,
    PurchaseRequisition,
    RequestForQuotation,
    SupplierEvaluation,
    SupplierInvoice,
    SupplierLicence,
    SupplierNote,
    SupplierPriceAgreement,
    SupplierProfile,
    SupplierQuote,
)
from apps.procurement.permissions import (
    CanHandleInvoices,
    CanManageProcurement,
    CanReceiveGoods,
    CanViewProcurement,
)
from apps.procurement.serializers import (
    GoodsReceiptSerializer,
    ImportConsignmentSerializer,
    LandedCostComponentSerializer,
    PurchaseOrderSerializer,
    PurchaseRequisitionSerializer,
    RequestForQuotationSerializer,
    SupplierEvaluationSerializer,
    SupplierInvoiceSerializer,
    SupplierLicenceSerializer,
    SupplierNoteSerializer,
    SupplierPriceAgreementSerializer,
    SupplierProfileSerializer,
    SupplierQuoteSerializer,
)

_WRITE = {"create", "update", "partial_update", "destroy"}


def _decimal(raw: Any, field: str) -> Decimal:
    try:
        return Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError({field: "A number is required."}) from exc


def _parse_date(raw: Any, field: str, default: date | None = None) -> date:
    if raw in (None, ""):
        if default is not None:
            return default
        raise ValidationError({field: "A date (YYYY-MM-DD) is required."})
    try:
        return date.fromisoformat(str(raw))
    except ValueError as exc:
        raise ValidationError({field: "Use the YYYY-MM-DD format."}) from exc


class _AuditedViewSet(viewsets.ModelViewSet):
    """Shared scaffolding: permission split, org guard, audit trail."""

    entity_type = "procurement_object"
    manage_permission: type = CanManageProcurement
    owner_field = ""  # set to a user FK name to stamp the creator
    # Documents are numbered the moment they are created, not when they are
    # submitted — a clerk needs something to call the draft they are working on.
    number_field = ""
    number_kind = ""

    permission_classes = [IsAuthenticated, CanViewProcurement]

    def get_permissions(self) -> list[Any]:
        if self.action in _WRITE or self.action in getattr(self, "manage_actions", ()):
            return [IsAuthenticated(), self.manage_permission()]
        return [IsAuthenticated(), CanViewProcurement()]

    # -- scoping ---------------------------------------------------------
    def visible_orgs(self) -> QuerySet[Organization]:
        return organizations_visible_to(cast(User, self.request.user))

    def guard_org(self, organization: Organization | None) -> None:
        if organization is None:
            return
        if not self.visible_orgs().filter(pk=organization.pk).exists():
            raise PermissionDenied("You cannot act for that organization.")

    # -- audit -----------------------------------------------------------
    def _audit(self, verb: str, obj: Any) -> None:
        record_audit(
            action=verb,
            user=cast(User, self.request.user),
            organization=getattr(obj, "organization", None),
            entity_type=self.entity_type,
            entity_id=str(obj.pk),
            request=self.request,
        )

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        organization = serializer.validated_data.get("organization")
        self.guard_org(organization)
        extra: dict[str, Any] = {}
        if self.owner_field:
            extra[self.owner_field] = cast(User, self.request.user)
        if self.number_field and self.number_kind and organization is not None:
            extra[self.number_field] = services.next_document_number(organization, self.number_kind)
        obj = serializer.save(**extra)
        self._audit("CREATE", obj)

    def perform_update(self, serializer: BaseSerializer[Any]) -> None:
        self.guard_org(serializer.validated_data.get("organization"))
        self._audit("UPDATE", serializer.save())

    def perform_destroy(self, instance: Any) -> None:
        self._audit("DELETE", instance)
        instance.delete()


# ---------------------------------------------------------------------------
# Supplier master
# ---------------------------------------------------------------------------


class SupplierProfileViewSet(_AuditedViewSet):
    """Supplier master: standing, trade terms, banking, scorecard, licences."""

    entity_type = "supplier_profile"
    serializer_class = SupplierProfileSerializer
    queryset = SupplierProfile.objects.select_related("supplier").all()
    manage_actions = ("set_standing", "score", "ensure")

    def get_queryset(self) -> QuerySet[SupplierProfile]:
        qs = SupplierProfile.objects.select_related("supplier").prefetch_related(
            "supplier__procurement_licences"
        )
        standing = self.request.query_params.get("standing")
        if standing:
            qs = qs.filter(standing=standing.upper())
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(Q(supplier__name__icontains=search) | Q(trading_name__icontains=search))
        return qs

    @action(detail=False, methods=["post"])
    def ensure(self, request: Request) -> Response:
        """Create the procurement profile for a catalog supplier that lacks one."""
        supplier = Supplier.objects.filter(pk=lookup_pk(request.data.get("supplier"))).first()
        if supplier is None:
            raise ValidationError({"supplier": "Unknown supplier."})
        profile = services.get_or_create_profile(supplier)
        return Response(SupplierProfileSerializer(profile).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def set_standing(self, request: Request, pk: str | None = None) -> Response:
        profile = self.get_object()
        try:
            services.set_supplier_standing(
                profile=profile,
                standing=str(request.data.get("standing", "")).upper(),
                reason=str(request.data.get("reason", "")),
                user=cast(User, request.user),
            )
        except services.ProcurementError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(SupplierProfileSerializer(profile).data)

    @action(detail=True, methods=["post"])
    def score(self, request: Request, pk: str | None = None) -> Response:
        """Recompute the scorecard from actual receipts over a period."""
        profile = self.get_object()
        org = Organization.objects.filter(pk=lookup_pk(request.data.get("organization"))).first()
        if org is None:
            org = self.visible_orgs().first()
        if org is None:
            raise ValidationError({"organization": "An organization is required."})
        self.guard_org(org)
        today = timezone.localdate()
        evaluation = services.refresh_supplier_scores(
            supplier=profile.supplier,
            organization=org,
            period_start=_parse_date(
                request.data.get("period_start"), "period_start", today - timedelta(days=180)
            ),
            period_end=_parse_date(request.data.get("period_end"), "period_end", today),
            user=cast(User, request.user),
            price_competitiveness=(
                _decimal(request.data["price_competitiveness"], "price_competitiveness")
                if request.data.get("price_competitiveness") not in (None, "")
                else None
            ),
            responsiveness=(
                _decimal(request.data["responsiveness"], "responsiveness")
                if request.data.get("responsiveness") not in (None, "")
                else None
            ),
            comments=str(request.data.get("comments", "")),
        )
        return Response(
            {
                "evaluation": SupplierEvaluationSerializer(evaluation).data,
                "profile": SupplierProfileSerializer(profile).data,
            }
        )


class SupplierLicenceViewSet(_AuditedViewSet):
    entity_type = "supplier_licence"
    serializer_class = SupplierLicenceSerializer
    queryset = SupplierLicence.objects.select_related("supplier").all()
    manage_actions = ("verify",)

    def get_queryset(self) -> QuerySet[SupplierLicence]:
        qs = SupplierLicence.objects.select_related("supplier", "verified_by")
        supplier = self.request.query_params.get("supplier")
        if supplier:
            qs = qs.filter(supplier_id=supplier)
        if self.request.query_params.get("expiring") == "1":
            qs = qs.filter(expires_on__lte=timezone.localdate() + timedelta(days=90))
        return qs

    @action(detail=True, methods=["post"])
    def verify(self, request: Request, pk: str | None = None) -> Response:
        from django.utils import timezone

        licence = self.get_object()
        licence.is_verified = bool(request.data.get("is_verified", True))
        licence.verified_by = cast(User, request.user)
        licence.verified_at = timezone.now()
        licence.save(update_fields=["is_verified", "verified_by", "verified_at"])
        self._audit("SUPPLIER_LICENCE_VERIFY", licence)
        return Response(SupplierLicenceSerializer(licence).data)


class SupplierPriceAgreementViewSet(_AuditedViewSet):
    entity_type = "supplier_price_agreement"
    serializer_class = SupplierPriceAgreementSerializer
    queryset = SupplierPriceAgreement.objects.select_related("supplier", "product").all()

    def get_queryset(self) -> QuerySet[SupplierPriceAgreement]:
        qs = SupplierPriceAgreement.objects.select_related("supplier", "product", "organization")
        supplier = self.request.query_params.get("supplier")
        if supplier:
            qs = qs.filter(supplier_id=supplier)
        product = self.request.query_params.get("product")
        if product:
            qs = qs.filter(product_id=product)
        return qs


class SupplierEvaluationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SupplierEvaluationSerializer
    queryset = SupplierEvaluation.objects.select_related("supplier", "rated_by").all()
    permission_classes = [IsAuthenticated, CanViewProcurement]

    def get_queryset(self) -> QuerySet[SupplierEvaluation]:
        qs = SupplierEvaluation.objects.select_related("supplier", "rated_by").filter(
            organization__in=organizations_visible_to(cast(User, self.request.user))
        )
        supplier = self.request.query_params.get("supplier")
        return qs.filter(supplier_id=supplier) if supplier else qs


# ---------------------------------------------------------------------------
# Requisitions
# ---------------------------------------------------------------------------


class PurchaseRequisitionViewSet(_AuditedViewSet):
    entity_type = "purchase_requisition"
    serializer_class = PurchaseRequisitionSerializer
    queryset = PurchaseRequisition.objects.all()
    owner_field = "requested_by"
    number_field = "requisition_number"
    number_kind = NumberSequence.Kind.REQUISITION
    manage_actions = ("submit", "consolidate")

    def get_queryset(self) -> QuerySet[PurchaseRequisition]:
        qs = (
            PurchaseRequisition.objects.filter(organization__in=self.visible_orgs())
            .select_related("organization", "requested_by", "approved_by", "preferred_supplier")
            .prefetch_related("lines__product")
        )
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param.upper())
        org = self.request.query_params.get("organization")
        if org:
            qs = qs.filter(organization_id=org)
        services.sync_approval_outcomes(
            resource_type=services.RES_REQUISITION,
            objects=list(qs),
            pending_status=PurchaseRequisition.Status.SUBMITTED,
            rejected_status=PurchaseRequisition.Status.REJECTED,
        )
        return qs

    @action(detail=True, methods=["post"])
    def submit(self, request: Request, pk: str | None = None) -> Response:
        requisition = self.get_object()
        try:
            approval = services.submit_requisition(
                requisition=requisition, user=cast(User, request.user)
            )
        except services.ProcurementError as exc:
            raise ValidationError(str(exc)) from exc
        requisition.refresh_from_db()
        return Response(
            {
                "requisition": PurchaseRequisitionSerializer(requisition).data,
                "approval_id": approval.pk,
                "message": "Sent to the approvals inbox. It cannot be approved by you.",
            }
        )

    @action(detail=False, methods=["post"])
    def consolidate(self, request: Request) -> Response:
        """HQ: merge several approved requisitions into one supplier PO."""
        org = Organization.objects.filter(pk=lookup_pk(request.data.get("organization"))).first()
        if org is None:
            raise ValidationError({"organization": "An organization is required."})
        self.guard_org(org)
        supplier = Supplier.objects.filter(pk=lookup_pk(request.data.get("supplier"))).first()
        if supplier is None:
            raise ValidationError({"supplier": "A supplier is required."})
        ids = request.data.get("requisitions") or []
        requisitions = list(
            PurchaseRequisition.objects.filter(
                pk__in=ids, organization__in=self.visible_orgs()
            ).prefetch_related("lines")
        )
        if len(requisitions) != len(ids):
            raise ValidationError({"requisitions": "One or more requisitions are not visible."})
        deliver_to = Organization.objects.filter(
            pk=lookup_pk(request.data.get("deliver_to"))
        ).first()
        try:
            order = services.consolidate_requisitions(
                organization=org,
                supplier=supplier,
                requisitions=requisitions,
                user=cast(User, request.user),
                expected_delivery=(
                    _parse_date(request.data.get("expected_delivery"), "expected_delivery")
                    if request.data.get("expected_delivery")
                    else None
                ),
                currency=request.data.get("currency") or None,
                exchange_rate=(
                    _decimal(request.data["exchange_rate"], "exchange_rate")
                    if request.data.get("exchange_rate")
                    else None
                ),
                is_import=bool(request.data.get("is_import")),
                deliver_to=deliver_to,
            )
        except services.ProcurementError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(PurchaseOrderSerializer(order).data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# RFQ & quotes
# ---------------------------------------------------------------------------


class RequestForQuotationViewSet(_AuditedViewSet):
    entity_type = "rfq"
    serializer_class = RequestForQuotationSerializer
    queryset = RequestForQuotation.objects.all()
    owner_field = "created_by"
    number_field = "rfq_number"
    number_kind = NumberSequence.Kind.RFQ
    manage_actions = ("send",)

    def get_queryset(self) -> QuerySet[RequestForQuotation]:
        qs = (
            RequestForQuotation.objects.filter(organization__in=self.visible_orgs())
            .select_related("organization", "created_by")
            .prefetch_related("lines__product", "quotes__supplier", "quotes__lines__product")
        )
        status_param = self.request.query_params.get("status")
        return qs.filter(status=status_param.upper()) if status_param else qs

    @action(detail=True, methods=["post"])
    def send(self, request: Request, pk: str | None = None) -> Response:
        rfq = self.get_object()
        try:
            services.send_rfq(rfq=rfq, user=cast(User, request.user))
        except services.ProcurementError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(RequestForQuotationSerializer(rfq).data)

    @action(detail=True, methods=["get"])
    def comparison(self, request: Request, pk: str | None = None) -> Response:
        """The quote-comparison table: totals in RWF, best price flagged."""
        return Response(services.compare_quotes(self.get_object()))


class SupplierQuoteViewSet(_AuditedViewSet):
    entity_type = "supplier_quote"
    serializer_class = SupplierQuoteSerializer
    queryset = SupplierQuote.objects.all()
    owner_field = "recorded_by"
    manage_actions = ("award", "shortlist")

    def get_queryset(self) -> QuerySet[SupplierQuote]:
        qs = (
            SupplierQuote.objects.filter(rfq__organization__in=self.visible_orgs())
            .select_related("supplier", "rfq")
            .prefetch_related("lines__product")
        )
        rfq = self.request.query_params.get("rfq")
        return qs.filter(rfq_id=lookup_pk(rfq)) if rfq else qs

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        rfq = serializer.validated_data.get("rfq")
        if rfq is not None:
            self.guard_org(rfq.organization)
        obj = serializer.save(recorded_by=cast(User, self.request.user))
        record_audit(
            action="CREATE",
            user=cast(User, self.request.user),
            organization=obj.rfq.organization,
            entity_type=self.entity_type,
            entity_id=str(obj.pk),
            request=self.request,
        )

    @action(detail=True, methods=["post"])
    def shortlist(self, request: Request, pk: str | None = None) -> Response:
        quote = self.get_object()
        quote.status = SupplierQuote.Status.SHORTLISTED
        quote.save(update_fields=["status"])
        return Response(SupplierQuoteSerializer(quote).data)

    @action(detail=True, methods=["post"])
    def award(self, request: Request, pk: str | None = None) -> Response:
        quote = self.get_object()
        try:
            order = services.award_quote(quote=quote, user=cast(User, request.user))
        except services.ProcurementError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(PurchaseOrderSerializer(order).data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Purchase orders
# ---------------------------------------------------------------------------


class PurchaseOrderViewSet(_AuditedViewSet):
    entity_type = "purchase_order"
    serializer_class = PurchaseOrderSerializer
    queryset = PurchaseOrder.objects.all()
    owner_field = "created_by"
    number_field = "po_number"
    number_kind = NumberSequence.Kind.PURCHASE_ORDER
    manage_actions = ("submit", "send", "cancel", "close", "start_receipt")

    def get_permissions(self) -> list[Any]:
        if self.action == "start_receipt":
            return [IsAuthenticated(), CanReceiveGoods()]
        return super().get_permissions()

    def get_queryset(self) -> QuerySet[PurchaseOrder]:
        qs = (
            PurchaseOrder.objects.filter(organization__in=self.visible_orgs())
            .select_related("organization", "supplier", "created_by", "approved_by", "deliver_to")
            .prefetch_related("lines__product", "receipts")
        )
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param.upper())
        supplier = self.request.query_params.get("supplier")
        if supplier:
            qs = qs.filter(supplier_id=supplier)
        org = self.request.query_params.get("organization")
        if org:
            qs = qs.filter(organization_id=org)
        if self.request.query_params.get("receivable") == "1":
            qs = qs.filter(status__in=list(PurchaseOrder.RECEIVABLE))
        services.sync_approval_outcomes(
            resource_type=services.RES_PURCHASE_ORDER,
            objects=list(qs),
            pending_status=PurchaseOrder.Status.PENDING_APPROVAL,
            rejected_status=PurchaseOrder.Status.DRAFT,
        )
        return qs

    @action(detail=True, methods=["post"])
    def submit(self, request: Request, pk: str | None = None) -> Response:
        order = self.get_object()
        try:
            approval = services.submit_order(order=order, user=cast(User, request.user))
        except services.ProcurementError as exc:
            raise ValidationError(str(exc)) from exc
        order.refresh_from_db()
        return Response(
            {
                "order": PurchaseOrderSerializer(order).data,
                "approval_id": approval.pk,
                "message": "Sent to the approvals inbox — you cannot approve your own order.",
            }
        )

    @action(detail=True, methods=["post"])
    def send(self, request: Request, pk: str | None = None) -> Response:
        order = self.get_object()
        try:
            document = services.send_order(
                order=order,
                user=cast(User, request.user),
                method=str(request.data.get("method", "EMAIL")).upper(),
            )
        except services.ProcurementError as exc:
            raise ValidationError(str(exc)) from exc
        order.refresh_from_db()
        return Response(
            {
                "order": PurchaseOrderSerializer(order).data,
                "document_number": document.doc_number,
                "document_id": document.pk,
            }
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request: Request, pk: str | None = None) -> Response:
        order = self.get_object()
        try:
            services.cancel_order(
                order=order,
                user=cast(User, request.user),
                reason=str(request.data.get("reason", "")),
            )
        except services.ProcurementError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(PurchaseOrderSerializer(order).data)

    @action(detail=True, methods=["post"])
    def close(self, request: Request, pk: str | None = None) -> Response:
        order = self.get_object()
        try:
            services.close_order(
                order=order,
                user=cast(User, request.user),
                reason=str(request.data.get("reason", "")),
            )
        except services.ProcurementError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(PurchaseOrderSerializer(order).data)

    @action(detail=True, methods=["post"])
    def start_receipt(self, request: Request, pk: str | None = None) -> Response:
        """Open a draft GRN pre-filled with everything still outstanding."""
        order = self.get_object()
        try:
            receipt = services.build_receipt_draft(
                order=order,
                user=cast(User, request.user),
                received_on=(
                    _parse_date(request.data.get("received_on"), "received_on")
                    if request.data.get("received_on")
                    else None
                ),
                requires_qc=request.data.get("requires_qc"),
            )
        except services.ProcurementError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(GoodsReceiptSerializer(receipt).data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------


class ImportConsignmentViewSet(_AuditedViewSet):
    entity_type = "import_consignment"
    serializer_class = ImportConsignmentSerializer
    queryset = ImportConsignment.objects.all()
    owner_field = "created_by"
    manage_actions = ("allocate_costs", "attach_order", "detach_order")

    def get_queryset(self) -> QuerySet[ImportConsignment]:
        qs = (
            ImportConsignment.objects.filter(organization__in=self.visible_orgs())
            .select_related("organization", "supplier")
            .prefetch_related("costs", "orders__lines")
        )
        status_param = self.request.query_params.get("status")
        return qs.filter(status=status_param.upper()) if status_param else qs

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        organization = serializer.validated_data.get("organization")
        self.guard_org(organization)
        obj = serializer.save(
            created_by=cast(User, self.request.user),
            reference=services.next_document_number(organization, NumberSequence.Kind.IMPORT),
        )
        self._audit("CREATE", obj)

    @action(detail=True, methods=["post"])
    def attach_order(self, request: Request, pk: str | None = None) -> Response:
        consignment = self.get_object()
        order = PurchaseOrder.objects.filter(
            pk=lookup_pk(request.data.get("order")), organization__in=self.visible_orgs()
        ).first()
        if order is None:
            raise ValidationError({"order": "Unknown purchase order."})
        order.consignment = consignment
        order.is_import = True
        order.save(update_fields=["consignment", "is_import", "updated_at"])
        self._audit("IMPORT_ATTACH_PO", consignment)
        return Response(ImportConsignmentSerializer(consignment).data)

    @action(detail=True, methods=["post"])
    def detach_order(self, request: Request, pk: str | None = None) -> Response:
        consignment = self.get_object()
        order = consignment.orders.filter(pk=lookup_pk(request.data.get("order"))).first()
        if order is None:
            raise ValidationError({"order": "That order is not on this consignment."})
        order.consignment = None
        order.save(update_fields=["consignment", "updated_at"])
        return Response(ImportConsignmentSerializer(consignment).data)

    @action(detail=True, methods=["post"])
    def allocate_costs(self, request: Request, pk: str | None = None) -> Response:
        """Spread duty/freight/insurance/clearing into each line's unit cost."""
        consignment = self.get_object()
        basis = str(request.data.get("allocation_basis", "")).upper()
        if basis in {"VALUE", "QUANTITY"} and basis != consignment.allocation_basis:
            consignment.allocation_basis = basis
            consignment.save(update_fields=["allocation_basis", "updated_at"])
        try:
            result = services.allocate_landed_costs(
                consignment=consignment, user=cast(User, request.user)
            )
        except services.ProcurementError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(result)


class LandedCostComponentViewSet(_AuditedViewSet):
    entity_type = "landed_cost_component"
    serializer_class = LandedCostComponentSerializer
    queryset = LandedCostComponent.objects.all()

    def get_queryset(self) -> QuerySet[LandedCostComponent]:
        qs = LandedCostComponent.objects.filter(
            consignment__organization__in=self.visible_orgs()
        ).select_related("consignment")
        consignment = self.request.query_params.get("consignment")
        return qs.filter(consignment_id=lookup_pk(consignment)) if consignment else qs

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        consignment = serializer.validated_data.get("consignment")
        if consignment is not None:
            self.guard_org(consignment.organization)
        obj = serializer.save()
        record_audit(
            action="CREATE",
            user=cast(User, self.request.user),
            organization=obj.consignment.organization,
            entity_type=self.entity_type,
            entity_id=str(obj.pk),
            request=self.request,
        )


# ---------------------------------------------------------------------------
# Goods receipts
# ---------------------------------------------------------------------------


class GoodsReceiptViewSet(_AuditedViewSet):
    entity_type = "goods_receipt"
    serializer_class = GoodsReceiptSerializer
    queryset = GoodsReceipt.objects.all()
    owner_field = "received_by"
    manage_permission = CanReceiveGoods
    manage_actions = ("post_to_stock", "cancel")

    def get_queryset(self) -> QuerySet[GoodsReceipt]:
        qs = (
            GoodsReceipt.objects.filter(organization__in=self.visible_orgs())
            .select_related("order__supplier", "organization", "received_by", "posted_by")
            .prefetch_related("lines__product", "lines__order_line")
        )
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param.upper())
        order = self.request.query_params.get("order")
        if order:
            qs = qs.filter(order_id=lookup_pk(order))
        return qs

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        order = serializer.validated_data.get("order")
        organization = serializer.validated_data.get("organization") or (
            order.destination if order else None
        )
        self.guard_org(organization)
        obj = serializer.save(
            received_by=cast(User, self.request.user),
            organization=organization,
            grn_number=services.next_document_number(
                cast(Organization, organization), NumberSequence.Kind.GOODS_RECEIPT
            ),
        )
        self._audit("CREATE", obj)

    @action(detail=True, methods=["post"], url_path="post")
    def post_to_stock(self, request: Request, pk: str | None = None) -> Response:
        """Post the receipt: stock in, quarantine for QC, PO progress, GRN, GL."""
        receipt = self.get_object()
        try:
            services.post_goods_receipt(receipt=receipt, user=cast(User, request.user))
        except services.ProcurementError as exc:
            raise ValidationError(str(exc)) from exc
        except ValueError as exc:  # inventory / ledger guard rails
            raise ValidationError(str(exc)) from exc
        receipt.refresh_from_db()
        return Response(GoodsReceiptSerializer(receipt).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request: Request, pk: str | None = None) -> Response:
        receipt = self.get_object()
        if receipt.status != GoodsReceipt.Status.DRAFT:
            raise ValidationError("Only a draft goods receipt can be cancelled.")
        receipt.status = GoodsReceipt.Status.CANCELLED
        receipt.save(update_fields=["status", "updated_at"])
        self._audit("GRN_CANCELLED", receipt)
        return Response(GoodsReceiptSerializer(receipt).data)


# ---------------------------------------------------------------------------
# Supplier invoices & notes
# ---------------------------------------------------------------------------


class SupplierInvoiceViewSet(_AuditedViewSet):
    entity_type = "supplier_invoice"
    serializer_class = SupplierInvoiceSerializer
    queryset = SupplierInvoice.objects.all()
    owner_field = "created_by"
    number_field = "internal_number"
    number_kind = NumberSequence.Kind.SUPPLIER_INVOICE
    manage_permission = CanHandleInvoices
    manage_actions = ("match", "submit")

    def get_queryset(self) -> QuerySet[SupplierInvoice]:
        qs = (
            SupplierInvoice.objects.filter(organization__in=self.visible_orgs())
            .select_related("organization", "supplier", "order", "receipt", "finance_bill")
            .prefetch_related("lines__product", "lines__order_line", "notes_issued")
        )
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param.upper())
        supplier = self.request.query_params.get("supplier")
        if supplier:
            qs = qs.filter(supplier_id=supplier)
        if self.request.query_params.get("variance") == "1":
            qs = qs.exclude(match_result=SupplierInvoice.MatchResult.MATCHED)
        services.sync_approval_outcomes(
            resource_type=services.RES_SUPPLIER_INVOICE,
            objects=list(qs),
            pending_status=SupplierInvoice.Status.PENDING_APPROVAL,
            rejected_status=SupplierInvoice.Status.REJECTED,
        )
        return qs

    @action(detail=True, methods=["post"])
    def match(self, request: Request, pk: str | None = None) -> Response:
        """Run the 3-way match (PO ↔ GRN ↔ invoice) and return the line detail."""
        invoice = self.get_object()
        try:
            services.run_three_way_match(invoice=invoice, user=cast(User, request.user))
        except services.ProcurementError as exc:
            raise ValidationError(str(exc)) from exc
        invoice.refresh_from_db()
        return Response(SupplierInvoiceSerializer(invoice).data)

    @action(detail=True, methods=["post"])
    def submit(self, request: Request, pk: str | None = None) -> Response:
        invoice = self.get_object()
        try:
            approval = services.submit_invoice(
                invoice=invoice,
                user=cast(User, request.user),
                override_reason=str(request.data.get("override_reason", "")),
            )
        except services.ProcurementError as exc:
            raise ValidationError(str(exc)) from exc
        invoice.refresh_from_db()
        return Response(
            {
                "invoice": SupplierInvoiceSerializer(invoice).data,
                "approval_id": approval.pk,
                "message": "Sent to the approvals inbox for authorisation.",
            }
        )


class SupplierNoteViewSet(_AuditedViewSet):
    entity_type = "supplier_note"
    serializer_class = SupplierNoteSerializer
    queryset = SupplierNote.objects.all()
    owner_field = "created_by"
    manage_permission = CanHandleInvoices
    manage_actions = ("issue", "settle")

    def get_queryset(self) -> QuerySet[SupplierNote]:
        qs = SupplierNote.objects.filter(organization__in=self.visible_orgs()).select_related(
            "organization", "supplier", "invoice"
        )
        supplier = self.request.query_params.get("supplier")
        if supplier:
            qs = qs.filter(supplier_id=supplier)
        kind = self.request.query_params.get("kind")
        if kind:
            qs = qs.filter(kind=kind.upper())
        return qs

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        organization = serializer.validated_data.get("organization")
        self.guard_org(organization)
        kind = serializer.validated_data.get("kind", SupplierNote.Kind.DEBIT)
        obj = serializer.save(
            created_by=cast(User, self.request.user),
            note_number=services.next_document_number(
                organization,
                (
                    NumberSequence.Kind.DEBIT_NOTE
                    if kind == SupplierNote.Kind.DEBIT
                    else NumberSequence.Kind.CREDIT_NOTE
                ),
            ),
        )
        self._audit("CREATE", obj)

    @action(detail=True, methods=["post"])
    def issue(self, request: Request, pk: str | None = None) -> Response:
        note = self.get_object()
        try:
            services.issue_supplier_note(note=note, user=cast(User, request.user))
        except services.ProcurementError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(SupplierNoteSerializer(note).data)

    @action(detail=True, methods=["post"])
    def settle(self, request: Request, pk: str | None = None) -> Response:
        note = self.get_object()
        if note.status != SupplierNote.Status.ISSUED:
            raise ValidationError("Only an issued note can be settled.")
        note.status = SupplierNote.Status.SETTLED
        note.settled_on = _parse_date(
            request.data.get("settled_on"), "settled_on", timezone.localdate()
        )
        note.save(update_fields=["status", "settled_on", "updated_at"])
        self._audit("SUPPLIER_NOTE_SETTLED", note)
        return Response(SupplierNoteSerializer(note).data)


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


class SupplierStatementView(APIView):
    """Statement of account for one supplier — invoices, notes, payments, balance."""

    permission_classes = [IsAuthenticated, CanViewProcurement]

    def get(self, request: Request) -> Response:
        user = cast(User, request.user)
        orgs = organizations_visible_to(user)
        org = (
            orgs.filter(pk=lookup_pk(request.query_params.get("organization"))).first()
            if request.query_params.get("organization")
            else orgs.first()
        )
        if org is None:
            raise NotFound("No visible organization.")
        supplier = Supplier.objects.filter(
            pk=lookup_pk(request.query_params.get("supplier"))
        ).first()
        if supplier is None:
            raise ValidationError({"supplier": "A supplier id is required."})
        today = timezone.localdate()
        return Response(
            services.supplier_statement(
                organization=org,
                supplier=supplier,
                date_from=_parse_date(
                    request.query_params.get("from"), "from", today - timedelta(days=180)
                ),
                date_to=_parse_date(request.query_params.get("to"), "to", today),
            )
        )


class ProcurementOverviewView(APIView):
    """Headline numbers for the Procurement home screen."""

    permission_classes = [IsAuthenticated, CanViewProcurement]

    def get(self, request: Request) -> Response:
        user = cast(User, request.user)
        orgs = organizations_visible_to(user)
        orders = PurchaseOrder.objects.filter(organization__in=orgs)
        receivable = orders.filter(status__in=list(PurchaseOrder.RECEIVABLE))
        open_value = sum(
            (o.total_amount_base for o in receivable.prefetch_related("lines")), Decimal("0")
        )
        invoices = SupplierInvoice.objects.filter(organization__in=orgs)
        today = timezone.localdate()
        return Response(
            {
                "requisitions_pending": PurchaseRequisition.objects.filter(
                    organization__in=orgs, status=PurchaseRequisition.Status.SUBMITTED
                ).count(),
                "orders_draft": orders.filter(status=PurchaseOrder.Status.DRAFT).count(),
                "orders_awaiting_approval": orders.filter(
                    status=PurchaseOrder.Status.PENDING_APPROVAL
                ).count(),
                "orders_open": receivable.count(),
                "orders_open_value": str(open_value.quantize(Decimal("0.01"))),
                "orders_overdue": receivable.filter(expected_delivery__lt=today).count(),
                "receipts_draft": GoodsReceipt.objects.filter(
                    organization__in=orgs, status=GoodsReceipt.Status.DRAFT
                ).count(),
                "invoices_variance": invoices.filter(
                    status=SupplierInvoice.Status.VARIANCE
                ).count(),
                "invoices_pending_approval": invoices.filter(
                    status=SupplierInvoice.Status.PENDING_APPROVAL
                ).count(),
                "consignments_in_transit": ImportConsignment.objects.filter(
                    organization__in=orgs,
                    status__in=[
                        ImportConsignment.Status.SHIPPED,
                        ImportConsignment.Status.ARRIVED,
                        ImportConsignment.Status.AT_CUSTOMS,
                    ],
                ).count(),
                "rfqs_open": RequestForQuotation.objects.filter(
                    organization__in=orgs, status=RequestForQuotation.Status.SENT
                ).count(),
                "suppliers_blacklisted": SupplierProfile.objects.filter(
                    standing__in=[
                        SupplierProfile.Standing.BLACKLISTED,
                        SupplierProfile.Standing.SUSPENDED,
                    ]
                ).count(),
                "licences_expiring": SupplierLicence.objects.filter(
                    is_required=True, expires_on__lte=today + timedelta(days=90)
                ).count(),
                "top_suppliers": list(
                    orders.values("supplier__name")
                    .annotate(orders=Count("id"))
                    .order_by("-orders")[:5]
                ),
            }
        )
