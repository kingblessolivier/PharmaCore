"""Django admin registrations for iam."""

from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.db.models import Model
from django.http import HttpRequest

from apps.iam.models import AuditLog, Department, Organization, Role, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = (
        *DjangoUserAdmin.fieldsets,  # type: ignore[misc]
        ("PharmaCore", {"fields": ("phone", "organization", "department", "roles")}),
    )
    filter_horizontal = ("roles", "groups", "user_permissions")


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "tin", "is_active")
    list_filter = ("type", "is_active")
    search_fields = ("name", "tin", "rwanda_fda_license_no")


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("organization", "code", "name")
    list_filter = ("code", "organization")
    search_fields = ("name",)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "user", "entity_type", "entity_id")
    list_filter = ("action", "entity_type")
    search_fields = ("entity_id", "action")

    # Append-only: no add/change/delete via the admin.
    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Model | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Model | None = None) -> bool:
        return False
