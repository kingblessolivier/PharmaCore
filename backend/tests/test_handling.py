"""What a medicine needs from whoever moves it, and how big a load is.

The catalogue could state one handling requirement — temperature. These pin the
rest: the cytotoxic that is dangerous but not controlled, the antibiotic that
browns in daylight, and the freight total that must not quietly report an
unmeasured line as weightless.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from apps.catalog import handling
from apps.catalog.models import Product, ProductUnit

pytestmark = pytest.mark.django_db


def codes(product: Product) -> set[str]:
    return {r.code for r in handling.requirements_for(product)}


class TestHandlingRequirements:
    def test_an_ordinary_tablet_needs_nothing_special(self) -> None:
        assert codes(Product.objects.create(generic_name="Paracetamol 500mg")) == set()

    def test_a_cold_chain_product_states_its_span(self) -> None:
        vaccine = Product.objects.create(
            generic_name="Measles vaccine",
            storage_condition=Product.Storage.COLD_CHAIN,
            min_temp_c=Decimal("2"),
            max_temp_c=Decimal("8"),
        )
        (requirement,) = handling.requirements_for(vaccine)
        assert requirement.code == "COLD_CHAIN"
        assert "2 °C to 8 °C" in requirement.detail
        assert requirement.critical

    def test_cold_chain_without_a_recorded_span_still_says_something_useful(self) -> None:
        vaccine = Product.objects.create(
            generic_name="Unspecified vaccine",
            storage_condition=Product.Storage.COLD_CHAIN,
        )
        (requirement,) = handling.requirements_for(vaccine)
        assert "2 °C to 8 °C" in requirement.detail, "must fall back, not render 'None to None'"

    def test_a_cytotoxic_is_flagged_even_though_it_is_not_controlled(self) -> None:
        """The distinction the old model could not express.

        `is_controlled_substance` is a legal category about diversion. A
        cytotoxic is not controlled and is far more dangerous to the person
        picking it — so a system that only knows about control says nothing
        about the one that can actually hurt somebody.
        """
        cyto = Product.objects.create(
            generic_name="Methotrexate 50mg/2mL",
            hazard_class=Product.Hazard.CYTOTOXIC,
        )
        assert cyto.is_controlled_substance is False
        (requirement,) = handling.requirements_for(cyto)
        assert requirement.code == "CYTOTOXIC"
        assert "spill kit" in requirement.detail
        assert requirement.critical

    def test_the_hazard_chip_is_a_name_not_the_whole_choice_label(self) -> None:
        cyto = Product.objects.create(
            generic_name="Methotrexate", hazard_class=Product.Hazard.CYTOTOXIC
        )
        (requirement,) = handling.requirements_for(cyto)
        assert requirement.label == "Cytotoxic"

    def test_light_and_humidity_are_separate_facts(self) -> None:
        product = Product.objects.create(
            generic_name="Ceftriaxone 1g",
            light_sensitive=True,
            humidity_sensitive=True,
        )
        assert codes(product) == {"LIGHT", "HUMIDITY"}

    def test_a_controlled_drug_appears_with_its_schedule(self) -> None:
        pethidine = Product.objects.create(
            generic_name="Pethidine 50mg",
            is_controlled_substance=True,
            controlled_schedule="Schedule 2",
        )
        (requirement,) = handling.requirements_for(pethidine)
        assert "Schedule 2" in requirement.detail

    def test_requirements_accumulate(self) -> None:
        # A frozen cytotoxic that is also light sensitive is not a silly case;
        # it is most of oncology.
        product = Product.objects.create(
            generic_name="Carmustine",
            storage_condition=Product.Storage.FROZEN,
            hazard_class=Product.Hazard.CYTOTOXIC,
            light_sensitive=True,
        )
        assert codes(product) == {"FROZEN", "CYTOTOXIC", "LIGHT"}


class TestDoseAgainstStock:
    def test_a_course_converts_into_bottles(self) -> None:
        # "5 mL twice daily for 7 days" = 70 mL; a bottle holds 100 mL.
        syrup = Product.objects.create(
            generic_name="Amoxicillin suspension",
            dose_unit=Product.DoseUnit.ML,
            doses_per_base_unit=Decimal("100"),
        )
        needed = handling.base_units_for_dose(
            syrup, dose_amount=Decimal("5"), doses_per_day=Decimal("2"), days=7
        )
        assert needed == Decimal("0.7")

    def test_a_course_can_exceed_one_pack(self) -> None:
        syrup = Product.objects.create(
            generic_name="Amoxicillin suspension",
            dose_unit=Product.DoseUnit.ML,
            doses_per_base_unit=Decimal("100"),
        )
        needed = handling.base_units_for_dose(
            syrup, dose_amount=Decimal("10"), doses_per_day=Decimal("3"), days=10
        )
        assert needed == Decimal("3")

    def test_an_unmapped_product_returns_nothing_rather_than_guessing(self) -> None:
        # Guessing here dispenses the wrong amount of medicine to a patient.
        tablet = Product.objects.create(generic_name="Paracetamol 500mg")
        assert (
            handling.base_units_for_dose(
                tablet, dose_amount=Decimal("1"), doses_per_day=Decimal("3"), days=5
            )
            is None
        )


class TestShipmentSize:
    @pytest.fixture
    def carton(self) -> ProductUnit:
        product = Product.objects.create(generic_name="Amoxicillin 500mg")
        return ProductUnit.objects.create(
            product=product,
            code="CARTON",
            name="Carton of 24 boxes",
            factor_to_base=2400,
            level=3,
            gross_weight_g=Decimal("4800"),
            volume_ml=Decimal("32000"),
        )

    def test_weight_and_volume_scale_with_quantity(self, carton: ProductUnit) -> None:
        shipment = handling.measure([(carton, 10)])
        assert shipment.gross_weight_kg == Decimal("48.000")
        assert shipment.volume_litres == Decimal("320.000")
        assert shipment.is_complete

    def test_an_unmeasured_line_is_named_rather_than_treated_as_weightless(self) -> None:
        product = Product.objects.create(generic_name="Unmeasured thing")
        bare = ProductUnit.objects.create(
            product=product, code="BOX", factor_to_base=1, level=1, is_base=True
        )
        shipment = handling.measure([(bare, 100)])
        assert shipment.gross_weight_g == 0
        assert not shipment.is_complete
        assert "Unmeasured thing" in shipment.unmeasured[0]

    def test_a_half_measured_line_still_flags(self, carton: ProductUnit) -> None:
        carton.volume_ml = None
        carton.save()
        shipment = handling.measure([(carton, 1)])
        assert shipment.gross_weight_g == Decimal("4800")
        assert not shipment.is_complete, "a weight without a volume is not a freight answer"

    def test_air_freight_bills_the_larger_of_the_two(self, carton: ProductUnit) -> None:
        """A pallet of bulky, light cartons costs what its size implies.

        Quoting on actual weight alone under-reads every voluminous order,
        which is most of a pharmacy's — boxes of boxes are mostly air.
        """
        shipment = handling.measure([(carton, 1)])
        # 4.8 kg actual against 32 L × 0.167 = 5.344 kg volumetric.
        assert shipment.gross_weight_kg == Decimal("4.800")
        assert shipment.chargeable_weight_kg == Decimal("5.344")

    def test_a_dense_load_bills_on_actual_weight(self) -> None:
        product = Product.objects.create(generic_name="Liquid concentrate")
        drum = ProductUnit.objects.create(
            product=product,
            code="DRUM",
            factor_to_base=1,
            level=1,
            is_base=True,
            gross_weight_g=Decimal("50000"),
            volume_ml=Decimal("50000"),
        )
        shipment = handling.measure([(drum, 1)])
        assert shipment.chargeable_weight_kg == Decimal("50.000")

    def test_cold_boxes_round_up(self, carton: ProductUnit) -> None:
        shipment = handling.measure([(carton, 1)])  # 32 L
        assert handling.cold_boxes_needed(shipment) == 2

    def test_an_empty_load_needs_no_box(self) -> None:
        assert handling.cold_boxes_needed(handling.Shipment()) == 0

    def test_an_exactly_full_box_is_not_rounded_to_two(self) -> None:
        product = Product.objects.create(generic_name="Vaccine")
        unit = ProductUnit.objects.create(
            product=product,
            code="BOX",
            factor_to_base=1,
            level=1,
            is_base=True,
            volume_ml=Decimal("20000"),
            gross_weight_g=Decimal("1000"),
        )
        assert handling.cold_boxes_needed(handling.measure([(unit, 1)])) == 1
