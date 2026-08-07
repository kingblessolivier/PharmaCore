"""Insurance is administered through its own screens, not the Django admin.

Schemes, policies and formulary entries all carry business rules that the admin
would bypass — a policy edited here would not re-resolve a member's co-payment,
and a claim edited here would stop agreeing with the sale behind it.
"""
