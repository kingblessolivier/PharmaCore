"""Cold-chain rigour: the calibration register and excursion investigations.

Detecting an excursion is the easy half. The regulated half is what happens next —
bound the window, quantify the exposure (min/max **and** mean kinetic temperature),
name the lots that were in the room, find the cause, and have QA sign a disposition.
Closing the investigation is what actually applies that decision to stock, so
product can never quietly go back on sale after an excursion nobody signed off.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.iam.models import User
from apps.inventory.analytics import mean_kinetic_temperature
from apps.inventory.models import (
    ExcursionInvestigation,
    InventoryBatch,
    SensorCalibration,
    StorageZone,
    TemperatureLog,
    TemperatureSensor,
)


@transaction.atomic
def record_calibration(
    *,
    sensor: TemperatureSensor,
    certificate_no: str,
    calibrated_on: Any,
    next_due_on: Any = None,
    calibrated_by: str = "",
    deviation_celsius: Decimal | None = None,
    accuracy_celsius: Decimal | None = None,
    result: str = SensorCalibration.Result.PASS,
    reference_standard: str = "",
    certificate_url: str = "",
    notes: str = "",
    user: User | None = None,
) -> SensorCalibration:
    """File a calibration certificate and roll the sensor's due date forward.

    A ``FAIL`` deliberately does *not* extend the due date and deactivates the
    device: a probe that failed its check is not a measuring instrument, and its
    readings should stop feeding excursion logic until it is fixed or replaced.
    """
    if next_due_on is None:
        months = sensor.calibration_interval_months or 12
        next_due_on = calibrated_on + timedelta(days=int(months * 30.44))

    calibration = SensorCalibration.objects.create(
        sensor=sensor,
        certificate_no=certificate_no,
        calibrated_on=calibrated_on,
        next_due_on=next_due_on,
        calibrated_by=calibrated_by,
        deviation_celsius=deviation_celsius,
        accuracy_celsius=accuracy_celsius,
        result=result,
        reference_standard=reference_standard,
        certificate_url=certificate_url,
        notes=notes,
        recorded_by=user,
    )

    if result == SensorCalibration.Result.FAIL:
        sensor.is_active = False
        sensor.save(update_fields=["is_active"])
    else:
        sensor.last_calibration_date = calibrated_on
        sensor.calibration_due_date = next_due_on
        if accuracy_celsius is not None:
            sensor.accuracy_celsius = accuracy_celsius
        sensor.is_active = True
        sensor.save(
            update_fields=[
                "last_calibration_date",
                "calibration_due_date",
                "accuracy_celsius",
                "is_active",
            ]
        )
    return calibration


def _severity_for(
    zone: StorageZone | None, min_temp: float | None, max_temp: float | None, minutes: int
) -> str:
    """Grade the excursion by how far outside the label range it went, and for how long."""
    if zone is None or min_temp is None or max_temp is None:
        return ExcursionInvestigation.Severity.MINOR
    low, high = float(zone.temp_min_celsius), float(zone.temp_max_celsius)
    overshoot = max(max_temp - high, low - min_temp, 0.0)
    if overshoot >= 10 or minutes >= 24 * 60:
        return ExcursionInvestigation.Severity.CRITICAL
    if overshoot >= 3 or minutes >= 4 * 60:
        return ExcursionInvestigation.Severity.MAJOR
    return ExcursionInvestigation.Severity.MINOR


@transaction.atomic
def open_investigation(
    *,
    organization: Any,
    reference_no: str,
    started_at: Any,
    ended_at: Any = None,
    sensor: TemperatureSensor | None = None,
    zone: StorageZone | None = None,
    user: User | None = None,
    auto_quarantine: bool = True,
) -> ExcursionInvestigation:
    """Open an investigation over a time window and populate it from the log.

    The readings in the window give min/max/MKT and the reading count; every ACTIVE
    lot sitting in the affected zone is attached as potentially affected. With
    ``auto_quarantine`` those lots are held immediately — the safe default, because
    stock must stop moving while its fitness is unknown, not after the paperwork.
    """
    zone = zone or (sensor.zone if sensor else None)
    ended_at = ended_at or timezone.now()

    logs = TemperatureLog.objects.filter(recorded_at__gte=started_at, recorded_at__lte=ended_at)
    if sensor is not None:
        logs = logs.filter(sensor=sensor)
    elif zone is not None:
        logs = logs.filter(sensor__zone=zone)

    temps = [float(t) for t in logs.values_list("temperature_celsius", flat=True)]
    minutes = int((ended_at - started_at).total_seconds() // 60)
    mkt = mean_kinetic_temperature(temps)

    investigation = ExcursionInvestigation.objects.create(
        organization=organization,
        reference_no=reference_no,
        sensor=sensor,
        zone=zone,
        started_at=started_at,
        ended_at=ended_at,
        duration_minutes=max(minutes, 0),
        min_temp_celsius=Decimal(str(round(min(temps), 2))) if temps else None,
        max_temp_celsius=Decimal(str(round(max(temps), 2))) if temps else None,
        mkt_celsius=Decimal(str(mkt)) if mkt is not None else None,
        readings_count=len(temps),
        severity=_severity_for(zone, min(temps) if temps else None, max(temps) if temps else None, minutes),
        opened_by=user,
    )

    if zone is not None:
        affected = InventoryBatch.objects.filter(
            organization=organization,
            bin_location__zone=zone,
            quantity_available__gt=0,
        ).exclude(status=InventoryBatch.Status.RECALLED)
        investigation.affected_batches.set(affected)
        if auto_quarantine:
            affected.update(status=InventoryBatch.Status.QUARANTINE)
    return investigation


@transaction.atomic
def close_investigation(
    *,
    investigation: ExcursionInvestigation,
    disposition: str,
    rationale: str = "",
    root_cause: str = "",
    corrective_action: str = "",
    impact_assessment: str = "",
    user: User | None = None,
) -> ExcursionInvestigation:
    """Apply QA's decision to the affected lots and close the record.

    ``RELEASE`` returns lots to ACTIVE; ``QUARANTINE`` holds them; ``DESTROY`` and
    ``RETURN_TO_SUPPLIER`` both take them out of sellable stock (destruction itself
    still runs through the witnessed :class:`StockDisposal` flow, which is where
    the certificate and the two signatures live).
    """
    if disposition == ExcursionInvestigation.Disposition.PENDING:
        raise ValueError("Choose a disposition before closing the investigation.")
    if investigation.status == ExcursionInvestigation.Status.CLOSED:
        raise ValueError("This investigation is already closed.")
    if not rationale.strip():
        raise ValueError("A disposition rationale is required — QA must say why.")

    target_status = {
        ExcursionInvestigation.Disposition.RELEASE: InventoryBatch.Status.ACTIVE,
        ExcursionInvestigation.Disposition.QUARANTINE: InventoryBatch.Status.QUARANTINE,
        ExcursionInvestigation.Disposition.DESTROY: InventoryBatch.Status.QUARANTINE,
        ExcursionInvestigation.Disposition.RETURN_TO_SUPPLIER: InventoryBatch.Status.QUARANTINE,
    }[disposition]
    investigation.affected_batches.all().update(status=target_status)

    investigation.disposition = disposition
    investigation.disposition_rationale = rationale
    investigation.root_cause = root_cause or investigation.root_cause
    investigation.corrective_action = corrective_action or investigation.corrective_action
    investigation.impact_assessment = impact_assessment or investigation.impact_assessment
    investigation.status = ExcursionInvestigation.Status.CLOSED
    investigation.qa_approver = user
    investigation.closed_at = timezone.now()
    investigation.save()
    return investigation


def calibration_register(organization: Any) -> list[dict[str, Any]]:
    """The register an inspector asks for: every device and whether it is in date."""
    rows: list[dict[str, Any]] = []
    sensors = (
        TemperatureSensor.objects.filter(organization=organization)
        .select_related("zone")
        .prefetch_related("calibrations")
    )
    for sensor in sensors:
        latest = sensor.calibrations.first()
        rows.append(
            {
                "sensor": sensor.id,
                "name": sensor.name,
                "device_id": sensor.device_id,
                "device_type": sensor.device_type,
                "manufacturer": sensor.manufacturer,
                "model_number": sensor.model_number,
                "serial_number": sensor.serial_number,
                "zone": sensor.zone_id,
                "zone_name": sensor.zone.name,
                "accuracy_celsius": str(sensor.accuracy_celsius) if sensor.accuracy_celsius else None,
                "last_calibration_date": (
                    sensor.last_calibration_date.isoformat()
                    if sensor.last_calibration_date
                    else None
                ),
                "calibration_due_date": (
                    sensor.calibration_due_date.isoformat()
                    if sensor.calibration_due_date
                    else None
                ),
                "calibration_state": sensor.calibration_state,
                "latest_certificate_no": latest.certificate_no if latest else None,
                "latest_result": latest.result if latest else None,
                "calibrations_count": sensor.calibrations.count(),
                "is_active": sensor.is_active,
            }
        )
    rows.sort(key=lambda r: {"OVERDUE": 0, "DUE_SOON": 1, "UNKNOWN": 2, "VALID": 3}[
        r["calibration_state"]
    ])
    return rows
