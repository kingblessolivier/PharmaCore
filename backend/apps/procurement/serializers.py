"""Procurement serializers.

Documents are edited as a whole — header plus its lines in one payload — because a
purchase order with no lines is not a thing anyone wants to save. Each parent
serializer therefore takes a writable nested ``lines`` list; omitting the key on a
PATCH leaves the existing lines alone, sending it replaces them.

Computed money/progress fields are exposed read-only so the UI never has to
re-derive totals (and can never disagree with the ledger).
"""

from __future__ import annotations

from typing import Any, cast

from rest_framework import serializers

from apps.core.fields import QuantityAwareModelSerializer
from apps.procurement.models import (
    GoodsReceipt,
    GoodsReceiptLine,
    ImportConsignment,
    LandedCostComponent,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseRequisition,
    RequestForQuotation,
    RequisitionLine,
    RFQLine,
    SupplierEvaluation,
    SupplierInvoice,
    SupplierInvoiceLine,
    SupplierLicence,
    SupplierNote,
    SupplierPriceAgreement,
    SupplierProfile,
    SupplierQuote,
    SupplierQuoteLine,
)


class _NestedLinesMixin:
    """Create/replace a document's lines from a nested ``lines`` payload."""

    lines_field = "lines"
    line_model: Any = None
    parent_fk = ""

    def _write_lines(self, parent: Any, lines_data: list[dict[str, Any]] | None) -> None:
        if lines_data is None:
            return
        getattr(parent, self.lines_field).all().delete()
        for line in lines_data:
            self.line_model.objects.create(**{self.parent_fk: parent}, **line)

    def create(self, validated_data: dict[str, Any]) -> Any:
        lines_data = validated_data.pop(self.lines_field, [])
        parent = super().create(validated_data)  # type: ignore[misc]
        self._write_lines(parent, lines_data)
        return parent

    def update(self, instance: Any, validated_data: dict[str, Any]) -> Any:
        lines_data = validated_data.pop(self.lines_field, None)
        parent = super().update(instance, validated_data)  # type: ignore[misc]
        self._write_lines(parent, lines_data)
        return parent


# ---------------------------------------------------------------------------
# Supplier master
# ---------------------------------------------------------------------------


class SupplierLicenceSerializer(QuantityAwareModelSerializer[SupplierLicence]):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    days_to_expiry = serializers.IntegerField(read_only=True)
    verified_by_name = serializers.CharField(
        source="verified_by.username", read_only=True, default=None
    )

    class Meta:
        model = SupplierLicence
        fields = [
            "id",
            "supplier",
            "supplier_name",
            "kind",
            "kind_display",
            "licence_number",
            "issuing_authority",
            "issued_on",
            "expires_on",
            "is_required",
            "is_verified",
            "verified_by",
            "verified_by_name",
            "verified_at",
            "document_url",
            "notes",
            "is_expired",
            "days_to_expiry",
            "created_at",
        ]
        read_only_fields = ["verified_by", "verified_at", "created_at"]


class SupplierPriceAgreementSerializer(QuantityAwareModelSerializer[SupplierPriceAgreement]):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    product_name = serializers.CharField(source="product.__str__", read_only=True)
    organization_name = serializers.CharField(
        source="organization.name", read_only=True, default=None
    )

    class Meta:
        model = SupplierPriceAgreement
        fields = [
            "id",
            "supplier",
            "supplier_name",
            "product",
            "product_name",
            "organization",
            "organization_name",
            "contract_reference",
            "currency",
            "unit_price",
            "min_quantity",
            "lead_time_days",
            "moq",
            "pack_multiple",
            "valid_from",
            "valid_to",
            "is_active",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class SupplierEvaluationSerializer(QuantityAwareModelSerializer[SupplierEvaluation]):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    rated_by_name = serializers.CharField(source="rated_by.username", read_only=True, default=None)

    class Meta:
        model = SupplierEvaluation
        fields = [
            "id",
            "supplier",
            "supplier_name",
            "organization",
            "period_start",
            "period_end",
            "orders_count",
            "on_time_delivery_pct",
            "quality_acceptance_pct",
            "price_competitiveness",
            "responsiveness",
            "documentation_compliance",
            "overall_score",
            "is_auto_generated",
            "comments",
            "rated_by",
            "rated_by_name",
            "created_at",
        ]
        read_only_fields = fields


class SupplierProfileSerializer(QuantityAwareModelSerializer[SupplierProfile]):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    supplier_tin = serializers.CharField(source="supplier.tin", read_only=True)
    supplier_email = serializers.CharField(source="supplier.email", read_only=True)
    supplier_phone = serializers.CharField(source="supplier.phone", read_only=True)
    supplier_lead_time_days = serializers.IntegerField(
        source="supplier.lead_time_days", read_only=True
    )
    standing_display = serializers.CharField(source="get_standing_display", read_only=True)
    overall_score = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    can_order = serializers.BooleanField(read_only=True)
    licences = SupplierLicenceSerializer(
        source="supplier.procurement_licences", many=True, read_only=True
    )
    qualification_issues = serializers.SerializerMethodField()

    class Meta:
        model = SupplierProfile
        fields = [
            "id",
            "supplier",
            "supplier_name",
            "supplier_tin",
            "supplier_email",
            "supplier_phone",
            "supplier_lead_time_days",
            "kind",
            "standing",
            "standing_display",
            "standing_reason",
            "standing_changed_at",
            "trading_name",
            "country",
            "city",
            "address",
            "website",
            "contact_person",
            "contact_email",
            "contact_phone",
            "is_import_source",
            "currency",
            "incoterm",
            "payment_terms_days",
            "early_payment_discount_pct",
            "early_payment_days",
            "minimum_order_value",
            "lead_time_variance_days",
            "credit_limit",
            "bank_name",
            "bank_account_number",
            "bank_swift",
            "mobile_money_number",
            "delivery_score",
            "quality_score",
            "price_score",
            "compliance_score",
            "scores_updated_at",
            "overall_score",
            "can_order",
            "licences",
            "qualification_issues",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "standing",
            "standing_reason",
            "standing_changed_at",
            "delivery_score",
            "quality_score",
            "price_score",
            "compliance_score",
            "scores_updated_at",
            "created_at",
            "updated_at",
        ]

    def get_qualification_issues(self, obj: SupplierProfile) -> list[str]:
        from apps.procurement.services import supplier_licence_issues

        return supplier_licence_issues(obj.supplier)


# ---------------------------------------------------------------------------
# Requisitions
# ---------------------------------------------------------------------------


class RequisitionLineSerializer(QuantityAwareModelSerializer[RequisitionLine]):
    product_name = serializers.CharField(source="product.__str__", read_only=True)
    estimated_total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    quantity_outstanding = serializers.IntegerField(read_only=True)

    class Meta:
        model = RequisitionLine
        fields = [
            "id",
            "product",
            "product_name",
            "quantity",
            "quantity_approved",
            "quantity_ordered",
            "estimated_unit_cost",
            "estimated_total",
            "quantity_outstanding",
            "notes",
        ]
        read_only_fields = ["quantity_ordered"]


class PurchaseRequisitionSerializer(
    _NestedLinesMixin, QuantityAwareModelSerializer[PurchaseRequisition]
):
    line_model = RequisitionLine
    parent_fk = "requisition"

    lines = RequisitionLineSerializer(many=True, required=False)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    requested_by_name = serializers.CharField(
        source="requested_by.username", read_only=True, default=None
    )
    approved_by_name = serializers.CharField(
        source="approved_by.username", read_only=True, default=None
    )
    preferred_supplier_name = serializers.CharField(
        source="preferred_supplier.name", read_only=True, default=None
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    estimated_total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    is_editable = serializers.BooleanField(read_only=True)

    class Meta:
        model = PurchaseRequisition
        fields = [
            "id",
            "requisition_number",
            "organization",
            "organization_name",
            "status",
            "status_display",
            "priority",
            "needed_by",
            "justification",
            "preferred_supplier",
            "preferred_supplier_name",
            "requested_by",
            "requested_by_name",
            "submitted_at",
            "approved_by",
            "approved_by_name",
            "approved_at",
            "decision_note",
            "estimated_total",
            "is_editable",
            "lines",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "requisition_number",
            "status",
            "requested_by",
            "submitted_at",
            "approved_by",
            "approved_at",
            "decision_note",
            "created_at",
            "updated_at",
        ]


# ---------------------------------------------------------------------------
# RFQ & quotes
# ---------------------------------------------------------------------------


class RFQLineSerializer(QuantityAwareModelSerializer[RFQLine]):
    product_name = serializers.CharField(source="product.__str__", read_only=True)

    class Meta:
        model = RFQLine
        fields = ["id", "product", "product_name", "quantity", "specification"]


class SupplierQuoteLineSerializer(QuantityAwareModelSerializer[SupplierQuoteLine]):
    product_name = serializers.CharField(source="product.__str__", read_only=True)
    line_total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = SupplierQuoteLine
        fields = [
            "id",
            "rfq_line",
            "product",
            "product_name",
            "quantity_offered",
            "unit_price",
            "line_total",
            "lead_time_days",
            "notes",
        ]


class SupplierQuoteSerializer(_NestedLinesMixin, QuantityAwareModelSerializer[SupplierQuote]):
    line_model = SupplierQuoteLine
    parent_fk = "quote"

    lines = SupplierQuoteLineSerializer(many=True, required=False)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    rfq_number = serializers.CharField(source="rfq.rfq_number", read_only=True)
    goods_total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    total_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    total_amount_base = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = SupplierQuote
        fields = [
            "id",
            "rfq",
            "rfq_number",
            "supplier",
            "supplier_name",
            "quote_reference",
            "quote_date",
            "valid_until",
            "status",
            "currency",
            "exchange_rate",
            "incoterm",
            "lead_time_days",
            "payment_terms_days",
            "freight_amount",
            "other_charges",
            "discount_amount",
            "warranty_terms",
            "notes",
            "goods_total",
            "total_amount",
            "total_amount_base",
            "lines",
            "recorded_by",
            "created_at",
        ]
        read_only_fields = ["status", "recorded_by", "created_at"]


class RequestForQuotationSerializer(
    _NestedLinesMixin, QuantityAwareModelSerializer[RequestForQuotation]
):
    line_model = RFQLine
    parent_fk = "rfq"

    lines = RFQLineSerializer(many=True, required=False)
    quotes = SupplierQuoteSerializer(many=True, read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.username", read_only=True, default=None
    )
    quote_count = serializers.IntegerField(source="quotes.count", read_only=True)

    class Meta:
        model = RequestForQuotation
        fields = [
            "id",
            "rfq_number",
            "organization",
            "organization_name",
            "title",
            "status",
            "status_display",
            "requisition",
            "issued_on",
            "response_due",
            "delivery_required_by",
            "terms",
            "notes",
            "created_by",
            "created_by_name",
            "quote_count",
            "lines",
            "quotes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["rfq_number", "status", "created_by", "created_at", "updated_at"]


# ---------------------------------------------------------------------------
# Purchase orders
# ---------------------------------------------------------------------------


class PurchaseOrderLineSerializer(QuantityAwareModelSerializer[PurchaseOrderLine]):
    product_name = serializers.CharField(source="product.__str__", read_only=True)
    net_unit_price = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    line_subtotal = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    line_tax = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    line_total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    quantity_outstanding = serializers.IntegerField(read_only=True)
    base_unit_cost = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    effective_unit_cost = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    unit_code = serializers.CharField(source="unit.code", read_only=True, default="")
    unit_label = serializers.SerializerMethodField()
    pack_factor = serializers.DecimalField(
        max_digits=14, decimal_places=3, read_only=True, coerce_to_string=False
    )
    product_image = serializers.CharField(source="product.image_url", read_only=True, default="")

    def get_unit_label(self, obj: PurchaseOrderLine) -> str:
        """What a buyer calls it — 'Carton of 24 boxes', not 'CARTON'."""
        if obj.unit is None:
            return ""
        return obj.unit.name or obj.unit.get_code_display()

    class Meta:
        model = PurchaseOrderLine
        fields = [
            "id",
            "product",
            "product_name",
            "description",
            "quantity_ordered",
            "quantity_received",
            "quantity_rejected",
            "quantity_invoiced",
            # The unit the numbers above are counted in. Ten of something is
            # ten cartons or ten tablets, and the line has to say which.
            "unit",
            "unit_code",
            "unit_label",
            "pack_factor",
            "quantity_base",
            "product_image",
            "unit_price",
            "discount_pct",
            "tax_rate_pct",
            "expected_delivery",
            "requisition_line",
            "landed_cost_allocated",
            "landed_unit_cost",
            "net_unit_price",
            "line_subtotal",
            "line_tax",
            "line_total",
            "quantity_outstanding",
            "base_unit_cost",
            "effective_unit_cost",
            "notes",
        ]
        read_only_fields = [
            "quantity_received",
            "quantity_rejected",
            "quantity_invoiced",
            "landed_cost_allocated",
            "landed_unit_cost",
        ]


class PurchaseOrderSerializer(_NestedLinesMixin, QuantityAwareModelSerializer[PurchaseOrder]):
    line_model = PurchaseOrderLine
    parent_fk = "order"

    lines = PurchaseOrderLineSerializer(many=True, required=False)
    #: The PDF sent to the supplier, once the order has been sent.
    #:
    #: The document was being generated, numbered, hashed and stored, and no
    #: screen could reach it — so the one artefact the supplier actually
    #: receives was the one thing the buyer could not open again.
    document = serializers.SerializerMethodField()
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    deliver_to_name = serializers.CharField(source="deliver_to.name", read_only=True, default=None)
    consignment_reference = serializers.CharField(
        source="consignment.reference", read_only=True, default=None
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.username", read_only=True, default=None
    )
    approved_by_name = serializers.CharField(
        source="approved_by.username", read_only=True, default=None
    )
    subtotal = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    tax_total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    total_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    total_amount_base = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    quantity_ordered = serializers.IntegerField(read_only=True)
    quantity_received = serializers.IntegerField(read_only=True)
    received_pct = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    is_editable = serializers.BooleanField(read_only=True)
    can_receive = serializers.BooleanField(read_only=True)
    receipt_count = serializers.IntegerField(source="receipts.count", read_only=True)

    def get_document(self, obj: PurchaseOrder) -> dict[str, Any] | None:
        from apps.documents.models import Document

        record = (
            Document.objects.filter(reference_type="purchase_order", reference_id=str(obj.pk))
            .order_by("-generated_at")
            .first()
        )
        if record is None:
            return None
        return {
            "doc_number": record.doc_number,
            "generated_at": record.generated_at,
            "download_url": record.file.url if record.file else "",
        }

    class Meta:
        model = PurchaseOrder
        fields = [
            "id",
            "po_number",
            "organization",
            "organization_name",
            "supplier",
            "document",
            "supplier_name",
            "status",
            "status_display",
            "order_date",
            "expected_delivery",
            "currency",
            "exchange_rate",
            "incoterm",
            "payment_terms_days",
            "payment_terms_note",
            "freight_amount",
            "other_charges",
            "discount_amount",
            "is_import",
            "consignment",
            "consignment_reference",
            "is_dropship",
            "deliver_to",
            "deliver_to_name",
            "delivery_address",
            "requisition",
            "quote",
            "supplier_reference",
            "terms",
            "notes",
            "created_by",
            "created_by_name",
            "submitted_at",
            "approved_by",
            "approved_by_name",
            "approved_at",
            "sent_at",
            "sent_method",
            "closed_at",
            "cancelled_at",
            "cancel_reason",
            "subtotal",
            "tax_total",
            "total_amount",
            "total_amount_base",
            "quantity_ordered",
            "quantity_received",
            "received_pct",
            "is_editable",
            "can_receive",
            "receipt_count",
            "lines",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "po_number",
            "status",
            "created_by",
            "submitted_at",
            "approved_by",
            "approved_at",
            "sent_at",
            "sent_method",
            "closed_at",
            "cancelled_at",
            "cancel_reason",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        instance = cast(Any, self.instance)
        if instance is not None and not instance.is_editable:
            raise serializers.ValidationError(
                f"A {instance.get_status_display().lower()} purchase order can no longer "
                "be edited. Cancel it and raise a new one."
            )
        return attrs


# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------


class LandedCostComponentSerializer(QuantityAwareModelSerializer[LandedCostComponent]):
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    amount_base = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = LandedCostComponent
        fields = [
            "id",
            "consignment",
            "kind",
            "kind_display",
            "description",
            "vendor_name",
            "invoice_reference",
            "amount",
            "currency",
            "exchange_rate",
            "is_recoverable_tax",
            "incurred_on",
            "amount_base",
            "created_at",
        ]
        read_only_fields = ["created_at"]


class ImportConsignmentSerializer(QuantityAwareModelSerializer[ImportConsignment]):
    costs = LandedCostComponentSerializer(many=True, read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    goods_value_base = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    landed_cost_total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    recoverable_tax_total = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    total_landed_value = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    uplift_pct = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)
    order_numbers = serializers.SerializerMethodField()

    class Meta:
        model = ImportConsignment
        fields = [
            "id",
            "reference",
            "organization",
            "organization_name",
            "supplier",
            "supplier_name",
            "status",
            "status_display",
            "mode",
            "incoterm",
            "currency",
            "exchange_rate",
            "proforma_number",
            "proforma_date",
            "proforma_amount",
            "proforma_document_url",
            "bill_of_lading_number",
            "bill_of_lading_date",
            "airway_bill_number",
            "vessel_or_flight",
            "container_numbers",
            "carrier",
            "port_of_loading",
            "port_of_discharge",
            "country_of_origin",
            "gross_weight_kg",
            "packages_count",
            "etd",
            "eta",
            "arrived_on",
            "customs_declaration_number",
            "customs_office",
            "customs_cleared_on",
            "clearing_agent",
            "clearing_agent_contact",
            "hs_code_summary",
            "insurance_policy_number",
            "insurer_name",
            "insured_value",
            "allocation_basis",
            "costs_allocated_at",
            "notes",
            "created_by",
            "goods_value_base",
            "landed_cost_total",
            "recoverable_tax_total",
            "total_landed_value",
            "uplift_pct",
            "order_numbers",
            "costs",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "reference",
            "costs_allocated_at",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def get_order_numbers(self, obj: ImportConsignment) -> list[str]:
        return [po.po_number or str(po.pk) for po in obj.orders.all()]


# ---------------------------------------------------------------------------
# Goods receipt
# ---------------------------------------------------------------------------


class GoodsReceiptLineSerializer(QuantityAwareModelSerializer[GoodsReceiptLine]):
    product_name = serializers.CharField(source="product.__str__", read_only=True)
    variance = serializers.IntegerField(read_only=True)
    is_over_delivery = serializers.BooleanField(read_only=True)
    is_under_delivery = serializers.BooleanField(read_only=True)
    line_value = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = GoodsReceiptLine
        fields = [
            "id",
            "order_line",
            "product",
            "product_name",
            "batch_number",
            "manufacture_date",
            "expiry_date",
            "quantity_expected",
            "quantity_received",
            "quantity_rejected",
            "rejection_reason",
            "rejection_note",
            "unit_cost",
            "storage_location",
            "bin_location",
            "batch",
            "variance",
            "is_over_delivery",
            "is_under_delivery",
            "line_value",
        ]
        read_only_fields = ["batch"]


class GoodsReceiptSerializer(_NestedLinesMixin, QuantityAwareModelSerializer[GoodsReceipt]):
    line_model = GoodsReceiptLine
    parent_fk = "receipt"

    lines = GoodsReceiptLineSerializer(many=True, required=False)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    po_number = serializers.CharField(source="order.po_number", read_only=True)
    supplier_name = serializers.CharField(source="order.supplier.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    received_by_name = serializers.CharField(
        source="received_by.username", read_only=True, default=None
    )
    posted_by_name = serializers.CharField(
        source="posted_by.username", read_only=True, default=None
    )
    total_received = serializers.IntegerField(read_only=True)
    total_rejected = serializers.IntegerField(read_only=True)
    goods_value_base = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    is_editable = serializers.BooleanField(read_only=True)

    class Meta:
        model = GoodsReceipt
        fields = [
            "id",
            "grn_number",
            "order",
            "po_number",
            "supplier_name",
            "organization",
            "organization_name",
            "consignment",
            "status",
            "status_display",
            "received_on",
            "supplier_delivery_note",
            "waybill_number",
            "vehicle_plate",
            "driver_name",
            "requires_qc",
            "cold_chain_intact",
            "packaging_intact",
            "temperature_on_arrival_c",
            "has_discrepancy",
            "discrepancy_note",
            "notes",
            "received_by",
            "received_by_name",
            "inspected_by",
            "posted_by",
            "posted_by_name",
            "posted_at",
            "total_received",
            "total_rejected",
            "goods_value_base",
            "is_editable",
            "lines",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "grn_number",
            "status",
            "has_discrepancy",
            "received_by",
            "posted_by",
            "posted_at",
            "created_at",
            "updated_at",
        ]
        # Defaults to the order's deliver-to (drop-ship aware) when omitted.
        extra_kwargs = {"organization": {"required": False}}

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        instance = cast(Any, self.instance)
        if instance is not None and not instance.is_editable:
            raise serializers.ValidationError(
                "A posted goods receipt is immutable — it is a stock write-event. "
                "Correct it with a stock adjustment or a supplier note."
            )
        return attrs


# ---------------------------------------------------------------------------
# Supplier invoices & notes
# ---------------------------------------------------------------------------


class SupplierInvoiceLineSerializer(QuantityAwareModelSerializer[SupplierInvoiceLine]):
    product_name = serializers.CharField(source="product.__str__", read_only=True, default=None)
    net_unit_price = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    line_subtotal = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    line_tax = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    line_total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = SupplierInvoiceLine
        fields = [
            "id",
            "order_line",
            "product",
            "product_name",
            "description",
            "quantity",
            "unit_price",
            "discount_pct",
            "tax_rate_pct",
            "net_unit_price",
            "line_subtotal",
            "line_tax",
            "line_total",
        ]


class SupplierNoteSerializer(QuantityAwareModelSerializer[SupplierNote]):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    reason_display = serializers.CharField(source="get_reason_display", read_only=True)
    total_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    invoice_number = serializers.CharField(
        source="invoice.invoice_number", read_only=True, default=None
    )

    class Meta:
        model = SupplierNote
        fields = [
            "id",
            "note_number",
            "organization",
            "organization_name",
            "supplier",
            "supplier_name",
            "invoice",
            "invoice_number",
            "receipt",
            "kind",
            "kind_display",
            "reason",
            "reason_display",
            "status",
            "note_date",
            "amount",
            "tax_amount",
            "total_amount",
            "currency",
            "description",
            "settled_on",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "note_number",
            "status",
            "created_by",
            "created_at",
            "updated_at",
        ]


class SupplierInvoiceSerializer(_NestedLinesMixin, QuantityAwareModelSerializer[SupplierInvoice]):
    line_model = SupplierInvoiceLine
    parent_fk = "invoice"

    lines = SupplierInvoiceLineSerializer(many=True, required=False)
    notes_issued = SupplierNoteSerializer(many=True, read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    po_number = serializers.CharField(source="order.po_number", read_only=True, default=None)
    grn_number = serializers.CharField(source="receipt.grn_number", read_only=True, default=None)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    match_result_display = serializers.CharField(source="get_match_result_display", read_only=True)
    goods_subtotal = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    tax_total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    net_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    total_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    total_amount_base = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    notes_total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    payable_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    has_variance = serializers.BooleanField(read_only=True)
    is_editable = serializers.BooleanField(read_only=True)
    approved_by_name = serializers.CharField(
        source="approved_by.username", read_only=True, default=None
    )

    class Meta:
        model = SupplierInvoice
        fields = [
            "id",
            "invoice_number",
            "internal_number",
            "organization",
            "organization_name",
            "supplier",
            "supplier_name",
            "order",
            "po_number",
            "receipt",
            "grn_number",
            "status",
            "status_display",
            "invoice_date",
            "due_date",
            "currency",
            "exchange_rate",
            "freight_amount",
            "other_charges",
            "discount_amount",
            "tax_class",
            "match_result",
            "match_result_display",
            "match_detail",
            "qty_tolerance_pct",
            "price_tolerance_pct",
            "matched_at",
            "override_reason",
            "finance_bill",
            "approved_by",
            "approved_by_name",
            "approved_at",
            "rejected_reason",
            "notes",
            "created_by",
            "goods_subtotal",
            "tax_total",
            "net_amount",
            "total_amount",
            "total_amount_base",
            "notes_total",
            "payable_amount",
            "has_variance",
            "is_editable",
            "lines",
            "notes_issued",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "internal_number",
            "status",
            "match_result",
            "match_detail",
            "matched_at",
            "override_reason",
            "finance_bill",
            "approved_by",
            "approved_at",
            "rejected_reason",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        instance = cast(Any, self.instance)
        if instance is not None and not instance.is_editable:
            raise serializers.ValidationError(
                "An approved or cancelled invoice can no longer be edited — raise a "
                "debit/credit note instead."
            )
        return attrs
