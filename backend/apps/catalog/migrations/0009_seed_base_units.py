"""Give every product the one unit it is already counted in.

This is deliberately a no-op on existing data. Every quantity in the database
today is implicitly in base units — there was no other unit to be in — so
creating a base unit per product and pointing the existing rows at it changes
no number anywhere. The packaging chain above the base (strip, pack, case) is
absent rather than wrong, so there is nothing to migrate, only something to
start capturing.

The base unit is derived from the dosage form, which is the only packaging fact
the catalog currently holds. `units_per_pack` is not used: it is the default 1
on every row in every environment checked, so it carries no information.
"""

from __future__ import annotations

from django.db import migrations

#: dosage form -> (base unit code, human name). The base is the smallest thing
#: that can leave the building: a tablet leaves as a tablet, a syrup leaves as a
#: bottle even though it is *dosed* in millilitres.
BASE_FOR_FORM = {
    "TABLET": ("TABLET", "Tablet"),
    "CAPSULE": ("CAPSULE", "Capsule"),
    "SYRUP": ("BOTTLE", "Bottle"),
    "INJECTION": ("VIAL", "Vial"),
    "OINTMENT": ("TUBE", "Tube"),
    "DROPS": ("BOTTLE", "Bottle"),
    "INHALER": ("DEVICE", "Device"),
    "OTHER": ("UNIT", "Unit"),
}
FALLBACK = ("UNIT", "Unit")


def seed(apps, schema_editor):
    Product = apps.get_model("catalog", "Product")
    ProductUnit = apps.get_model("catalog", "ProductUnit")

    existing = set(
        ProductUnit.objects.filter(is_base=True).values_list("product_id", flat=True)
    )
    rows = []
    for product in Product.objects.exclude(pk__in=existing).iterator():
        code, name = BASE_FOR_FORM.get(product.dosage_form, FALLBACK)
        rows.append(
            ProductUnit(
                product_id=product.pk,
                code=code,
                name=name,
                factor_to_base=1,
                level=0,
                is_base=True,
                # Until somebody records a pack, the base is what you buy and
                # what you sell. Both defaults move the moment a pack exists.
                is_purchase_default=True,
                is_sale_default=True,
            )
        )
    ProductUnit.objects.bulk_create(rows, batch_size=500)


def unseed(apps, schema_editor):
    apps.get_model("catalog", "ProductUnit").objects.filter(is_base=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0008_productunit_product_divisibility_product_split_note_and_more"),
    ]
    operations = [migrations.RunPython(seed, unseed)]
