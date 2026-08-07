"""Warehouse & supply-chain intelligence: GS1 serialisation, EPCIS, cold-chain
calibration/excursions, replenishment analytics, put-away, wave picking and
consignment/VMI.

The service layer is tested directly (that is where the invariants live) and each
subsystem also gets an API pass, because an engine nobody can reach is not a feature.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from apps.catalog.models import Product, Supplier
from apps.iam.models import Organization, Role, User
from apps.inventory import analytics, coldchain, gs1, serialisation, warehouse_services
from apps.inventory.models import (
    BinLocation,
    ConsignmentAgreement,
    ConsignmentSettlement,
    EpcisEvent,
    ExcursionInvestigation,
    InventoryBatch,
    PickTask,
    PickWave,
    PutawayRule,
    ReorderRule,
    SensorCalibration,
    SerialUnit,
    StockMovement,
    StorageZone,
    TemperatureLog,
    TemperatureSensor,
    Warehouse,
)
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient


def _auth(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def wh(db):
    org = Organization.objects.create(name="Kigali Central Depot", type="DEPOT")
    user = User.objects.create_user(
        username="wh_lead", email="lead@medlink.rw", password="Password123!"
    )
    user.organization = org
    user.roles.add(Role.objects.get(code="SYS_ADMIN"))
    user.save()

    warehouse = Warehouse.objects.create(
        organization=org, code="WH1", name="Main Store", is_default=True
    )
    ambient = StorageZone.objects.create(
        organization=org, warehouse=warehouse, name="Ambient A", zone_type="AMBIENT"
    )
    cold = StorageZone.objects.create(
        organization=org,
        warehouse=warehouse,
        name="Cold Room",
        zone_type="COLD_CHAIN",
        temp_min_celsius=Decimal("2.00"),
        temp_max_celsius=Decimal("8.00"),
    )
    bin_a = BinLocation.objects.create(zone=ambient, aisle="A", shelf="01", bin_code="A-01-01")
    bin_c = BinLocation.objects.create(zone=cold, aisle="C", shelf="01", bin_code="C-01-01")

    # GTIN 05012345678900 carries a valid mod-10 check digit.
    amox = Product.objects.create(
        generic_name="Amoxicillin",
        dosage_form="Capsule",
        strength="500mg",
        gtin="05012345678900",
    )
    vaccine = Product.objects.create(
        generic_name="Measles Vaccine",
        dosage_form="Injection",
        strength="0.5ml",
        storage_condition="COLD_CHAIN",
        max_temp_c=Decimal("8.0"),
    )
    supplier = Supplier.objects.create(name="Rwanda Pharma Ltd")
    return {
        "org": org,
        "user": user,
        "warehouse": warehouse,
        "ambient": ambient,
        "cold": cold,
        "bin_a": bin_a,
        "bin_c": bin_c,
        "amox": amox,
        "vaccine": vaccine,
        "supplier": supplier,
    }


def _batch(wh, product, *, number, days_to_expiry=365, qty=100, cost="1000.00", **kwargs):
    return InventoryBatch.objects.create(
        organization=wh["org"],
        product=product,
        batch_number=number,
        expiry_date=date.today() + timedelta(days=days_to_expiry),
        quantity_available=qty,
        wholesale_cost=Decimal(cost),
        status=InventoryBatch.Status.ACTIVE,
        **kwargs,
    )


# --- GS1 parsing -----------------------------------------------------------


@pytest.mark.django_db
def test_gs1_parses_element_string_bracketed_and_digital_link_alike():
    """The three shapes a scanner emits must decode to the same four facts."""
    gs = gs1.GROUP_SEPARATOR
    element = "010501234567890017261231" + "10BATCH-A" + gs + "21SER0001"
    bracketed = "(01)05012345678900(17)261231(10)BATCH-A(21)SER0001"
    link = "https://id.gs1.org/01/05012345678900/21/SER0001?17=261231&10=BATCH-A"

    for raw in (element, bracketed, link):
        parsed = gs1.parse_gs1(raw)
        assert parsed["gtin"] == "05012345678900"
        assert parsed["batch_number"] == "BATCH-A"
        assert parsed["serial"] == "SER0001"
        assert parsed["expiry_date"] == "2026-12-31"
        assert parsed["is_serialised"] is True
        assert parsed["epc"].startswith("urn:epc:id:sgtin:")


@pytest.mark.django_db
def test_gs1_rejects_a_bad_check_digit_rather_than_storing_it():
    with pytest.raises(gs1.GS1ParseError, match="check digit"):
        gs1.parse_gs1("0105012345678901")


@pytest.mark.django_db
def test_gs1_expiry_day_00_means_end_of_month():
    """AI 17 with DD=00 is 'last day of that month' per the General Specifications."""
    assert gs1.parse_gs1_date("260200") == date(2026, 2, 28)


@pytest.mark.django_db
def test_gs1_symbology_prefix_is_stripped():
    parsed = gs1.parse_gs1("]d20105012345678900" + "21SER9")
    assert parsed["serial"] == "SER9"


# --- Serialisation & EPCIS -------------------------------------------------


@pytest.mark.django_db
def test_commission_from_scan_creates_the_unit_then_recognises_a_rescan(wh):
    scan = "(01)05012345678900(17)271231(10)BATCH-A(21)SER0001"
    unit, parsed, created = serialisation.commission_from_scan(
        organization=wh["org"], scan=scan, user=wh["user"]
    )
    assert created is True
    assert unit.product_id == wh["amox"].id  # resolved from the GTIN
    assert unit.status == SerialUnit.Status.COMMISSIONED
    assert unit.expiry_date == date(2027, 12, 31)
    assert EpcisEvent.objects.filter(biz_step=EpcisEvent.BizStep.COMMISSIONING).count() == 1

    again, _parsed, created_again = serialisation.commission_from_scan(
        organization=wh["org"], scan=scan, user=wh["user"]
    )
    assert created_again is False
    assert again.pk == unit.pk
    assert SerialUnit.objects.count() == 1


@pytest.mark.django_db
def test_a_non_serialised_code_cannot_be_commissioned(wh):
    with pytest.raises(ValueError, match="identifies a product"):
        serialisation.commission_from_scan(
            organization=wh["org"], scan="(01)05012345678900(10)BATCH-A", user=wh["user"]
        )


@pytest.mark.django_db
def test_aggregation_walks_up_the_hierarchy_and_refuses_to_walk_down(wh):
    pallet = SerialUnit.objects.create(
        organization=wh["org"],
        level=SerialUnit.Level.PALLET,
        sscc="106141411234567891",
        epc="urn:epc:id:sscc:0614141.10123456789",
    )
    case = SerialUnit.objects.create(
        organization=wh["org"],
        level=SerialUnit.Level.CASE,
        sscc="206141411234567892",
        epc="urn:epc:id:sscc:0614141.20123456789",
    )
    packs = [
        SerialUnit.objects.create(
            organization=wh["org"],
            product=wh["amox"],
            gtin="05012345678900",
            serial=f"S{i}",
            epc=f"urn:epc:id:sgtin:501234.5678900.S{i}",
        )
        for i in range(3)
    ]

    serialisation.aggregate(parent=case, children=packs, user=wh["user"])
    case.refresh_from_db()
    assert case.quantity == 3
    assert set(case.children.values_list("pk", flat=True)) == {p.pk for p in packs}

    serialisation.aggregate(parent=pallet, children=[case], user=wh["user"])
    assert EpcisEvent.objects.filter(biz_step=EpcisEvent.BizStep.PACKING).count() == 2

    with pytest.raises(ValueError, match="each → case → pallet"):
        serialisation.aggregate(parent=case, children=[pallet], user=wh["user"])
    with pytest.raises(ValueError, match="cannot contain itself"):
        serialisation.aggregate(parent=case, children=[case], user=wh["user"])


@pytest.mark.django_db
def test_observing_a_pallet_cascades_to_every_pack_on_it(wh):
    pallet = SerialUnit.objects.create(
        organization=wh["org"],
        level=SerialUnit.Level.PALLET,
        sscc="106141411234567891",
        epc="urn:epc:id:sscc:0614141.10123456789",
    )
    case = SerialUnit.objects.create(
        organization=wh["org"],
        level=SerialUnit.Level.CASE,
        sscc="206141411234567892",
        epc="urn:epc:id:sscc:0614141.20123456789",
        parent=pallet,
    )
    pack = SerialUnit.objects.create(
        organization=wh["org"],
        product=wh["amox"],
        gtin="05012345678900",
        serial="S1",
        epc="urn:epc:id:sgtin:501234.5678900.S1",
        parent=case,
    )

    serialisation.observe(units=[pallet], biz_step=EpcisEvent.BizStep.SHIPPING, user=wh["user"])
    pack.refresh_from_db()
    case.refresh_from_db()
    assert pack.status == SerialUnit.Status.IN_TRANSIT
    assert case.status == SerialUnit.Status.IN_TRANSIT

    event = EpcisEvent.objects.get(biz_step=EpcisEvent.BizStep.SHIPPING)
    assert event.disposition == EpcisEvent.Disposition.IN_TRANSIT
    assert pack.epc in event.epc_list


@pytest.mark.django_db
def test_trace_returns_the_whole_chain_of_custody(wh):
    unit, _parsed, _created = serialisation.commission_from_scan(
        organization=wh["org"],
        scan="(01)05012345678900(17)271231(10)BATCH-A(21)SER0001",
        user=wh["user"],
    )
    serialisation.observe(units=[unit], biz_step=EpcisEvent.BizStep.RECEIVING, user=wh["user"])
    trace = serialisation.trace(SerialUnit.objects.get(pk=unit.pk))
    assert trace["serial"] == "SER0001"
    assert trace["batch_number"] == "BATCH-A"
    steps = [e["biz_step"] for e in trace["events"]]
    assert steps == [EpcisEvent.BizStep.COMMISSIONING, EpcisEvent.BizStep.RECEIVING]


@pytest.mark.django_db
def test_epcis_events_are_evidentiary_and_cannot_be_rewritten(wh):
    event = serialisation.record_event(
        organization=wh["org"],
        event_type=EpcisEvent.EventType.OBJECT,
        action=EpcisEvent.Action.OBSERVE,
        biz_step=EpcisEvent.BizStep.INSPECTING,
    )
    event.read_point = "somewhere else"
    with pytest.raises(ValueError, match="cannot be modified"):
        event.save()
    with pytest.raises(ValueError, match="cannot be deleted"):
        event.delete()


@pytest.mark.django_db
def test_epcis_export_is_a_valid_2_0_document(wh):
    serialisation.commission_from_scan(
        organization=wh["org"],
        scan="(01)05012345678900(17)271231(10)BATCH-A(21)SER0001",
        user=wh["user"],
    )
    doc = gs1.build_epcis_document(EpcisEvent.objects.all(), sender=wh["org"].name)
    assert doc["type"] == "EPCISDocument"
    assert doc["schemaVersion"] == "2.0"
    body = doc["epcisBody"]["eventList"]
    assert len(body) == 1
    assert body[0]["type"] == "ObjectEvent"
    assert body[0]["bizStep"] == "https://ref.gs1.org/cbv/BizStep-commissioning"


# --- Cold chain: calibration & excursions ----------------------------------


@pytest.mark.django_db
def test_calibration_pass_rolls_the_due_date_forward_and_fail_withdraws_the_probe(wh):
    sensor = TemperatureSensor.objects.create(
        organization=wh["org"],
        zone=wh["cold"],
        device_id="LOG-1",
        name="Cold Room Probe",
        calibration_interval_months=12,
    )
    coldchain.record_calibration(
        sensor=sensor,
        certificate_no="CAL-2026-001",
        calibrated_on=date(2026, 1, 15),
        user=wh["user"],
    )
    sensor.refresh_from_db()
    assert sensor.last_calibration_date == date(2026, 1, 15)
    assert sensor.calibration_due_date == date(2027, 1, 15)
    assert sensor.is_active is True

    coldchain.record_calibration(
        sensor=sensor,
        certificate_no="CAL-2026-002",
        calibrated_on=date(2026, 6, 1),
        result=SensorCalibration.Result.FAIL,
        user=wh["user"],
    )
    sensor.refresh_from_db()
    assert sensor.is_active is False, "A probe that failed its check is not a measuring instrument"
    assert sensor.calibration_due_date == date(2027, 1, 15), "A fail must not extend the due date"


@pytest.mark.django_db
def test_calibration_state_reports_what_an_inspector_asks_for(wh):
    sensor = TemperatureSensor.objects.create(
        organization=wh["org"], zone=wh["cold"], device_id="LOG-2", name="Probe 2"
    )
    assert sensor.calibration_state == "UNKNOWN"
    sensor.calibration_due_date = date.today() - timedelta(days=1)
    assert sensor.calibration_state == "OVERDUE"
    sensor.calibration_due_date = date.today() + timedelta(days=10)
    assert sensor.calibration_state == "DUE_SOON"
    sensor.calibration_due_date = date.today() + timedelta(days=200)
    assert sensor.calibration_state == "VALID"


@pytest.mark.django_db
def test_mean_kinetic_temperature_exceeds_the_arithmetic_mean(wh):
    """MKT is Arrhenius-weighted, so a spike counts for more than it does in an average."""
    mkt = analytics.mean_kinetic_temperature([4.0, 4.0, 4.0, 25.0])
    assert mkt is not None
    assert mkt > sum([4.0, 4.0, 4.0, 25.0]) / 4


@pytest.mark.django_db
def test_excursion_investigation_quarantines_then_the_disposition_decides(wh):
    sensor = TemperatureSensor.objects.create(
        organization=wh["org"], zone=wh["cold"], device_id="LOG-3", name="Cold Probe"
    )
    batch = _batch(wh, wh["vaccine"], number="VAX-01", bin_location=wh["bin_c"])
    start = timezone.now() - timedelta(hours=3)
    for offset, temp in enumerate([4.0, 14.5, 16.0, 5.0]):
        TemperatureLog.objects.create(
            sensor=sensor,
            temperature_celsius=Decimal(str(temp)),
            recorded_at=start + timedelta(minutes=30 * offset),
        )

    investigation = coldchain.open_investigation(
        organization=wh["org"],
        reference_no="EXC-001",
        started_at=start,
        ended_at=timezone.now(),
        sensor=sensor,
        user=wh["user"],
    )
    assert investigation.readings_count == 4
    assert investigation.max_temp_celsius == Decimal("16.00")
    assert investigation.mkt_celsius is not None
    assert batch in investigation.affected_batches.all()

    batch.refresh_from_db()
    assert batch.status == InventoryBatch.Status.QUARANTINE, "Stock stops while fitness is unknown"

    coldchain.close_investigation(
        investigation=investigation,
        disposition=ExcursionInvestigation.Disposition.RELEASE,
        rationale="Within the manufacturer's stability data for a 90-minute excursion.",
        user=wh["user"],
    )
    batch.refresh_from_db()
    investigation.refresh_from_db()
    assert batch.status == InventoryBatch.Status.ACTIVE
    assert investigation.status == ExcursionInvestigation.Status.CLOSED
    assert investigation.qa_approver_id == wh["user"].id


@pytest.mark.django_db
def test_an_investigation_cannot_be_closed_without_a_decision(wh):
    investigation = ExcursionInvestigation.objects.create(
        organization=wh["org"], reference_no="EXC-002", started_at=timezone.now()
    )
    with pytest.raises(ValueError):
        coldchain.close_investigation(
            investigation=investigation,
            disposition=ExcursionInvestigation.Disposition.PENDING,
            user=wh["user"],
        )


# --- Replenishment analytics ----------------------------------------------


def _sell(wh, product, batch, *, units, days_ago):
    movement = StockMovement.objects.create(
        organization=wh["org"],
        product=product,
        batch=batch,
        batch_number=batch.batch_number,
        movement_type=StockMovement.Type.SALE,
        quantity_delta=-units,
    )
    StockMovement.objects.filter(pk=movement.pk).update(
        occurred_at=timezone.now() - timedelta(days=days_ago)
    )
    return movement


@pytest.mark.django_db
def test_recompute_sets_reorder_point_from_observed_demand_and_classes(wh):
    batch = _batch(wh, wh["amox"], number="AMX-1", qty=500, cost="2000.00")
    for day in range(1, 61):
        _sell(wh, wh["amox"], batch, units=10, days_ago=day)

    result = analytics.recompute_reorder_rules(wh["org"], days=90)
    assert result["rules_created"] + result["rules_updated"] >= 1

    rule = ReorderRule.objects.get(organization=wh["org"], product=wh["amox"])
    assert rule.avg_daily_demand > 0
    # Lead-time demand (7 days) plus safety stock must clear the raw lead-time cover.
    assert rule.reorder_point >= rule.avg_daily_demand * 7
    assert rule.abc_class == ReorderRule.ABC.A
    assert rule.xyz_class in {ReorderRule.XYZ.X, ReorderRule.XYZ.Y, ReorderRule.XYZ.Z}
    assert rule.last_computed_at is not None


@pytest.mark.django_db
def test_a_hand_set_rule_keeps_its_levers_but_still_gets_fresh_statistics(wh):
    batch = _batch(wh, wh["amox"], number="AMX-2", qty=500)
    for day in range(1, 31):
        _sell(wh, wh["amox"], batch, units=5, days_ago=day)
    rule = ReorderRule.objects.create(
        organization=wh["org"],
        product=wh["amox"],
        reorder_point=999,
        max_level=1234,
        is_auto_calculated=False,
    )

    analytics.recompute_reorder_rules(wh["org"], days=90)
    rule.refresh_from_db()
    assert rule.reorder_point == 999, "A buyer's deliberate override must survive the engine"
    assert rule.max_level == 1234
    assert rule.avg_daily_demand > 0, "…but the observed statistics are still refreshed"


@pytest.mark.django_db
def test_suggested_orders_nets_off_reserved_stock(wh):
    batch = _batch(wh, wh["amox"], number="AMX-3", qty=40)
    ReorderRule.objects.create(
        organization=wh["org"],
        product=wh["amox"],
        reorder_point=50,
        max_level=200,
        reorder_quantity=100,
        is_active=True,
    )
    assert analytics.suggested_orders(wh["org"])[0]["free_stock"] == 40

    batch.quantity_reserved = 15
    batch.save(update_fields=["quantity_reserved"])
    row = analytics.suggested_orders(wh["org"])[0]
    assert row["free_stock"] == 25, "Reserved units are spoken for and are not cover"
    assert row["suggested_quantity"] > 0


@pytest.mark.django_db
def test_abc_xyz_matrix_buckets_every_classified_rule(wh):
    _batch(wh, wh["amox"], number="AMX-4", qty=100)
    ReorderRule.objects.create(
        organization=wh["org"], product=wh["amox"], abc_class="A", xyz_class="X"
    )
    matrix = analytics.abc_xyz_matrix(wh["org"])
    assert matrix["cells"]["AX"]["count"] == 1
    assert matrix["cells"]["AX"]["units"] == 100


@pytest.mark.django_db
def test_never_moved_stock_is_called_out_separately_from_merely_slow(wh):
    _batch(wh, wh["amox"], number="AMX-5", qty=100)
    rows = analytics.slow_and_dead_stock(wh["org"])
    assert rows[0]["category"] == "NEVER_MOVED"
    assert Decimal(rows[0]["capital_tied"]) > 0


@pytest.mark.django_db
def test_near_expiry_action_narrows_as_the_clock_runs(wh):
    _batch(wh, wh["amox"], number="EXP-LATE", days_to_expiry=150, qty=10)
    _batch(wh, wh["amox"], number="EXP-SOON", days_to_expiry=10, qty=10)
    rows = {r["batch_number"]: r for r in analytics.near_expiry_actions(wh["org"])}
    assert set(rows) == {"EXP-LATE", "EXP-SOON"}
    assert rows["EXP-SOON"]["days_to_expiry"] < rows["EXP-LATE"]["days_to_expiry"]
    assert rows["EXP-SOON"]["recommended_action"] != rows["EXP-LATE"]["recommended_action"]


# --- Put-away --------------------------------------------------------------


@pytest.mark.django_db
def test_a_cold_chain_product_is_never_defaulted_onto_an_ambient_shelf(wh):
    """No rule exists — the fallback must still respect the label's storage condition."""
    result = warehouse_services.suggest_putaway(
        organization=wh["org"], product=wh["vaccine"], warehouse=wh["warehouse"], quantity=10
    )
    assert result["zone"] == wh["cold"].id
    assert result["bin_location"] == wh["bin_c"].id
    assert result["required_zone_type"] == StorageZone.ZoneType.COLD_CHAIN


@pytest.mark.django_db
def test_the_first_matching_rule_by_priority_wins(wh):
    PutawayRule.objects.create(
        organization=wh["org"],
        name="Everything to ambient",
        priority=200,
        strategy=PutawayRule.Strategy.FIXED_BIN,
        target_bin=wh["bin_a"],
    )
    PutawayRule.objects.create(
        organization=wh["org"],
        name="Cold chain first",
        priority=10,
        strategy=PutawayRule.Strategy.FIXED_BIN,
        target_bin=wh["bin_c"],
        match_cold_chain_only=True,
    )
    result = warehouse_services.suggest_putaway(
        organization=wh["org"], product=wh["vaccine"], warehouse=wh["warehouse"]
    )
    assert result["bin_location"] == wh["bin_c"].id
    assert result["rule"] is not None


@pytest.mark.django_db
def test_apply_putaway_moves_the_lot_and_frees_the_bin_it_left(wh):
    batch = _batch(wh, wh["amox"], number="PUT-1", bin_location=wh["bin_a"])
    wh["bin_a"].is_occupied = True
    wh["bin_a"].save()

    warehouse_services.apply_putaway(batch=batch, bin_location=wh["bin_c"], user=wh["user"])
    batch.refresh_from_db()
    wh["bin_a"].refresh_from_db()
    wh["bin_c"].refresh_from_db()
    assert batch.bin_location_id == wh["bin_c"].id
    assert batch.storage_location == "C-01-01"
    assert batch.warehouse_id == wh["warehouse"].id
    assert wh["bin_c"].is_occupied is True
    assert wh["bin_a"].is_occupied is False


# --- Wave picking ----------------------------------------------------------


@pytest.mark.django_db
def test_pick_tasks_are_built_fefo_across_batches(wh):
    _batch(wh, wh["amox"], number="LATE", days_to_expiry=400, qty=100, bin_location=wh["bin_a"])
    _batch(wh, wh["amox"], number="SOON", days_to_expiry=30, qty=40, bin_location=wh["bin_a"])
    wave = PickWave.objects.create(
        organization=wh["org"], warehouse=wh["warehouse"], wave_no="W-001"
    )

    tasks = warehouse_services.build_pick_tasks(
        wave=wave,
        demands=[
            {"product": wh["amox"], "quantity": 60, "reference_type": "order", "reference_id": "42"}
        ],
        user=wh["user"],
    )
    assert [t.batch_number for t in tasks] == ["SOON", "LATE"], "Soonest expiry goes first"
    assert [t.quantity_requested for t in tasks] == [40, 20]
    assert all(t.reference_id == "42" for t in tasks)


@pytest.mark.django_db
def test_an_uncoverable_demand_still_shows_the_shortfall(wh):
    _batch(wh, wh["amox"], number="ONLY", days_to_expiry=100, qty=10, bin_location=wh["bin_a"])
    wave = PickWave.objects.create(organization=wh["org"], wave_no="W-002")
    tasks = warehouse_services.build_pick_tasks(
        wave=wave, demands=[{"product": wh["amox"], "quantity": 25}], user=wh["user"]
    )
    short = [t for t in tasks if t.status == PickTask.Status.SHORT]
    assert len(short) == 1
    assert short[0].quantity_requested == 15, "The floor must see the gap, not a smaller number"


@pytest.mark.django_db
def test_release_reserves_stock_and_confirming_a_short_pick_hands_it_back(wh):
    batch = _batch(
        wh, wh["amox"], number="RES-1", days_to_expiry=90, qty=50, bin_location=wh["bin_a"]
    )
    wave = PickWave.objects.create(organization=wh["org"], wave_no="W-003")
    warehouse_services.build_pick_tasks(
        wave=wave, demands=[{"product": wh["amox"], "quantity": 30}], user=wh["user"]
    )
    warehouse_services.release_wave(wave=wave, user=wh["user"])

    batch.refresh_from_db()
    assert batch.quantity_reserved == 30, "Release reserves so two waves cannot promise one unit"

    task = wave.tasks.get()
    warehouse_services.confirm_pick(
        task=task, quantity_picked=18, user=wh["user"], short_reason="Bin held only 18."
    )
    task.refresh_from_db()
    batch.refresh_from_db()
    assert task.status == PickTask.Status.SHORT
    assert task.quantity_picked == 18
    # Picking stages stock, it does not ship it: on-hand only falls at dispatch, so
    # the 12 units that were never picked go back to free stock and the 18 on the
    # cart stay committed.
    assert batch.quantity_reserved == 18
    assert batch.quantity_available == 50


@pytest.mark.django_db
def test_cancelling_a_wave_releases_every_unpicked_reservation(wh):
    batch = _batch(
        wh, wh["amox"], number="RES-2", days_to_expiry=90, qty=50, bin_location=wh["bin_a"]
    )
    wave = PickWave.objects.create(organization=wh["org"], wave_no="W-004")
    warehouse_services.build_pick_tasks(
        wave=wave, demands=[{"product": wh["amox"], "quantity": 20}], user=wh["user"]
    )
    warehouse_services.release_wave(wave=wave, user=wh["user"])
    warehouse_services.cancel_wave(wave=wave, user=wh["user"])

    batch.refresh_from_db()
    wave.refresh_from_db()
    assert batch.quantity_reserved == 0
    assert batch.quantity_available == 50
    assert wave.status == PickWave.Status.CANCELLED


@pytest.mark.django_db
def test_a_wave_cannot_be_released_twice_or_released_empty(wh):
    wave = PickWave.objects.create(organization=wh["org"], wave_no="W-005")
    with pytest.raises(ValueError, match="Build pick tasks"):
        warehouse_services.release_wave(wave=wave, user=wh["user"])

    _batch(wh, wh["amox"], number="RES-3", days_to_expiry=90, qty=5, bin_location=wh["bin_a"])
    warehouse_services.build_pick_tasks(
        wave=wave, demands=[{"product": wh["amox"], "quantity": 5}], user=wh["user"]
    )
    warehouse_services.release_wave(wave=wave, user=wh["user"])
    with pytest.raises(ValueError, match="draft wave"):
        warehouse_services.release_wave(wave=wave, user=wh["user"])


# --- Consignment / VMI -----------------------------------------------------


@pytest.fixture
def agreement(wh):
    return ConsignmentAgreement.objects.create(
        organization=wh["org"],
        agreement_no="VMI-001",
        direction=ConsignmentAgreement.Direction.SUPPLIER_OWNED,
        owner_supplier=wh["supplier"],
        status=ConsignmentAgreement.Status.ACTIVE,
        start_date=date.today() - timedelta(days=30),
    )


@pytest.mark.django_db
def test_owned_stock_never_creates_a_consignment_liability(wh, agreement):
    owned = _batch(wh, wh["amox"], number="OWNED-1", qty=100)
    assert (
        warehouse_services.record_consignment_consumption(batch=owned, quantity=10, trigger="SALE")
        is None
    )


@pytest.mark.django_db
def test_consuming_consigned_stock_creates_the_liability_at_lot_cost(wh, agreement):
    batch = _batch(
        wh,
        wh["amox"],
        number="VMI-BATCH",
        qty=100,
        cost="1500.00",
        is_consignment=True,
        consignment_agreement=agreement,
    )
    consumption = warehouse_services.record_consignment_consumption(
        batch=batch, quantity=8, trigger="SALE"
    )
    assert consumption is not None
    assert consumption.total_value == Decimal("12000.00")

    position = warehouse_services.consignment_position(agreement)
    assert position["unsettled_units"] == 8
    assert Decimal(position["unsettled_value"]) == Decimal("12000.00")


@pytest.mark.django_db
def test_settlement_rolls_consumptions_up_and_raises_the_supplier_bill(wh, agreement):
    batch = _batch(
        wh,
        wh["amox"],
        number="VMI-BATCH-2",
        qty=100,
        cost="1000.00",
        is_consignment=True,
        consignment_agreement=agreement,
    )
    for _ in range(3):
        warehouse_services.record_consignment_consumption(batch=batch, quantity=5, trigger="SALE")

    settlement = warehouse_services.settle_consignment(
        agreement=agreement,
        settlement_no="CS-001",
        period_start=date.today() - timedelta(days=1),
        period_end=date.today() + timedelta(days=1),
        user=wh["user"],
    )
    assert settlement.lines_count == 3
    assert settlement.total_quantity == 15
    assert settlement.total_value == Decimal("15000.00")
    assert settlement.status == ConsignmentSettlement.Status.INVOICED
    assert settlement.supplier_bill is not None
    assert settlement.supplier_bill.total_amount == Decimal("15000.00")

    # A second settlement over the same window finds nothing left to bill.
    assert warehouse_services.consignment_position(agreement)["unsettled_lines"] == 0


@pytest.mark.django_db
def test_settling_an_empty_period_is_refused_rather_than_billing_zero(wh, agreement):
    with pytest.raises(ValueError):
        warehouse_services.settle_consignment(
            agreement=agreement,
            settlement_no="CS-002",
            period_start=date.today() - timedelta(days=1),
            period_end=date.today(),
            user=wh["user"],
        )


# --- API surface -----------------------------------------------------------


@pytest.mark.django_db
def test_warehouse_crud_and_occupancy_endpoint(wh):
    client = _auth(wh["user"])
    created = client.post(
        "/api/inventory/warehouses/",
        {
            "organization": wh["org"].id,
            "code": "WH2",
            "name": "Satellite",
            "warehouse_type": "SATELLITE",
        },
        format="json",
    )
    assert created.status_code == status.HTTP_201_CREATED

    listed = client.get(f"/api/inventory/warehouses/?organization={wh['org'].id}")
    assert listed.status_code == status.HTTP_200_OK
    assert listed.json()["count"] == 2

    patched = client.patch(
        f"/api/inventory/warehouses/{created.json()['id']}/",
        {"name": "Satellite Cross-dock"},
        format="json",
    )
    assert patched.status_code == status.HTTP_200_OK
    assert patched.json()["name"] == "Satellite Cross-dock"

    occupancy = client.get(f"/api/inventory/warehouses/{wh['warehouse'].id}/occupancy/")
    assert occupancy.status_code == status.HTTP_200_OK
    zones = {z["zone_name"]: z for z in occupancy.json()["zones"]}
    assert zones["Cold Room"]["bins_total"] == 1

    deleted = client.delete(f"/api/inventory/warehouses/{created.json()['id']}/")
    assert deleted.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_scan_endpoint_commissions_then_trace_and_export_read_back(wh):
    client = _auth(wh["user"])
    scanned = client.post(
        "/api/inventory/serial-units/scan/",
        {
            "organization": wh["org"].id,
            "scan": "(01)05012345678900(17)271231(10)BATCH-A(21)SER0001",
        },
        format="json",
    )
    assert scanned.status_code == status.HTTP_201_CREATED
    assert scanned.json()["created"] is True
    unit_id = scanned.json()["unit"]["id"]

    rescanned = client.post(
        "/api/inventory/serial-units/scan/",
        {
            "organization": wh["org"].id,
            "scan": "(01)05012345678900(17)271231(10)BATCH-A(21)SER0001",
        },
        format="json",
    )
    assert rescanned.status_code == status.HTTP_200_OK
    assert rescanned.json()["created"] is False

    traced = client.get(f"/api/inventory/serial-units/{unit_id}/trace/")
    assert traced.status_code == status.HTTP_200_OK
    assert traced.json()["serial"] == "SER0001"

    exported = client.get(f"/api/inventory/epcis-events/export/?organization={wh['org'].id}")
    assert exported.status_code == status.HTTP_200_OK
    assert exported.json()["type"] == "EPCISDocument"


@pytest.mark.django_db
def test_scan_endpoint_rejects_a_mis_scanned_code(wh):
    client = _auth(wh["user"])
    response = client.post(
        "/api/inventory/serial-units/scan/",
        {"organization": wh["org"].id, "scan": "0105012345678901" + "21SER1"},
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_replenishment_endpoints_recompute_and_report(wh):
    client = _auth(wh["user"])
    batch = _batch(wh, wh["amox"], number="API-1", qty=20, cost="500.00")
    for day in range(1, 31):
        _sell(wh, wh["amox"], batch, units=4, days_ago=day)

    recomputed = client.post(
        "/api/inventory/reorder-rules/recompute/",
        {"organization": wh["org"].id, "days": 90},
        format="json",
    )
    assert recomputed.status_code == status.HTTP_200_OK

    for endpoint in ("suggestions", "abc_xyz", "slow_dead", "near_expiry"):
        response = client.get(
            f"/api/inventory/reorder-rules/{endpoint}/?organization={wh['org'].id}"
        )
        assert response.status_code == status.HTTP_200_OK, endpoint

    rules = client.get(f"/api/inventory/reorder-rules/?organization={wh['org'].id}")
    assert rules.json()["results"][0]["abc_class"] in {"A", "B", "C"}


@pytest.mark.django_db
def test_pick_wave_endpoints_drive_a_wave_end_to_end(wh):
    client = _auth(wh["user"])
    batch = _batch(
        wh, wh["amox"], number="API-PICK", days_to_expiry=60, qty=30, bin_location=wh["bin_a"]
    )

    wave = client.post(
        "/api/inventory/pick-waves/",
        {
            "organization": wh["org"].id,
            "warehouse": wh["warehouse"].id,
            "wave_no": "W-API-1",
            "strategy": "BATCH",
        },
        format="json",
    )
    assert wave.status_code == status.HTTP_201_CREATED
    wave_id = wave.json()["id"]

    built = client.post(
        f"/api/inventory/pick-waves/{wave_id}/build_tasks/",
        {"demands": [{"product": wh["amox"].id, "quantity": 12}]},
        format="json",
    )
    assert built.status_code == status.HTTP_200_OK
    assert built.json()["task_summary"]["total"] == 1

    released = client.post(f"/api/inventory/pick-waves/{wave_id}/release/", {}, format="json")
    assert released.status_code == status.HTTP_200_OK
    assert released.json()["status"] == PickWave.Status.RELEASED

    task_id = released.json()["tasks"][0]["id"]
    confirmed = client.post(
        f"/api/inventory/pick-tasks/{task_id}/confirm/",
        {"quantity_picked": 12},
        format="json",
    )
    assert confirmed.status_code == status.HTTP_200_OK
    assert confirmed.json()["status"] == PickTask.Status.PICKED

    batch.refresh_from_db()
    assert batch.quantity_available == 30, "On-hand falls at dispatch, not at the bin"
    assert batch.quantity_reserved == 12


@pytest.mark.django_db
def test_consignment_endpoints_expose_position_and_settlement(wh):
    client = _auth(wh["user"])
    created = client.post(
        "/api/inventory/consignments/",
        {
            "organization": wh["org"].id,
            "agreement_no": "VMI-API-1",
            "direction": "SUPPLIER_OWNED",
            "owner_supplier": wh["supplier"].id,
            "status": "ACTIVE",
            "start_date": str(date.today() - timedelta(days=10)),
        },
        format="json",
    )
    assert created.status_code == status.HTTP_201_CREATED
    agreement_id = created.json()["id"]

    agreement = ConsignmentAgreement.objects.get(pk=agreement_id)
    batch = _batch(
        wh,
        wh["amox"],
        number="VMI-API-BATCH",
        qty=50,
        cost="800.00",
        is_consignment=True,
        consignment_agreement=agreement,
    )
    warehouse_services.record_consignment_consumption(batch=batch, quantity=6, trigger="SALE")

    position = client.get(f"/api/inventory/consignments/{agreement_id}/position/")
    assert position.json()["unsettled_units"] == 6

    settled = client.post(
        f"/api/inventory/consignments/{agreement_id}/settle/",
        {
            "period_start": str(date.today() - timedelta(days=1)),
            "period_end": str(date.today() + timedelta(days=1)),
        },
        format="json",
    )
    assert settled.status_code == status.HTTP_201_CREATED
    assert settled.json()["total_value"] == "4800.00"


@pytest.mark.django_db
def test_supplier_owned_agreement_must_name_its_owner(wh):
    client = _auth(wh["user"])
    response = client.post(
        "/api/inventory/consignments/",
        {
            "organization": wh["org"].id,
            "agreement_no": "VMI-BAD",
            "direction": "SUPPLIER_OWNED",
            "start_date": str(date.today()),
        },
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "owner_supplier" in response.json()


@pytest.mark.django_db
def test_cold_chain_endpoints_record_calibration_and_run_an_investigation(wh):
    client = _auth(wh["user"])
    sensor = TemperatureSensor.objects.create(
        organization=wh["org"], zone=wh["cold"], device_id="API-LOG", name="API Probe"
    )
    _batch(wh, wh["vaccine"], number="API-VAX", bin_location=wh["bin_c"])

    calibrated = client.post(
        f"/api/inventory/temp-sensors/{sensor.id}/record_calibration/",
        {"certificate_no": "CAL-API-1", "calibrated_on": str(date.today())},
        format="json",
    )
    assert calibrated.status_code == status.HTTP_201_CREATED

    register = client.get(
        f"/api/inventory/temp-sensors/calibration_register/?organization={wh['org'].id}"
    )
    assert register.status_code == status.HTTP_200_OK
    assert register.json()[0]["calibration_state"] == "VALID"

    start = timezone.now() - timedelta(hours=2)
    for offset, temp in enumerate([4.0, 15.0, 16.5]):
        TemperatureLog.objects.create(
            sensor=sensor,
            temperature_celsius=Decimal(str(temp)),
            recorded_at=start + timedelta(minutes=20 * offset),
        )

    opened = client.post(
        "/api/inventory/excursions/open_from_window/",
        {
            "organization": wh["org"].id,
            "sensor": sensor.id,
            "started_at": start.isoformat(),
            "ended_at": timezone.now().isoformat(),
        },
        format="json",
    )
    assert opened.status_code == status.HTTP_201_CREATED
    assert opened.json()["readings_count"] == 3

    closed = client.post(
        f"/api/inventory/excursions/{opened.json()['id']}/close/",
        {"disposition": "DESTROY", "rationale": "Vaccine held above 8 °C for 40 minutes."},
        format="json",
    )
    assert closed.status_code == status.HTTP_200_OK
    assert closed.json()["status"] == ExcursionInvestigation.Status.CLOSED


@pytest.mark.django_db
def test_putaway_endpoints_suggest_then_commit(wh):
    client = _auth(wh["user"])
    batch = _batch(wh, wh["vaccine"], number="PUT-API")

    suggestion = client.get(f"/api/inventory/batches/{batch.id}/putaway_suggestion/")
    assert suggestion.status_code == status.HTTP_200_OK
    assert suggestion.json()["bin_location"] == wh["bin_c"].id

    applied = client.post(
        f"/api/inventory/batches/{batch.id}/putaway/",
        {"bin_location": wh["bin_c"].id},
        format="json",
    )
    assert applied.status_code == status.HTTP_200_OK
    assert applied.json()["bin_code"] == "C-01-01"


@pytest.mark.django_db
def test_another_organizations_data_is_invisible(wh):
    other_org = Organization.objects.create(name="Rival Depot", type="DEPOT")
    other_user = User.objects.create_user(
        username="rival", email="rival@medlink.rw", password="Password123!"
    )
    other_user.organization = other_org
    other_user.roles.add(Role.objects.get(code="PHARMACIST"))
    other_user.save()

    Warehouse.objects.create(organization=wh["org"], code="WH9", name="Hidden")
    client = _auth(other_user)
    for endpoint in ("warehouses", "serial-units", "pick-waves"):
        assert client.get(f"/api/inventory/{endpoint}/").json()["count"] == 0, endpoint
