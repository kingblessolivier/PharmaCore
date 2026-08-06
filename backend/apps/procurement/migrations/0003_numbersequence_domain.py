"""F4.1 — Extend NumberSequence with a Domain field (ADR-014).

A single, first-class numbering primitive now serves every domain: the
``Domain`` enum namespaces the ``Kind`` so finance journals, HR payslips,
retail receipts, etc. all live in the same table. Existing procurement
rows are unaffected because ``domain`` defaults to PROCUREMENT.

The unique constraint is widened from (organization, kind, year) to
(organization, domain, kind, year) — strictly additive since every
existing row already has domain=PROCUREMENT.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("iam", "0017_user_tin_payroll_email_reports_to"),
        ("procurement", "0002_seed_procurement_rbac"),
    ]

    operations = [
        migrations.AddField(
            model_name="numbersequence",
            name="domain",
            field=models.CharField(
                choices=[
                    ("PROC", "Procurement"),
                    ("FIN", "Finance"),
                    ("HR", "HR"),
                    ("INV", "Inventory"),
                    ("DIST", "Distribution"),
                    ("RTL", "Retail"),
                    ("DOC", "Documents (vault)"),
                ],
                default="PROC",
                max_length=4,
            ),
        ),
        migrations.AlterField(
            model_name="numbersequence",
            name="kind",
            field=models.CharField(
                choices=[
                    # --- Procurement (pre-existing) ---
                    ("PR", "Purchase requisition"),
                    ("RFQ", "Request for quotation"),
                    ("PO", "Purchase order"),
                    ("GRN", "Goods receipt"),
                    ("IMP", "Import consignment"),
                    ("SINV", "Supplier invoice"),
                    ("DBN", "Debit note"),
                    ("CRN", "Credit note"),
                    # --- Finance (ADR-014) ---
                    ("CINV", "Customer invoice (AR)"),
                    ("RCT", "Customer receipt"),
                    ("JE", "Journal entry"),
                    ("PRUN", "Payment run (AP disbursement)"),
                    ("FIL", "Statutory filing (PAYE/RSSB/CBHI/VAT)"),
                    # --- HR (ADR-014) ---
                    ("PSL", "Payslip"),
                    ("EMP", "Employee number"),
                    ("LOAN", "Loan / advance"),
                    # --- Documents ---
                    ("DOC", "Document vault reference"),
                ],
                max_length=6,
            ),
        ),
        migrations.RemoveConstraint(
            model_name="numbersequence",
            name="uniq_procurement_sequence",
        ),
        migrations.AddConstraint(
            model_name="numbersequence",
            constraint=models.UniqueConstraint(
                fields=["organization", "domain", "kind", "year"],
                name="uniq_procurement_sequence",
            ),
        ),
    ]