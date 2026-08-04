"""Identity & Access models: User, Role, and the append-only AuditLog.

Phase 0 foundation. Organization/department scoping and licenses arrive in Phase 1
(see docs/02-data-model.md); the FKs are intentionally deferred to keep this slice
focused on auth + base RBAC + audit.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.Model):
    """A named role users can hold (base RBAC). Permissions are attached in Phase 1."""

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return self.code


class Organization(models.Model):
    """A depot, retail pharmacy, or HQ — the multi-tenant root everything scopes by."""

    class OrgType(models.TextChoices):
        DEPOT = "DEPOT", "Depot"
        RETAIL = "RETAIL", "Retail"
        HQ = "HQ", "HQ"

    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children"
    )
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=OrgType.choices)
    tin = models.CharField(max_length=20, blank=True, default="")  # RRA taxpayer id
    rwanda_fda_license_no = models.CharField(max_length=100, blank=True, default="")
    license_expiry_date = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    district = models.CharField(max_length=100, blank=True, default="")
    sector = models.CharField(max_length=100, blank=True, default="")
    cell = models.CharField(max_length=100, blank=True, default="")
    address_line = models.TextField(blank=True, default="")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Department(models.Model):
    """An operational department within an organization (dispensing, cashier, …)."""

    class DeptCode(models.TextChoices):
        WAREHOUSE = "WAREHOUSE", "Warehouse"
        DISPATCH = "DISPATCH", "Dispatch"
        PURCHASING = "PURCHASING", "Purchasing"
        DISPENSING = "DISPENSING", "Dispensing"
        CASHIER = "CASHIER", "Cashier"
        INSURANCE = "INSURANCE", "Insurance"
        FINANCE = "FINANCE", "Finance"
        HR = "HR", "Human Resources"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="departments"
    )
    code = models.CharField(max_length=30, choices=DeptCode.choices)
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["organization", "code"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "code"], name="uniq_department_per_org")
        ]

    def __str__(self) -> str:
        return f"{self.organization.name} · {self.code}"


class User(AbstractUser):
    """Custom user model (set as AUTH_USER_MODEL before the first migration).

    Extends Django's AbstractUser (username/email/password/flags) and adds a phone,
    org/department scoping, and role membership. Passwords are hashed with argon2.
    """

    phone = models.CharField(max_length=20, blank=True, default="")
    organization = models.ForeignKey(
        Organization, null=True, blank=True, on_delete=models.SET_NULL, related_name="users"
    )
    department = models.ForeignKey(
        Department, null=True, blank=True, on_delete=models.SET_NULL, related_name="users"
    )
    roles = models.ManyToManyField(Role, related_name="users", blank=True)

    def has_role(self, code: str) -> bool:
        return self.roles.filter(code=code).exists()


class AuditLog(models.Model):
    """Append-only record of every significant action (GDP requirement).

    Immutability is enforced here at the model level (no updates, no deletes); on
    PostgreSQL a migration additionally denies UPDATE/DELETE to the app role.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_entries",
    )
    action = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=100, blank=True, default="")
    entity_id = models.CharField(max_length=64, blank=True, default="")
    changes = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["entity_type", "entity_id"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.action} @ {self.created_at:%Y-%m-%d %H:%M:%S}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        # Append-only: allow the initial insert, forbid any update.
        if not self._state.adding:
            raise ValueError("AuditLog is append-only and cannot be modified.")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> Any:
        raise ValueError("AuditLog is append-only and cannot be deleted.")
