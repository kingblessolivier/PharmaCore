"""Inventory API: per-pharmacy product listing, batch stock, storage zones, bins,
temperature logs, QA checks, batch recalls, physical stock counts, and witness disposal.

Org-scoped; reads for any authed user in the org, writes admin/manager-only and audited.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, cast

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView

from apps.iam.audit import record_audit
from apps.iam.models import User
from apps.iam.permissions import CanManageOrg
from apps.iam.scoping import organizations_visible_to
from apps.inventory.models import (
    BatchRecall,
    BinLocation,
    InventoryBatch,
    PharmacyProduct,
    QualityCheck,
    StockCount,
    StockCountItem,
    StockDisposal,
    StockMovement,
    StorageZone,
    TemperatureLog,
    TemperatureSensor,
)
from apps.inventory.serializers import (
    BatchRecallSerializer,
    BinLocationSerializer,
    IntakeSerializer,
    InventoryBatchSerializer,
    PharmacyProductSerializer,
    QualityCheckSerializer,
    StockCountSerializer,
    StockDisposalSerializer,
    StockMovementSerializer,
    StorageZoneSerializer,
    TemperatureLogSerializer,
    TemperatureSensorSerializer,
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
        org = getattr(obj, "organization", None) or getattr(getattr(obj, "zone", None), "organization", None)
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
        org = getattr(obj, "organization", None) or getattr(getattr(obj, "zone", None), "organization", None)
        record_audit(
            action="UPDATE",
            user=cast(User, self.request.user),
            organization=org,
            entity_type=obj._meta.model_name,
            entity_id=str(obj.pk),
            request=self.request,
        )

    def perform_destroy(self, instance: Any) -> None:
        org = getattr(instance, "organization", None) or getattr(getattr(instance, "zone", None), "organization", None)
        record_audit(
            action="DELETE",
            user=cast(User, self.request.user),
            organization=org,
            entity_type=instance._meta.model_name,
            entity_id=str(instance.pk),
            request=self.request,
        )
        instance.delete()


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
        return TemperatureSensor.objects.filter(organization__in=organizations_visible_to(user))


class TemperatureLogViewSet(_AuditedAdminViewSet):
    serializer_class = TemperatureLogSerializer
    queryset = TemperatureLog.objects.all()

    def get_queryset(self) -> QuerySet[TemperatureLog]:
        user = cast(User, self.request.user)
        return TemperatureLog.objects.filter(sensor__organization__in=organizations_visible_to(user))


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
