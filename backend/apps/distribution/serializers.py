from __future__ import annotations

from typing import Any

from django.db import transaction
from rest_framework import serializers

from apps.core.fields import QuantityAwareModelSerializer
from apps.distribution.models import (
    BackorderLine,
    CustomerReturn,
    CustomerReturnLine,
    DepotProductListing,
    GoodsReceivedNote,
    GRNLine,
    InTransitStock,
    JourneyPlan,
    OrderItem,
    OrderPayment,
    SalesRepresentative,
    SalesVisitLog,
    Shipment,
    StockOrder,
    TenderContract,
    VanStock,
    VanStockMovement,
)


class OrderPaymentSerializer(QuantityAwareModelSerializer):
    class Meta:
        model = OrderPayment
        fields = ["id", "amount", "method", "reference", "paid_at"]
        read_only_fields = ["id", "paid_at"]


class InTransitStockSerializer(QuantityAwareModelSerializer):
    product_name = serializers.SerializerMethodField()
    source_name = serializers.CharField(source="source_org.name", read_only=True)
    destination_name = serializers.CharField(source="destination_org.name", read_only=True)
    order_number = serializers.CharField(source="order.order_number", read_only=True)

    class Meta:
        model = InTransitStock
        fields = [
            "id",
            "order",
            "order_number",
            "source_org",
            "source_name",
            "destination_org",
            "destination_name",
            "product",
            "product_name",
            "batch_number",
            "expiry_date",
            "quantity",
            "dispatched_at",
        ]
        read_only_fields = fields

    def get_product_name(self, obj: InTransitStock) -> str:
        return f"{obj.product.generic_name} {obj.product.strength}".strip()


class ShipmentSerializer(QuantityAwareModelSerializer):
    class Meta:
        model = Shipment
        fields = ["id", "driver_name", "vehicle_registration", "dispatched_at"]
        read_only_fields = fields


class GRNLineSerializer(QuantityAwareModelSerializer):
    product_name = serializers.SerializerMethodField()
    has_discrepancy = serializers.BooleanField(read_only=True)

    class Meta:
        model = GRNLine
        fields = [
            "id",
            "product",
            "product_name",
            "batch_number",
            "expiry_date",
            "quantity_expected",
            "quantity_received",
            "quantity_damaged",
            "has_discrepancy",
        ]
        read_only_fields = fields

    def get_product_name(self, obj: GRNLine) -> str:
        return f"{obj.product.generic_name} {obj.product.strength}".strip()


class GRNSerializer(QuantityAwareModelSerializer):
    lines = GRNLineSerializer(many=True, read_only=True)
    order_number = serializers.CharField(source="order.order_number", read_only=True)

    class Meta:
        model = GoodsReceivedNote
        fields = [
            "id",
            "grn_number",
            "order",
            "order_number",
            "status",
            "has_discrepancy",
            "received_at",
            "lines",
        ]
        read_only_fields = fields


class OrderItemSerializer(QuantityAwareModelSerializer):
    product_name = serializers.SerializerMethodField()
    line_total = serializers.FloatField(read_only=True)

    product_image = serializers.CharField(source="product.image_url", read_only=True, default="")

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product",
            "product_name",
            "product_image",
            "quantity_ordered",
            "quantity_approved",
            "quantity_shipped",
            "quantity_received",
            "price_per_unit",
            "line_total",
        ]
        read_only_fields = [
            "id",
            "product_name",
            "quantity_approved",
            "quantity_shipped",
            "quantity_received",
            # Price is NOT set by the buyer — it is pulled from the depot's wholesale price.
            "price_per_unit",
            "line_total",
        ]

    def get_product_name(self, obj: OrderItem) -> str:
        return f"{obj.product.generic_name} {obj.product.strength}".strip()


class StockOrderSerializer(QuantityAwareModelSerializer):
    items = OrderItemSerializer(many=True)
    depot_name = serializers.CharField(source="depot.name", read_only=True)
    retail_name = serializers.CharField(source="retail.name", read_only=True)
    total_amount = serializers.FloatField(read_only=True)
    amount_due = serializers.FloatField(read_only=True)
    shipments = ShipmentSerializer(many=True, read_only=True)
    order_payments = OrderPaymentSerializer(many=True, read_only=True)
    in_transit = InTransitStockSerializer(many=True, read_only=True)
    # Opt out to have unfillable lines refused outright instead of recorded as
    # demand. On by default: a depot that never hears what it could not supply
    # cannot decide what to import.
    allow_backorder = serializers.BooleanField(write_only=True, required=False, default=True)
    backorders = serializers.SerializerMethodField()

    class Meta:
        model = StockOrder
        fields = [
            "id",
            "order_number",
            "depot",
            "depot_name",
            "retail",
            "retail_name",
            "status",
            "expected_delivery",
            "notes",
            "total_amount",
            "payment_status",
            "amount_paid",
            "amount_due",
            "payment_due_date",
            "order_payments",
            "in_transit",
            "items",
            "shipments",
            "allow_backorder",
            "backorders",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "order_number",
            "status",
            "total_amount",
            "payment_status",
            "amount_paid",
            "amount_due",
            "order_payments",
            "backorders",
            "created_at",
        ]

    def get_backorders(self, obj: StockOrder) -> list[dict[str, Any]]:
        """What this order asked for that the depot could not supply."""
        return [
            {
                "id": b.pk,
                "product": b.product_id,
                "product_name": str(b.product),
                "quantity": b.quantity,
                "status": b.status,
                "origin": b.origin,
                "note": b.note,
            }
            for b in obj.backorders.select_related("product").all()
        ]

    @transaction.atomic
    def create(self, validated_data: dict[str, Any]) -> StockOrder:
        from apps.distribution import demand as demand_engine
        from apps.distribution.marketplace import decide_line

        items = validated_data.pop("items", [])
        allow_backorder = validated_data.pop("allow_backorder", True)
        order = StockOrder.objects.create(**validated_data)
        # Stamp the human-readable number immediately. ``order_number`` is unique, so
        # leaving it at its "" default (even briefly) makes the *next* order collide.
        order.order_number = f"PO-{order.pk:05d}"
        order.save(update_fields=["order_number"])

        user = getattr(self.context.get("request"), "user", None)
        placed = 0
        shortfalls: list[str] = []

        for item in items:
            product = item["product"]
            requested = item["quantity_ordered"]
            decision = decide_line(
                depot=order.depot_id,
                buyer=order.retail_id,
                product=product,
                quantity=requested,
                allow_backorder=allow_backorder,
            )

            if decision.fulfillable > 0:
                # Authoritative: the depot's published price (or its awarded tender
                # price), never the buyer's input.
                line = {**item, "quantity_ordered": decision.fulfillable}
                OrderItem.objects.create(order=order, price_per_unit=decision.price, **line)
                placed += 1

            if decision.backordered > 0:
                demand_engine.capture(
                    depot=order.depot_id,
                    retail=order.retail_id,
                    product=product,
                    quantity=decision.backordered,
                    origin=demand_engine.origin_for(decision.availability),
                    order=order,
                    note=decision.note,
                    user=user if user and user.is_authenticated else None,
                )
                shortfalls.append(f"{product}: {decision.backordered} ({decision.note})")

            if decision.fulfillable == 0 and decision.backordered == 0:
                raise serializers.ValidationError(
                    f"'{product}' cannot be ordered from {order.depot.name}"
                    f"{' — ' + decision.note if decision.note else ''}."
                )

        if placed == 0 and not shortfalls:
            raise serializers.ValidationError("No line on this order could be placed.")

        # An order that is entirely backordered is legitimate — it is a request the
        # depot will import against — but it must not sit in the fulfilment flow as
        # though goods were coming, so it stays in DRAFT with its demand recorded.
        self._shortfalls = shortfalls
        return order


class DepotProductListingSerializer(QuantityAwareModelSerializer):
    product_name = serializers.CharField(source="product.generic_name", read_only=True)
    product_brand = serializers.CharField(source="product.brand_name", read_only=True)
    depot_name = serializers.CharField(source="depot.name", read_only=True)
    available_for_order = serializers.IntegerField(read_only=True)
    # ``available_for_order`` on the model is the published intent (offered minus
    # buffer) and knows nothing about stock. These are the live figures the
    # storefront and the order guard actually use.
    available_now = serializers.SerializerMethodField()
    stock_on_hand = serializers.SerializerMethodField()
    availability_note = serializers.SerializerMethodField()

    image = serializers.SerializerMethodField()
    image_is_trusted = serializers.BooleanField(read_only=True)
    # ``image`` above falls back to the catalogue picture, which is right for a
    # buyer and wrong for the depot managing its own listing — it would show a
    # photo they cannot replace and did not upload. So the depot's own field is
    # served separately, alongside who vouched for it.
    image_verified_by_name = serializers.CharField(
        source="image_verified_by.get_full_name", read_only=True, default=""
    )
    pack_units = serializers.SerializerMethodField()

    def get_image(self, obj: DepotProductListing) -> str:
        """The depot's own photograph, or the catalogue's."""
        return obj.image_url or obj.product.image_url or ""

    def get_pack_units(self, obj: DepotProductListing) -> list[dict[str, Any]]:
        """The levels this medicine is packed in, smallest first."""
        return [
            {
                "code": unit.code,
                "label": unit.name or unit.get_code_display(),
                "factor_to_base": str(unit.factor_to_base),
                "is_base": unit.is_base,
                "is_purchase_default": unit.is_purchase_default,
            }
            for unit in sorted(obj.product.units.all(), key=lambda u: u.level)
        ]

    class Meta:
        model = DepotProductListing
        fields = [
            "id",
            "depot",
            "depot_name",
            "product",
            "product_name",
            "product_brand",
            "offered_qty",
            "buffer_qty",
            "price_per_unit",
            "available_for_order",
            "available_now",
            "stock_on_hand",
            "availability_note",
            "is_published",
            "customer_segment",
            "min_order_qty",
            "order_multiple",
            # A buyer browsing a storefront of text alone cannot tell one white
            # box from another. `image` falls back to the catalogue picture when
            # the depot has not photographed its own stock.
            "image",
            "image_is_trusted",
            # The depot's own photo, unfallen-back, plus who vouched for it —
            # what the seller needs to manage the picture rather than just see
            # one. Without these the listing screen cannot tell "no photo" from
            # "showing the catalogue's photo", and cannot show whether the tick
            # has been given.
            "image_url",
            "image_verified_at",
            "image_verified_by_name",
            # How it is packed, so a pharmacy orders a case knowing it holds 24
            # boxes of 100 rather than guessing what "1" means.
            "pack_units",
            "updated_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "available_for_order",
            "available_now",
            "stock_on_hand",
            "availability_note",
            "updated_at",
            "created_at",
        ]

    def _availability(self, obj: DepotProductListing) -> Any:
        from apps.distribution.marketplace import availability

        cache = self.context.setdefault("_avail_cache", {})
        if obj.pk not in cache:
            cache[obj.pk] = availability(depot=obj.depot_id, product=obj.product_id)
        return cache[obj.pk]

    def get_available_now(self, obj: DepotProductListing) -> int:
        return self._availability(obj).available

    def get_stock_on_hand(self, obj: DepotProductListing) -> int:
        """Physical free stock — shown to the depot, never to a buyer.

        A depot may hold stock it has deliberately not offered. Exposing that to
        the buying side would defeat the point of withholding it, so this is
        served only where the requester owns the depot.
        """
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return 0
        owns_depot = (
            user.is_superuser or user.has_role("SYS_ADMIN") or user.organization_id == obj.depot_id
        )
        return self._availability(obj).physical_free if owns_depot else 0

    def get_availability_note(self, obj: DepotProductListing) -> str:
        return self._availability(obj).reason


class SalesRepresentativeSerializer(QuantityAwareModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    full_name = serializers.CharField(source="user.get_full_name", read_only=True)

    class Meta:
        model = SalesRepresentative
        fields = [
            "id",
            "organization",
            "user",
            "username",
            "full_name",
            "employee",
            "territory_code",
            "monthly_sales_target",
            "commission_rate_pct",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class JourneyPlanSerializer(QuantityAwareModelSerializer):
    rep_username = serializers.CharField(source="rep.user.username", read_only=True)
    customer_name = serializers.CharField(source="customer_org.name", read_only=True)

    class Meta:
        model = JourneyPlan
        fields = [
            "id",
            "rep",
            "rep_username",
            "customer_org",
            "customer_name",
            "planned_date",
            "is_completed",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class SalesVisitLogSerializer(QuantityAwareModelSerializer):
    rep_username = serializers.CharField(source="rep.user.username", read_only=True)
    customer_name = serializers.CharField(source="customer_org.name", read_only=True)

    class Meta:
        model = SalesVisitLog
        fields = [
            "id",
            "journey_plan",
            "rep",
            "rep_username",
            "customer_org",
            "customer_name",
            "visit_type",
            "visited_at",
            "notes",
            "order",
            "sales_amount",
        ]
        read_only_fields = ["id", "visited_at"]


class TenderContractSerializer(QuantityAwareModelSerializer):
    depot_name = serializers.CharField(source="depot.name", read_only=True)
    client_name = serializers.CharField(source="client_org.name", read_only=True)
    product_name = serializers.CharField(source="product.generic_name", read_only=True)
    remaining_qty = serializers.IntegerField(read_only=True)

    class Meta:
        model = TenderContract
        fields = [
            "id",
            "tender_number",
            "depot",
            "depot_name",
            "client_org",
            "client_name",
            "product",
            "product_name",
            "contract_price",
            "total_committed_qty",
            "drawn_qty",
            "remaining_qty",
            "valid_until",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "remaining_qty", "created_at"]


class CustomerReturnLineSerializer(QuantityAwareModelSerializer):
    product_name = serializers.CharField(source="product.generic_name", read_only=True)
    credit_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = CustomerReturnLine
        fields = [
            "id",
            "product",
            "product_name",
            "batch_number",
            "expiry_date",
            "quantity_returned",
            "quantity_accepted",
            "quantity_rejected",
            "unit_price",
            "inspection_note",
            "restocked_batch",
            "credit_amount",
        ]
        read_only_fields = ["id", "restocked_batch", "credit_amount"]


class CustomerReturnSerializer(QuantityAwareModelSerializer):
    depot_name = serializers.CharField(source="depot.name", read_only=True)
    retail_name = serializers.CharField(source="retail.name", read_only=True)
    lines = CustomerReturnLineSerializer(many=True, required=False)

    class Meta:
        model = CustomerReturn
        fields = [
            "id",
            "return_number",
            "depot",
            "depot_name",
            "retail",
            "retail_name",
            "status",
            "reason",
            "credit_note_amount",
            "lines",
            "created_at",
        ]
        # ``credit_note_amount`` is computed from inspected lines at approval. It
        # was previously typed by hand, which is how a retailer could be credited
        # for stock that never came back.
        read_only_fields = ["id", "status", "credit_note_amount", "created_at"]

    @transaction.atomic
    def create(self, validated_data: dict[str, Any]) -> CustomerReturn:
        lines = validated_data.pop("lines", [])
        if not validated_data.get("return_number"):
            validated_data["return_number"] = "RET-PENDING"
        request = CustomerReturn.objects.create(**validated_data)
        if request.return_number == "RET-PENDING":
            request.return_number = f"RET-{request.pk:05d}"
            request.save(update_fields=["return_number"])
        for line in lines:
            CustomerReturnLine.objects.create(return_request=request, **line)
        return request


class BackorderLineSerializer(QuantityAwareModelSerializer):
    product_name = serializers.CharField(source="product.generic_name", read_only=True)
    depot_name = serializers.CharField(source="depot.name", read_only=True)
    retail_name = serializers.CharField(source="retail.name", read_only=True)
    quantity_outstanding = serializers.IntegerField(read_only=True)
    order_number = serializers.CharField(source="order.order_number", read_only=True, default="")

    class Meta:
        model = BackorderLine
        fields = [
            "id",
            "depot",
            "depot_name",
            "retail",
            "retail_name",
            "product",
            "product_name",
            "order",
            "order_number",
            "quantity",
            "quantity_fulfilled",
            "quantity_outstanding",
            "status",
            "origin",
            "note",
            "requisition",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "quantity_fulfilled",
            "quantity_outstanding",
            "status",
            "requisition",
            "created_at",
        ]


class VanStockSerializer(QuantityAwareModelSerializer):
    product_name = serializers.CharField(source="product.generic_name", read_only=True)
    rep_name = serializers.CharField(source="rep.user.username", read_only=True)

    class Meta:
        model = VanStock
        fields = ["id", "rep", "rep_name", "product", "product_name", "batch_number", "quantity"]
        # Van quantities move only through load/sell/return, never by direct edit —
        # an editable quantity is stock that cannot be reconciled.
        read_only_fields = ["id", "quantity"]


class VanStockMovementSerializer(QuantityAwareModelSerializer):
    product_name = serializers.CharField(source="product.generic_name", read_only=True)

    class Meta:
        model = VanStockMovement
        fields = [
            "id",
            "rep",
            "product",
            "product_name",
            "batch_number",
            "kind",
            "quantity",
            "visit",
            "reference",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
