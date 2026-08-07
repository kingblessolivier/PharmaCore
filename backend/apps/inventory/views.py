"""Inventory API: per-pharmacy product listing, batch stock, storage zones, bins,
temperature logs, QA checks, batch recalls, physical stock counts, and witness disposal.

Org-scoped; reads for any authed user in the org, writes admin/manager-only and audited.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, cast

from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView

from apps.core.lookups import lookup_pk
from apps.iam.audit import record_audit
from apps.iam.models import Organization, User
from apps.iam.permissions import CanManageOrg
from apps.iam.scoping import organizations_visible_to
from apps.inventory import analytics, coldchain, gs1, serialisation, warehouse_services
from apps.inventory.models import (
    BatchRecall,
    BinLocation,
    ConsignmentAgreement,
    ConsignmentConsumption,
    ConsignmentSettlement,
    EpcisEvent,
    ExcursionInvestigation,
    InventoryBatch,
    PharmacyProduct,
    PickTask,
    PickWave,
    PutawayRule,
    QualityCheck,
    ReorderRule,
    SensorCalibration,
    SerialUnit,
    StockCount,
    StockDisposal,
    StockMovement,
    StorageZone,
    TemperatureLog,
    TemperatureSensor,
    Warehouse,
)
from apps.inventory.serializers import (
    AggregateSerializer,
    ApplyPutawaySerializer,
    BatchRecallSerializer,
    BinLocationSerializer,
    BuildTasksSerializer,
    CloseInvestigationSerializer,
    ConfirmPickSerializer,
    ConsignmentAgreementSerializer,
    ConsignmentConsumptionSerializer,
    ConsignmentSettlementSerializer,
    DisaggregateSerializer,
    EpcisEventSerializer,
    ExcursionInvestigationSerializer,
    IntakeSerializer,
    InventoryBatchSerializer,
    ObserveSerializer,
    OpenInvestigationSerializer,
    PharmacyProductSerializer,
    PickTaskSerializer,
    PickWaveSerializer,
    PutawayRuleSerializer,
    QualityCheckSerializer,
    RecordCalibrationSerializer,
    ReorderRuleSerializer,
    ScanSerializer,
    SensorCalibrationSerializer,
    SerialUnitSerializer,
    SettleConsignmentSerializer,
    StockCountSerializer,
    StockDisposalSerializer,
    StockMovementSerializer,
    StorageZoneSerializer,
    TemperatureLogSerializer,
    TemperatureSensorSerializer,
    WarehouseSerializer,
)
from apps.inventory.services import adjust_stock, log_wastage, receive_intake

_WRITE = {"create", "update", "partial_update", "destroy"}


class _AuditedAdminViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_permissions(self) -> list[BasePermission]:
        if self.action in _WRITE:
            return [IsAuthenticated(), CanManageOrg()]
        return [IsAuthenticated()]

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        obj = serializer.save()
        org = getattr(obj, "organization", None) or getattr(
            getattr(obj, "zone", None), "organization", None
        )
        record_audit(
            action="CREATE",
            user=cast(User, self.request.user),
            organization=org,
            entity_type=obj._meta.model_name,
            entity_id=str(obj.pk),
            request=self.request,
        )

    def perform_update(self, serializer: BaseSerializer[Any]) -> None:
        obj = serializer.save()
        org = getattr(obj, "organization", None) or getattr(
            getattr(obj, "zone", None), "organization", None
        )
        record_audit(
            action="UPDATE",
            user=cast(User, self.request.user),
            organization=org,
            entity_type=obj._meta.model_name,
            entity_id=str(obj.pk),
            request=self.request,
        )

    def perform_destroy(self, instance: Any) -> None:
        org = getattr(instance, "organization", None) or getattr(
            getattr(instance, "zone", None), "organization", None
        )
        record_audit(
            action="DELETE",
            user=cast(User, self.request.user),
            organization=org,
            entity_type=instance._meta.model_name,
            entity_id=str(instance.pk),
            request=self.request,
        )
        instance.delete()


def _require_org(request: Request, org: Organization | None) -> Organization:
    """Resolve an organization from the request and check the caller may act for it."""
    if org is None:
        raise ValidationError({"organization": "An organization is required."})
    user = cast(User, request.user)
    if not organizations_visible_to(user).filter(pk=org.pk).exists():
        raise PermissionDenied("You cannot act for that organization.")
    return org


def _org_from_query(request: Request) -> Organization:
    raw = request.query_params.get("organization")
    if not raw:
        raise ValidationError({"organization": "Pass ?organization=<id>."})
    return _require_org(request, Organization.objects.filter(pk=raw).first())


class StorageZoneViewSet(_AuditedAdminViewSet):
    serializer_class = StorageZoneSerializer
    queryset = StorageZone.objects.all()

    def get_queryset(self) -> QuerySet[StorageZone]:
        user = cast(User, self.request.user)
        return StorageZone.objects.filter(organization__in=organizations_visible_to(user))


class BinLocationViewSet(_AuditedAdminViewSet):
    serializer_class = BinLocationSerializer
    queryset = BinLocation.objects.all()

    def get_queryset(self) -> QuerySet[BinLocation]:
        user = cast(User, self.request.user)
        return BinLocation.objects.filter(zone__organization__in=organizations_visible_to(user))


class TemperatureSensorViewSet(_AuditedAdminViewSet):
    serializer_class = TemperatureSensorSerializer
    queryset = TemperatureSensor.objects.all()

    def get_queryset(self) -> QuerySet[TemperatureSensor]:
        user = cast(User, self.request.user)
        qs = TemperatureSensor.objects.select_related("zone").filter(
            organization__in=organizations_visible_to(user)
        )
        org = self.request.query_params.get("organization")
        if org:
            qs = qs.filter(organization_id=org)
        return qs

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, CanManageOrg])
    def record_calibration(self, request: Request, pk: str | None = None) -> Response:
        """File a calibration certificate against the sensor's register."""
        sensor = self.get_object()
        ser = RecordCalibrationSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            calibration = coldchain.record_calibration(
                sensor=sensor, user=cast(User, request.user), **ser.validated_data
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        record_audit(
            action="SENSOR_CALIBRATION",
            user=cast(User, request.user),
            organization=sensor.organization,
            entity_type="sensor_calibration",
            entity_id=str(calibration.pk),
            changes={"certificate_no": calibration.certificate_no, "result": calibration.result},
            request=request,
        )
        return Response(
            SensorCalibrationSerializer(calibration).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["get"])
    def thermal_profile(self, request: Request, pk: str | None = None) -> Response:
        """MKT, min/mean/max and excursion counts over a window (default 30 days)."""
        sensor = self.get_object()
        days = int(request.query_params.get("days", 30))
        return Response(
            analytics.sensor_thermal_profile(
                sensor, start=timezone.now() - timedelta(days=days), end=timezone.now()
            )
        )

    @action(detail=False, methods=["get"])
    def calibration_register(self, request: Request) -> Response:
        """Every sensor with its calibration state — what an inspector asks to see."""
        return Response(coldchain.calibration_register(_org_from_query(request)))


class TemperatureLogViewSet(_AuditedAdminViewSet):
    serializer_class = TemperatureLogSerializer
    queryset = TemperatureLog.objects.all()

    def get_queryset(self) -> QuerySet[TemperatureLog]:
        user = cast(User, self.request.user)
        return TemperatureLog.objects.filter(
            sensor__organization__in=organizations_visible_to(user)
        )


class QualityCheckViewSet(_AuditedAdminViewSet):
    serializer_class = QualityCheckSerializer
    queryset = QualityCheck.objects.all()

    def get_queryset(self) -> QuerySet[QualityCheck]:
        user = cast(User, self.request.user)
        return QualityCheck.objects.filter(batch__organization__in=organizations_visible_to(user))

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        serializer.save(inspector=cast(User, self.request.user))

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, CanManageOrg])
    def pass_qc(self, request: Request, pk: str | None = None) -> Response:
        qc = self.get_object()
        qc.status = QualityCheck.Status.PASSED
        qc.save()
        batch = qc.batch
        batch.status = InventoryBatch.Status.ACTIVE
        batch.save()
        return Response(QualityCheckSerializer(qc).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, CanManageOrg])
    def fail_qc(self, request: Request, pk: str | None = None) -> Response:
        qc = self.get_object()
        qc.status = QualityCheck.Status.FAILED
        qc.save()
        batch = qc.batch
        batch.status = InventoryBatch.Status.QUARANTINE
        batch.save()
        return Response(QualityCheckSerializer(qc).data)


class BatchRecallViewSet(_AuditedAdminViewSet):
    serializer_class = BatchRecallSerializer
    queryset = BatchRecall.objects.all()

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, CanManageOrg])
    def execute_freeze(self, request: Request, pk: str | None = None) -> Response:
        recall = self.get_object()
        # Freeze batch across all organizations
        affected = InventoryBatch.objects.filter(batch_number=recall.batch_number)
        updated_count = affected.update(status=InventoryBatch.Status.RECALLED)
        recall.status = BatchRecall.Status.IN_PROGRESS
        recall.save()
        record_audit(
            action="EMERGENCY_RECALL_FREEZE",
            user=cast(User, request.user),
            organization=None,
            entity_type="batch_recall",
            entity_id=str(recall.pk),
            changes={"batch_number": recall.batch_number, "frozen_batches": updated_count},
            request=request,
        )
        return Response({"status": "frozen", "affected_batches": updated_count})


class StockCountViewSet(_AuditedAdminViewSet):
    serializer_class = StockCountSerializer
    queryset = StockCount.objects.all()

    def get_queryset(self) -> QuerySet[StockCount]:
        user = cast(User, self.request.user)
        return StockCount.objects.filter(organization__in=organizations_visible_to(user))

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        serializer.save(counter_user=cast(User, self.request.user))

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, CanManageOrg])
    def approve_count(self, request: Request, pk: str | None = None) -> Response:
        from apps.finance.services import post_inventory_adjustment

        sc = self.get_object()
        with transaction.atomic():
            for item in sc.items.all():
                if item.variance_qty != 0:
                    delta = item.variance_qty
                    adjust_stock(
                        batch=item.batch,
                        counted_quantity=item.counted_qty,
                        reason=f"Stock Count Variance Reconciliation ({sc.reference_no})",
                        user=cast(User, request.user),
                    )
                    post_inventory_adjustment(
                        batch=item.batch,
                        delta=delta,
                        unit_cost=item.batch.wholesale_cost,
                        reason=f"Stock count {sc.reference_no}",
                        reference_type="stock_count",
                        reference_id=str(sc.pk),
                        user=cast(User, request.user),
                    )
            sc.status = StockCount.Status.APPROVED
            sc.approver_user = cast(User, request.user)
            sc.completed_at = timezone.now()
            sc.save()
        return Response(StockCountSerializer(sc).data)


class StockDisposalViewSet(_AuditedAdminViewSet):
    serializer_class = StockDisposalSerializer
    queryset = StockDisposal.objects.all()

    def get_queryset(self) -> QuerySet[StockDisposal]:
        user = cast(User, self.request.user)
        return StockDisposal.objects.filter(organization__in=organizations_visible_to(user))

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        serializer.save(primary_witness=cast(User, self.request.user))

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, CanManageOrg])
    def confirm_destruction(self, request: Request, pk: str | None = None) -> Response:
        sd = self.get_object()
        sd.status = StockDisposal.Status.DESTROYED
        sd.destroyed_at = timezone.now()
        sd.save()
        return Response(StockDisposalSerializer(sd).data)


class PharmacyProductViewSet(viewsets.ModelViewSet):
    serializer_class = PharmacyProductSerializer
    queryset = PharmacyProduct.objects.select_related("product", "organization").all()
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self) -> list[BasePermission]:
        if self.action in _WRITE:
            return [IsAuthenticated(), CanManageOrg()]
        return [IsAuthenticated()]

    def get_queryset(self) -> QuerySet[PharmacyProduct]:
        user = cast(User, self.request.user)
        qs = PharmacyProduct.objects.select_related("product", "organization").filter(
            organization__in=organizations_visible_to(user)
        )
        org = self.request.query_params.get("organization")
        if org:
            qs = qs.filter(organization_id=org)
        return qs

    def _guard(self, serializer: BaseSerializer[Any]) -> Any:
        user = cast(User, self.request.user)
        org = serializer.validated_data.get("organization")
        if org and not organizations_visible_to(user).filter(pk=org.pk).exists():
            raise PermissionDenied("You cannot manage stock for that organization.")
        return org

    def _audit(self, action: str, obj: PharmacyProduct) -> None:
        record_audit(
            action=action,
            user=cast(User, self.request.user),
            organization=obj.organization,
            entity_type="pharmacy_product",
            entity_id=str(obj.pk),
            request=self.request,
        )

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        self._guard(serializer)
        self._audit("CREATE", serializer.save())

    def perform_update(self, serializer: BaseSerializer[Any]) -> None:
        self._guard(serializer)
        self._audit("UPDATE", serializer.save())

    def perform_destroy(self, instance: PharmacyProduct) -> None:
        self._audit("DELETE", instance)
        instance.delete()


class InventoryBatchViewSet(viewsets.ReadOnlyModelViewSet):
    """Batch stock-on-hand, org-scoped, FEFO-ordered (soonest expiry first)."""

    serializer_class = InventoryBatchSerializer
    queryset = InventoryBatch.objects.select_related("product", "organization").all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self) -> QuerySet[InventoryBatch]:
        user = cast(User, self.request.user)
        qs = InventoryBatch.objects.select_related("product").filter(
            organization__in=organizations_visible_to(user)
        )
        org = self.request.query_params.get("organization")
        if org:
            qs = qs.filter(organization_id=org)
        if self.request.query_params.get("in_stock") == "1":
            qs = qs.filter(quantity_available__gt=0)
        within = self.request.query_params.get("expiring_within")
        if within:
            qs = qs.filter(expiry_date__lte=date.today() + timedelta(days=int(within)))
        return qs

    def _act(self, action_name: str, batch: InventoryBatch, changes: dict[str, object]) -> None:
        record_audit(
            action=action_name,
            user=cast(User, self.request.user),
            organization=batch.organization,
            entity_type="inventory_batch",
            entity_id=str(batch.pk),
            changes=changes,
            request=self.request,
        )

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, CanManageOrg])
    def adjust(self, request: Request, pk: str | None = None) -> Response:
        batch = self.get_object()
        try:
            counted = int(request.data["counted_quantity"])
        except (KeyError, ValueError, TypeError) as exc:
            raise ValidationError({"counted_quantity": "An integer is required."}) from exc
        reason = str(request.data.get("reason", ""))
        try:
            adjust_stock(
                batch=batch, counted_quantity=counted, reason=reason, user=cast(User, request.user)
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        self._act("ADJUSTMENT", batch, {"counted": counted, "reason": reason})
        return Response(InventoryBatchSerializer(batch).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, CanManageOrg])
    def waste(self, request: Request, pk: str | None = None) -> Response:
        batch = self.get_object()
        try:
            qty = int(request.data["quantity"])
        except (KeyError, ValueError, TypeError) as exc:
            raise ValidationError({"quantity": "An integer is required."}) from exc
        reason = str(request.data.get("reason", ""))
        try:
            log_wastage(batch=batch, quantity=qty, reason=reason, user=cast(User, request.user))
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        self._act("WASTAGE", batch, {"quantity": qty, "reason": reason})
        return Response(InventoryBatchSerializer(batch).data)

    @action(detail=True, methods=["get"])
    def putaway_suggestion(self, request: Request, pk: str | None = None) -> Response:
        """Where this lot should go, and the rule that decided it."""
        batch = self.get_object()
        return Response(
            warehouse_services.suggest_putaway(
                organization=batch.organization,
                product=batch.product,
                warehouse=batch.warehouse,
                quantity=batch.quantity_available,
            )
        )

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, CanManageOrg])
    def putaway(self, request: Request, pk: str | None = None) -> Response:
        """Commit the put-away — move the lot into a concrete bin."""
        batch = self.get_object()
        ser = ApplyPutawaySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        bin_location = ser.validated_data["bin_location"]
        if bin_location.zone.organization_id != batch.organization_id:
            raise ValidationError({"bin_location": "That bin belongs to a different organization."})
        batch = warehouse_services.apply_putaway(
            batch=batch, bin_location=bin_location, user=cast(User, request.user)
        )
        self._act("PUTAWAY", batch, {"bin": bin_location.bin_code})
        return Response(InventoryBatchSerializer(batch).data)


class StockMovementViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = StockMovementSerializer
    queryset = StockMovement.objects.select_related("product", "created_by").all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self) -> QuerySet[StockMovement]:
        user = cast(User, self.request.user)
        qs = StockMovement.objects.select_related("product", "created_by").filter(
            organization__in=organizations_visible_to(user)
        )
        org = self.request.query_params.get("organization")
        if org:
            qs = qs.filter(organization_id=org)
        return qs


class IntakeView(APIView):
    permission_classes = [IsAuthenticated, CanManageOrg]

    def post(self, request: Request) -> Response:
        ser = IntakeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        actor = cast(User, request.user)
        if not organizations_visible_to(actor).filter(pk=data["organization"].pk).exists():
            raise PermissionDenied("You cannot receive stock for that organization.")
        if data["organization"].type != "DEPOT":
            raise PermissionDenied(
                "Only depots receive supplier intake. Retail branches get stock via transfers."
            )
        batch = receive_intake(
            organization=data["organization"],
            product=data["product"],
            batch_number=data["batch_number"],
            expiry_date=data["expiry_date"],
            quantity=data["quantity"],
            manufacture_date=data.get("manufacture_date"),
            wholesale_cost=data.get("wholesale_cost"),
            storage_location=data.get("storage_location", ""),
            user=actor,
            source_supplier=data.get("supplier"),
        )
        record_audit(
            action="INTAKE",
            user=actor,
            organization=data["organization"],
            entity_type="inventory_batch",
            entity_id=str(batch.pk),
            changes={"quantity": data["quantity"], "batch": data["batch_number"]},
            request=request,
        )
        return Response(InventoryBatchSerializer(batch).data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Warehouse depth: warehouses, put-away, picking, serialisation, cold-chain
# investigations, and consignment (supplier-owned) stock.
# Each queryset is tenant-scoped through its own path to the owning org.
# ---------------------------------------------------------------------------


class WarehouseViewSet(_AuditedAdminViewSet):
    serializer_class = WarehouseSerializer
    queryset = Warehouse.objects.all()

    def get_queryset(self) -> QuerySet[Warehouse]:
        user = cast(User, self.request.user)
        qs = Warehouse.objects.filter(organization__in=organizations_visible_to(user))
        org = self.request.query_params.get("organization")
        if org:
            qs = qs.filter(organization_id=org)
        return qs

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        _require_org(self.request, serializer.validated_data.get("organization"))
        super().perform_create(serializer)

    @action(detail=True, methods=["get"])
    def occupancy(self, request: Request, pk: str | None = None) -> Response:
        """Bin utilisation and stock value per zone — what the facility is holding."""
        warehouse = self.get_object()
        rows = []
        for zone in warehouse.zones.all():
            bins = zone.bins.all()
            batches = InventoryBatch.objects.filter(
                bin_location__zone=zone, quantity_available__gt=0
            ).select_related("product")
            value = sum((b.wholesale_cost or 0) * b.quantity_available for b in batches)
            total_bins = bins.count()
            occupied = bins.filter(is_occupied=True).count()
            rows.append(
                {
                    "zone": zone.id,
                    "zone_name": zone.name,
                    "zone_type": zone.zone_type,
                    "bins_total": total_bins,
                    "bins_occupied": occupied,
                    "utilisation_percent": (
                        round(occupied * 100 / total_bins, 1) if total_bins else 0.0
                    ),
                    "batches": batches.count(),
                    "units": sum(b.quantity_available for b in batches),
                    "stock_value": f"{value:.2f}",
                }
            )
        return Response({"warehouse": warehouse.id, "name": warehouse.name, "zones": rows})


class PutawayRuleViewSet(_AuditedAdminViewSet):
    serializer_class = PutawayRuleSerializer
    queryset = PutawayRule.objects.all()

    def get_queryset(self) -> QuerySet[PutawayRule]:
        user = cast(User, self.request.user)
        qs = PutawayRule.objects.select_related(
            "warehouse", "target_zone", "target_bin", "match_product"
        ).filter(organization__in=organizations_visible_to(user))
        org = self.request.query_params.get("organization")
        if org:
            qs = qs.filter(organization_id=org)
        return qs

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        _require_org(self.request, serializer.validated_data.get("organization"))
        super().perform_create(serializer)

    @action(detail=False, methods=["get"])
    def simulate(self, request: Request) -> Response:
        """Dry-run the rule set against a product — which rule wins, and which bin."""
        org = _org_from_query(request)
        from apps.catalog.models import Product

        product = Product.objects.filter(pk=lookup_pk(request.query_params.get("product"))).first()
        if product is None:
            raise ValidationError({"product": "Pass ?product=<id>."})
        warehouse = Warehouse.objects.filter(
            pk=lookup_pk(request.query_params.get("warehouse")), organization=org
        ).first()
        return Response(
            warehouse_services.suggest_putaway(
                organization=org,
                product=product,
                warehouse=warehouse,
                quantity=int(request.query_params.get("quantity", 0)),
            )
        )


class ReorderRuleViewSet(_AuditedAdminViewSet):
    serializer_class = ReorderRuleSerializer
    queryset = ReorderRule.objects.all()

    def get_queryset(self) -> QuerySet[ReorderRule]:
        user = cast(User, self.request.user)
        qs = ReorderRule.objects.select_related("product", "preferred_supplier").filter(
            organization__in=organizations_visible_to(user)
        )
        params = self.request.query_params
        if params.get("organization"):
            qs = qs.filter(organization_id=params["organization"])
        if params.get("abc_class"):
            qs = qs.filter(abc_class=params["abc_class"])
        return qs

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        _require_org(self.request, serializer.validated_data.get("organization"))
        super().perform_create(serializer)

    @action(detail=False, methods=["post"], permission_classes=[IsAuthenticated, CanManageOrg])
    def recompute(self, request: Request) -> Response:
        """Refresh demand stats, ABC/XYZ and the reorder levers from movement history."""
        org = _require_org(
            request,
            Organization.objects.filter(pk=lookup_pk(request.data.get("organization"))).first(),
        )
        result = analytics.recompute_reorder_rules(org, days=int(request.data.get("days", 90)))
        record_audit(
            action="REORDER_RECOMPUTE",
            user=cast(User, request.user),
            organization=org,
            entity_type="reorder_rule",
            entity_id="",
            changes=result,
            request=request,
        )
        return Response(result)

    @action(detail=False, methods=["get"])
    def suggestions(self, request: Request) -> Response:
        """Everything at or below its reorder point, with the quantity to buy."""
        return Response(analytics.suggested_orders(_org_from_query(request)))

    @action(detail=False, methods=["get"])
    def abc_xyz(self, request: Request) -> Response:
        """The 3x3 ABC/XYZ grid — counts and stock value in each cell."""
        return Response(analytics.abc_xyz_matrix(_org_from_query(request)))

    @action(detail=False, methods=["get"])
    def slow_dead(self, request: Request) -> Response:
        """Batches that have not moved, with the capital they are tying up."""
        return Response(
            analytics.slow_and_dead_stock(
                _org_from_query(request),
                slow_days=int(request.query_params.get("slow_days", 90)),
                dead_days=int(request.query_params.get("dead_days", 180)),
            )
        )

    @action(detail=False, methods=["get"])
    def near_expiry(self, request: Request) -> Response:
        """Batches approaching expiry, each with the action still open to it."""
        return Response(
            analytics.near_expiry_actions(
                _org_from_query(request),
                horizon_days=int(request.query_params.get("horizon_days", 180)),
            )
        )


class PickWaveViewSet(_AuditedAdminViewSet):
    serializer_class = PickWaveSerializer
    queryset = PickWave.objects.all()

    def get_queryset(self) -> QuerySet[PickWave]:
        user = cast(User, self.request.user)
        qs = PickWave.objects.select_related("warehouse", "zone", "assigned_to").filter(
            organization__in=organizations_visible_to(user)
        )
        params = self.request.query_params
        if params.get("organization"):
            qs = qs.filter(organization_id=params["organization"])
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        return qs

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        _require_org(self.request, serializer.validated_data.get("organization"))
        obj = serializer.save(created_by=cast(User, self.request.user))
        record_audit(
            action="CREATE",
            user=cast(User, self.request.user),
            organization=obj.organization,
            entity_type="pick_wave",
            entity_id=str(obj.pk),
            request=self.request,
        )

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, CanManageOrg])
    def build_tasks(self, request: Request, pk: str | None = None) -> Response:
        """Turn demand lines into FEFO pick tasks, ordered along the picker's walk."""
        wave = self.get_object()
        ser = BuildTasksSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            warehouse_services.build_pick_tasks(
                wave=wave,
                demands=[dict(d) for d in ser.validated_data["demands"]],
                user=cast(User, request.user),
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        wave.refresh_from_db()
        return Response(PickWaveSerializer(wave).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, CanManageOrg])
    def release(self, request: Request, pk: str | None = None) -> Response:
        """Release to the floor, reserving each task's stock as it goes."""
        wave = self.get_object()
        try:
            wave = warehouse_services.release_wave(wave=wave, user=cast(User, request.user))
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        record_audit(
            action="WAVE_RELEASED",
            user=cast(User, request.user),
            organization=wave.organization,
            entity_type="pick_wave",
            entity_id=str(wave.pk),
            request=request,
        )
        return Response(PickWaveSerializer(wave).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, CanManageOrg])
    def cancel(self, request: Request, pk: str | None = None) -> Response:
        """Cancel the wave and hand every un-picked reservation back to free stock."""
        wave = self.get_object()
        try:
            wave = warehouse_services.cancel_wave(wave=wave, user=cast(User, request.user))
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        record_audit(
            action="WAVE_CANCELLED",
            user=cast(User, request.user),
            organization=wave.organization,
            entity_type="pick_wave",
            entity_id=str(wave.pk),
            request=request,
        )
        return Response(PickWaveSerializer(wave).data)


class PickTaskViewSet(_AuditedAdminViewSet):
    serializer_class = PickTaskSerializer
    queryset = PickTask.objects.all()

    def get_queryset(self) -> QuerySet[PickTask]:
        user = cast(User, self.request.user)
        qs = PickTask.objects.select_related(
            "product", "batch", "zone", "bin_location", "picker"
        ).filter(wave__organization__in=organizations_visible_to(user))
        params = self.request.query_params
        if params.get("wave"):
            qs = qs.filter(wave_id=lookup_pk(params["wave"]))
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        if params.get("mine") == "1":
            qs = qs.filter(picker=user)
        return qs

    @action(detail=True, methods=["post"])
    def confirm(self, request: Request, pk: str | None = None) -> Response:
        """Confirm what actually came off the shelf; a short pick is recorded as short."""
        task = self.get_object()
        ser = ConfirmPickSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            task = warehouse_services.confirm_pick(
                task=task,
                quantity_picked=ser.validated_data["quantity_picked"],
                user=cast(User, request.user),
                short_reason=ser.validated_data.get("short_reason", ""),
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(PickTaskSerializer(task).data)


class SerialUnitViewSet(_AuditedAdminViewSet):
    """Serialised units are created by scanning, not by posting a form."""

    serializer_class = SerialUnitSerializer
    queryset = SerialUnit.objects.all()
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self) -> QuerySet[SerialUnit]:
        user = cast(User, self.request.user)
        qs = SerialUnit.objects.select_related("product", "parent", "current_bin").filter(
            organization__in=organizations_visible_to(user)
        )
        params = self.request.query_params
        if params.get("organization"):
            qs = qs.filter(organization_id=params["organization"])
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        if params.get("level"):
            qs = qs.filter(level=params["level"])
        if params.get("batch_number"):
            qs = qs.filter(batch_number=params["batch_number"])
        if params.get("search"):
            term = params["search"]
            qs = qs.filter(
                Q(epc__icontains=term)
                | Q(serial__icontains=term)
                | Q(sscc__icontains=term)
                | Q(gtin__icontains=term)
                | Q(batch_number__icontains=term)
            )
        return qs

    @action(detail=False, methods=["post"], permission_classes=[IsAuthenticated, CanManageOrg])
    def scan(self, request: Request) -> Response:
        """Parse a scanned DataMatrix and commission (or re-find) the unit it names."""
        ser = ScanSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        org = _require_org(request, data["organization"])
        try:
            unit, parsed, created = serialisation.commission_from_scan(
                organization=org,
                scan=data["scan"],
                product=data.get("product"),
                batch=data.get("batch"),
                user=cast(User, request.user),
                read_point=data.get("read_point", ""),
            )
        except ValueError as exc:
            raise ValidationError({"scan": str(exc)}) from exc
        payload = {
            "unit": SerialUnitSerializer(unit).data,
            "parsed": {
                k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in parsed.items()
            },
            "created": created,
        }
        return Response(payload, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=False, methods=["post"])
    def parse(self, request: Request) -> Response:
        """Decode a barcode without touching stock — the 'what is this?' button."""
        raw = str(request.data.get("scan", ""))
        if not raw:
            raise ValidationError({"scan": "Nothing was scanned."})
        try:
            parsed = gs1.parse_gs1(raw)
        except ValueError as exc:
            raise ValidationError({"scan": str(exc)}) from exc
        return Response(
            {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in parsed.items()}
        )

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, CanManageOrg])
    def aggregate(self, request: Request, pk: str | None = None) -> Response:
        """Pack the named units into this one (each -> case -> pallet)."""
        parent = self.get_object()
        ser = AggregateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            parent = serialisation.aggregate(
                parent=parent,
                children=list(ser.validated_data["children"]),
                user=cast(User, request.user),
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(SerialUnitSerializer(parent).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, CanManageOrg])
    def disaggregate(self, request: Request, pk: str | None = None) -> Response:
        """Unpack — all children, or only the named ones."""
        parent = self.get_object()
        ser = DisaggregateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        children = ser.validated_data.get("children")
        parent = serialisation.disaggregate(
            parent=parent,
            children=list(children) if children else None,
            user=cast(User, request.user),
        )
        return Response(SerialUnitSerializer(parent).data)

    @action(detail=False, methods=["post"], permission_classes=[IsAuthenticated, CanManageOrg])
    def observe(self, request: Request) -> Response:
        """Record a business step (ship / receive / dispense / hold) against units."""
        ser = ObserveSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        units = list(data["units"])
        visible = organizations_visible_to(cast(User, request.user))
        for unit in units:
            if not visible.filter(pk=unit.organization_id).exists():
                raise PermissionDenied("One of those units belongs to another organization.")
        updated = serialisation.observe(
            units=units,
            biz_step=data["biz_step"],
            user=cast(User, request.user),
            read_point=data.get("read_point", ""),
            reference_type=data.get("reference_type", ""),
            reference_id=data.get("reference_id", ""),
            cascade=data.get("cascade", True),
        )
        return Response(SerialUnitSerializer(updated, many=True).data)

    @action(detail=True, methods=["get"])
    def trace(self, request: Request, pk: str | None = None) -> Response:
        """Full chain-of-custody: identity, parents, children, every event."""
        return Response(serialisation.trace(self.get_object()))


class EpcisEventViewSet(viewsets.ReadOnlyModelViewSet):
    """EPCIS events are an evidentiary record — readable and exportable, never edited."""

    serializer_class = EpcisEventSerializer
    queryset = EpcisEvent.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self) -> QuerySet[EpcisEvent]:
        user = cast(User, self.request.user)
        qs = EpcisEvent.objects.filter(organization__in=organizations_visible_to(user))
        params = self.request.query_params
        if params.get("organization"):
            qs = qs.filter(organization_id=params["organization"])
        if params.get("biz_step"):
            qs = qs.filter(biz_step=params["biz_step"])
        if params.get("event_type"):
            qs = qs.filter(event_type=params["event_type"])
        if params.get("since"):
            qs = qs.filter(event_time__gte=params["since"])
        return qs

    @action(detail=False, methods=["get"])
    def export(self, request: Request) -> Response:
        """EPCIS 2.0 JSON-LD document for a regulator or trading partner."""
        org = _org_from_query(request)
        events = self.get_queryset().filter(organization=org).order_by("event_time")
        limit = int(request.query_params.get("limit", 1000))
        return Response(gs1.build_epcis_document(events[:limit], sender=org.name))


class SensorCalibrationViewSet(_AuditedAdminViewSet):
    serializer_class = SensorCalibrationSerializer
    queryset = SensorCalibration.objects.all()

    def get_queryset(self) -> QuerySet[SensorCalibration]:
        user = cast(User, self.request.user)
        qs = SensorCalibration.objects.select_related("sensor").filter(
            sensor__organization__in=organizations_visible_to(user)
        )
        if self.request.query_params.get("sensor"):
            qs = qs.filter(sensor_id=lookup_pk(self.request.query_params["sensor"]))
        return qs

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        serializer.save(recorded_by=cast(User, self.request.user))


class ExcursionInvestigationViewSet(_AuditedAdminViewSet):
    serializer_class = ExcursionInvestigationSerializer
    queryset = ExcursionInvestigation.objects.all()

    def get_queryset(self) -> QuerySet[ExcursionInvestigation]:
        user = cast(User, self.request.user)
        qs = ExcursionInvestigation.objects.select_related("sensor", "zone").filter(
            organization__in=organizations_visible_to(user)
        )
        params = self.request.query_params
        if params.get("organization"):
            qs = qs.filter(organization_id=params["organization"])
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        return qs

    @action(detail=False, methods=["post"], permission_classes=[IsAuthenticated, CanManageOrg])
    def open_from_window(self, request: Request) -> Response:
        """Open an investigation over a time window, populated from the sensor log."""
        ser = OpenInvestigationSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = dict(ser.validated_data)
        org = _require_org(request, data.pop("organization"))
        reference_no = data.pop("reference_no", "") or f"EXC-{timezone.now():%Y%m%d-%H%M%S}"
        try:
            investigation = coldchain.open_investigation(
                organization=org,
                reference_no=reference_no,
                user=cast(User, request.user),
                **data,
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        record_audit(
            action="EXCURSION_OPENED",
            user=cast(User, request.user),
            organization=org,
            entity_type="excursion_investigation",
            entity_id=str(investigation.pk),
            changes={
                "reference_no": investigation.reference_no,
                "severity": investigation.severity,
                "affected_batches": investigation.affected_batches.count(),
            },
            request=request,
        )
        return Response(
            ExcursionInvestigationSerializer(investigation).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, CanManageOrg])
    def close(self, request: Request, pk: str | None = None) -> Response:
        """Apply QA's disposition to the affected lots and close the record."""
        investigation = self.get_object()
        ser = CloseInvestigationSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            investigation = coldchain.close_investigation(
                investigation=investigation,
                user=cast(User, request.user),
                **ser.validated_data,
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        record_audit(
            action="EXCURSION_CLOSED",
            user=cast(User, request.user),
            organization=investigation.organization,
            entity_type="excursion_investigation",
            entity_id=str(investigation.pk),
            changes={"disposition": investigation.disposition},
            request=request,
        )
        return Response(ExcursionInvestigationSerializer(investigation).data)


class ConsignmentAgreementViewSet(_AuditedAdminViewSet):
    """Supplier-owned stock held on our shelves: ownership only transfers on use."""

    serializer_class = ConsignmentAgreementSerializer
    queryset = ConsignmentAgreement.objects.all()

    def get_queryset(self) -> QuerySet[ConsignmentAgreement]:
        user = cast(User, self.request.user)
        qs = ConsignmentAgreement.objects.select_related(
            "owner_supplier", "holder_organization"
        ).filter(organization__in=organizations_visible_to(user))
        params = self.request.query_params
        if params.get("organization"):
            qs = qs.filter(organization_id=params["organization"])
        if params.get("direction"):
            qs = qs.filter(direction=params["direction"])
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        return qs

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        _require_org(self.request, serializer.validated_data.get("organization"))
        obj = serializer.save(created_by=cast(User, self.request.user))
        record_audit(
            action="CREATE",
            user=cast(User, self.request.user),
            organization=obj.organization,
            entity_type="consignment_agreement",
            entity_id=str(obj.pk),
            request=self.request,
        )

    @action(detail=True, methods=["get"])
    def position(self, request: Request, pk: str | None = None) -> Response:
        """Stock held under the agreement plus the unsettled liability."""
        return Response(warehouse_services.consignment_position(self.get_object()))

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, CanManageOrg])
    def settle(self, request: Request, pk: str | None = None) -> Response:
        """Roll a period's consumptions into a settlement (and an AP bill if owed)."""
        agreement = self.get_object()
        ser = SettleConsignmentSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        settlement_no = (
            data.get("settlement_no") or f"CS-{agreement.agreement_no}-{data['period_end']:%Y%m}"
        )
        try:
            settlement = warehouse_services.settle_consignment(
                agreement=agreement,
                settlement_no=settlement_no,
                period_start=data["period_start"],
                period_end=data["period_end"],
                raise_bill=data.get("raise_bill", True),
                user=cast(User, request.user),
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        record_audit(
            action="CONSIGNMENT_SETTLED",
            user=cast(User, request.user),
            organization=agreement.organization,
            entity_type="consignment_settlement",
            entity_id=str(settlement.pk),
            changes={
                "settlement_no": settlement.settlement_no,
                "total_value": str(settlement.total_value),
            },
            request=request,
        )
        return Response(
            ConsignmentSettlementSerializer(settlement).data, status=status.HTTP_201_CREATED
        )


class ConsignmentConsumptionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ConsignmentConsumptionSerializer
    queryset = ConsignmentConsumption.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self) -> QuerySet[ConsignmentConsumption]:
        user = cast(User, self.request.user)
        qs = ConsignmentConsumption.objects.select_related("product", "agreement").filter(
            agreement__organization__in=organizations_visible_to(user)
        )
        params = self.request.query_params
        if params.get("agreement"):
            qs = qs.filter(agreement_id=lookup_pk(params["agreement"]))
        if params.get("unsettled") == "1":
            qs = qs.filter(settlement__isnull=True)
        return qs


class ConsignmentSettlementViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ConsignmentSettlementSerializer
    queryset = ConsignmentSettlement.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self) -> QuerySet[ConsignmentSettlement]:
        user = cast(User, self.request.user)
        qs = ConsignmentSettlement.objects.select_related("agreement", "supplier_bill").filter(
            agreement__organization__in=organizations_visible_to(user)
        )
        if self.request.query_params.get("agreement"):
            qs = qs.filter(agreement_id=lookup_pk(self.request.query_params["agreement"]))
        return qs
