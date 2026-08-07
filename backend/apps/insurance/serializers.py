from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.insurance.models import (
    Claim,
    ClaimLine,
    InsuranceScheme,
    MemberPolicy,
    RemittanceAdvice,
    RemittanceLine,
    SchemeFormulary,
)


class InsuranceSchemeSerializer(serializers.ModelSerializer[InsuranceScheme]):
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    settlement_display = serializers.CharField(source="get_settlement_display", read_only=True)
    is_capitated = serializers.BooleanField(read_only=True)
    members = serializers.SerializerMethodField()
    covered_products = serializers.SerializerMethodField()

    class Meta:
        model = InsuranceScheme
        fields = [
            "id",
            "organization",
            "code",
            "name",
            "kind",
            "kind_display",
            "settlement",
            "settlement_display",
            "is_capitated",
            "default_copay_pct",
            "consultation_fee",
            "claim_window_days",
            "contact_person",
            "contact_email",
            "contact_phone",
            "is_active",
            "members",
            "covered_products",
            "created_at",
        ]
        read_only_fields = ["id", "is_capitated", "members", "covered_products", "created_at"]

    def get_members(self, obj: InsuranceScheme) -> int:
        return obj.policies.count()

    def get_covered_products(self, obj: InsuranceScheme) -> int:
        return obj.formulary.filter(is_covered=True).count()


class MemberPolicySerializer(serializers.ModelSerializer[MemberPolicy]):
    scheme_name = serializers.CharField(source="scheme.name", read_only=True)
    scheme_code = serializers.CharField(source="scheme.code", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    effective_copay_pct = serializers.SerializerMethodField()

    class Meta:
        model = MemberPolicy
        fields = [
            "id",
            "scheme",
            "scheme_name",
            "scheme_code",
            "member_number",
            "group_number",
            "full_name",
            "national_id",
            "phone",
            "relationship",
            "ubudehe_category",
            "copay_pct_override",
            "effective_copay_pct",
            "valid_from",
            "valid_to",
            "status",
            "status_display",
            "priority",
            "created_at",
        ]
        read_only_fields = ["id", "effective_copay_pct", "created_at"]

    def get_effective_copay_pct(self, obj: MemberPolicy) -> str:
        """What this member actually pays — the override if set, else the scheme."""
        from apps.insurance.eligibility import resolve_copay_pct

        return str(resolve_copay_pct(policy=obj))


class SchemeFormularySerializer(serializers.ModelSerializer[SchemeFormulary]):
    product_name = serializers.CharField(source="product.generic_name", read_only=True)
    product_strength = serializers.CharField(source="product.strength", read_only=True)
    scheme_code = serializers.CharField(source="scheme.code", read_only=True)

    class Meta:
        model = SchemeFormulary
        fields = [
            "id",
            "scheme",
            "scheme_code",
            "product",
            "product_name",
            "product_strength",
            "is_covered",
            "copay_pct_override",
            "max_price_per_unit",
            "max_quantity_per_claim",
            "requires_prior_auth",
            "note",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]


class ClaimLineSerializer(serializers.ModelSerializer[ClaimLine]):
    product_name = serializers.CharField(source="product.generic_name", read_only=True)

    class Meta:
        model = ClaimLine
        fields = [
            "id",
            "product",
            "product_name",
            "quantity",
            "unit_price",
            "gross_amount",
            "patient_amount",
            "insurer_amount",
            "copay_pct_applied",
            "note",
        ]
        read_only_fields = fields


class ClaimSerializer(serializers.ModelSerializer[Claim]):
    scheme_name = serializers.CharField(source="scheme.name", read_only=True)
    member_name = serializers.CharField(source="policy.full_name", read_only=True)
    member_number = serializers.CharField(source="policy.member_number", read_only=True)
    sale_number = serializers.CharField(source="sale.sale_number", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    outstanding = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    shortfall = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    lines = ClaimLineSerializer(many=True, read_only=True)

    class Meta:
        model = Claim
        fields = [
            "id",
            "claim_number",
            "organization",
            "scheme",
            "scheme_name",
            "policy",
            "member_name",
            "member_number",
            "sale",
            "sale_number",
            "status",
            "status_display",
            "service_date",
            "patient_paid",
            "claimed_amount",
            "paid_amount",
            "outstanding",
            "shortfall",
            "rejection_reason",
            "prior_auth_reference",
            "notes",
            "submitted_at",
            "adjudicated_at",
            "reversed_at",
            "lines",
            "created_at",
        ]
        # Every money field moves through the claims service, never by PATCH — a
        # claim edited directly would stop agreeing with the sale behind it.
        read_only_fields = [
            "id",
            "claim_number",
            "status",
            "patient_paid",
            "claimed_amount",
            "paid_amount",
            "outstanding",
            "shortfall",
            "submitted_at",
            "adjudicated_at",
            "reversed_at",
            "lines",
            "created_at",
        ]


class RemittanceLineSerializer(serializers.ModelSerializer[RemittanceLine]):
    claim_number = serializers.CharField(source="claim.claim_number", read_only=True)
    claimed_amount = serializers.DecimalField(
        source="claim.claimed_amount", max_digits=14, decimal_places=2, read_only=True
    )

    class Meta:
        model = RemittanceLine
        fields = ["id", "claim", "claim_number", "claimed_amount", "amount_paid", "denial_reason"]
        read_only_fields = ["id", "claim_number", "claimed_amount"]


class RemittanceAdviceSerializer(serializers.ModelSerializer[RemittanceAdvice]):
    scheme_name = serializers.CharField(source="scheme.name", read_only=True)
    lines = RemittanceLineSerializer(many=True, read_only=True)
    total_matched = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    unmatched = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = RemittanceAdvice
        fields = [
            "id",
            "reference",
            "organization",
            "scheme",
            "scheme_name",
            "status",
            "advice_date",
            "total_advised",
            "total_matched",
            "unmatched",
            "lines",
            "posted_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "total_matched",
            "unmatched",
            "lines",
            "posted_at",
            "created_at",
        ]


class QuoteRequestSerializer(serializers.Serializer[Any]):
    """What the counter asks before dispensing."""

    member_number = serializers.CharField()
    lines = serializers.ListField(child=serializers.DictField(), allow_empty=False)
    on = serializers.DateField(required=False)
