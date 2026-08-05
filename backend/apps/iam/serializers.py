"""Serializers for the iam app."""

from __future__ import annotations

from datetime import date
from typing import Any

from rest_framework import serializers

from apps.iam.models import (
    AuditLog,
    Company,
    Department,
    License,
    Organization,
    Role,
    User,
)


class CompanySerializer(serializers.ModelSerializer):
    branch_count = serializers.IntegerField(source="branches.count", read_only=True)

    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "legal_name",
            "tin",
            "registration_number",
            "contact_person",
            "phone",
            "email",
            "logo_url",
            "currency",
            "is_active",
            "branch_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "branch_count", "created_at", "updated_at"]


class LicenseSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", read_only=True, default=None)
    days_to_expiry = serializers.SerializerMethodField()

    class Meta:
        model = License
        fields = [
            "id",
            "organization",
            "user",
            "user_name",
            "license_type",
            "license_number",
            "issuing_authority",
            "issue_date",
            "expiry_date",
            "days_to_expiry",
            "status",
            "document_url",
            "created_at",
        ]
        read_only_fields = ["id", "user_name", "days_to_expiry", "created_at"]

    def get_days_to_expiry(self, obj: License) -> int | None:
        return (obj.expiry_date - date.today()).days if obj.expiry_date else None


class AuditLogSerializer(serializers.ModelSerializer):
    user = serializers.CharField(source="user.username", read_only=True, default=None)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "action",
            "entity_type",
            "entity_id",
            "user",
            "organization",
            "ip_address",
            "changes",
            "created_at",
        ]


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "code", "name", "description"]


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = [
            "id",
            "company",
            "parent",
            "name",
            "type",
            "tin",
            "registration_number",
            "rwanda_fda_license_no",
            "license_expiry_date",
            "contact_person",
            "phone",
            "email",
            "logo_url",
            "currency",
            "province",
            "district",
            "sector",
            "cell",
            "village",
            "address_line",
            "latitude",
            "longitude",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "organization", "code", "name", "created_at"]
        read_only_fields = ["id", "created_at"]


class UserSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "pf_number",
            "email",
            "first_name",
            "last_name",
            "phone",
            "organization",
            "department",
            "is_active",
            "is_staff",
            "is_superuser",
            "roles",
            "date_joined",
        ]
        read_only_fields = fields

    def get_roles(self, obj: User) -> list[str]:
        return list(obj.roles.values_list("code", flat=True))


class UserAdminSerializer(serializers.ModelSerializer):
    """Admin management of users: create/update with password + role assignment."""

    roles = serializers.SlugRelatedField(
        slug_field="code", many=True, queryset=Role.objects.all(), required=False
    )
    password = serializers.CharField(write_only=True, required=False, min_length=8)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "pf_number",
            "email",
            "first_name",
            "last_name",
            "phone",
            "organization",
            "department",
            "roles",
            "is_active",
            "password",
            "date_joined",
        ]
        read_only_fields = ["id", "date_joined"]

    def create(self, validated_data: dict[str, Any]) -> User:
        roles = validated_data.pop("roles", [])
        password = validated_data.pop("password", None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        if roles:
            user.roles.set(roles)
        return user

    def update(self, instance: User, validated_data: dict[str, Any]) -> User:
        roles = validated_data.pop("roles", None)
        password = validated_data.pop("password", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password:
            instance.set_password(password)
        instance.save()
        if roles is not None:
            instance.roles.set(roles)
        return instance
