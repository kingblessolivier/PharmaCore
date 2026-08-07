"""Backfill `Account.classification` for accounts created before the field existed.

Without this, an existing tenant's reports silently fall back to the per-type
default until something happens to call ``ensure_default_accounts`` — so cost of
sales reads as an operating expense and gross profit comes out as zero. A report
must never depend on an unrelated write having run first, so the classification
is set here, once, for every row already in the database.

Accounts outside the seeded control set are classified by their code range, which
is the same convention the seed uses; anything unrecognised falls back to the
per-type default rather than being left blank.
"""

from __future__ import annotations

from django.db import migrations

# code -> classification, mirroring apps/finance/services._CLASSIFICATIONS
BY_CODE: dict[str, str] = {
    "1100": "CURRENT_ASSET",
    "1200": "CURRENT_ASSET",
    "1300": "CURRENT_ASSET",
    "1350": "CURRENT_ASSET",
    "1400": "CURRENT_ASSET",
    "1500": "CURRENT_ASSET",
    "1700": "NON_CURRENT_ASSET",
    "1701": "NON_CURRENT_ASSET",
    "2100": "CURRENT_LIABILITY",
    "2150": "CURRENT_LIABILITY",
    "2160": "CURRENT_LIABILITY",
    "2200": "CURRENT_LIABILITY",
    "2210": "CURRENT_LIABILITY",
    "2220": "CURRENT_LIABILITY",
    "2230": "CURRENT_LIABILITY",
    "2240": "CURRENT_LIABILITY",
    "2250": "CURRENT_LIABILITY",
    "2300": "CURRENT_LIABILITY",
    "2400": "CURRENT_LIABILITY",
    "2500": "CURRENT_LIABILITY",
    "2600": "CURRENT_LIABILITY",
    "3000": "EQUITY",
    "4100": "REVENUE",
    "4200": "REVENUE",
    "4300": "REVENUE",
    "5000": "COGS",
    "5100": "COGS",
    "5900": "COGS",
    "6100": "OPERATING_EXPENSE",
    "6110": "OPERATING_EXPENSE",
    "6120": "OPERATING_EXPENSE",
    "6130": "OPERATING_EXPENSE",
    "6140": "OPERATING_EXPENSE",
    "7000": "TAX_EXPENSE",
    "7100": "FINANCE_COST",
}

BY_TYPE: dict[str, str] = {
    "ASSET": "CURRENT_ASSET",
    "LIABILITY": "CURRENT_LIABILITY",
    "EQUITY": "EQUITY",
    "REVENUE": "REVENUE",
    "EXPENSE": "OPERATING_EXPENSE",
}


def classify_by_code(code: str, account_type: str) -> str:
    """Best guess for a hand-created account, from the code range then the type."""
    if code in BY_CODE:
        return BY_CODE[code]
    if code[:1] == "1":
        return "NON_CURRENT_ASSET" if code[:2] in {"17", "18"} else "CURRENT_ASSET"
    if code[:1] == "2":
        return "NON_CURRENT_LIABILITY" if code[:2] in {"27", "28"} else "CURRENT_LIABILITY"
    if code[:1] == "3":
        return "EQUITY"
    if code[:1] == "4":
        return "REVENUE"
    if code[:1] == "5":
        return "COGS"
    if code[:2] == "65":
        return "DEPRECIATION"
    if code[:1] == "6":
        return "OPERATING_EXPENSE"
    if code[:1] == "7":
        return "TAX_EXPENSE"
    return BY_TYPE.get(account_type, "OPERATING_EXPENSE")


def backfill(apps, schema_editor):  # type: ignore[no-untyped-def]
    Account = apps.get_model("finance", "Account")
    for account in Account.objects.filter(classification=""):
        account.classification = classify_by_code(account.code, account.account_type)
        account.save(update_fields=["classification"])


def unbackfill(apps, schema_editor):  # type: ignore[no-untyped-def]
    apps.get_model("finance", "Account").objects.update(classification="")


class Migration(migrations.Migration):
    dependencies = [("finance", "0015_account_classification")]
    operations = [migrations.RunPython(backfill, unbackfill)]
