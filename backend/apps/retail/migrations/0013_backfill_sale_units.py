"""Point existing sale lines at the unit they were always counted in.

Every line written before this was implicitly in the product's base unit, since
there was no other unit to be in. So `unit = base` and `quantity_base =
quantity` is not a conversion — it is writing down what was already true. No
figure on any past receipt changes.
"""

from __future__ import annotations

from django.db import migrations


def backfill(apps, schema_editor):
    SaleItem = apps.get_model("retail", "SaleItem")
    ProductUnit = apps.get_model("catalog", "ProductUnit")

    base_by_product = dict(
        ProductUnit.objects.filter(is_base=True).values_list("product_id", "id")
    )
    updates = []
    for item in SaleItem.objects.all().iterator():
        item.unit_id = base_by_product.get(item.product_id)
        item.quantity_base = item.quantity
        updates.append(item)
        if len(updates) >= 500:
            SaleItem.objects.bulk_update(updates, ["unit_id", "quantity_base"])
            updates = []
    if updates:
        SaleItem.objects.bulk_update(updates, ["unit_id", "quantity_base"])


def noop(apps, schema_editor):
    """Nothing to undo: the columns go with the schema migration."""


class Migration(migrations.Migration):
    dependencies = [
        ("retail", "0012_saleitem_quantity_base_saleitem_unit_and_more"),
        ("catalog", "0009_seed_base_units"),
    ]
    operations = [migrations.RunPython(backfill, noop)]
