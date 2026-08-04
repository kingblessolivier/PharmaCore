"""Serializers for the iam app."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.iam.models import AuditLog, Department, Organization, Role, User


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
            "parent",
            "name",
            "type",
            "tin",
            "rwanda_fda_license_no",
            "license_expiry_date",
            "phone",
            "email",
            "district",
            "sector",
            "cell",
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
