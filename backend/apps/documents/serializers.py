from __future__ import annotations

from rest_framework import serializers

from apps.documents.models import Document


class DocumentSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id",
            "doc_type",
            "doc_number",
            "reference_type",
            "reference_id",
            "content_hash",
            "qr_token",
            "generated_at",
            "download_url",
        ]
        read_only_fields = fields

    def get_download_url(self, obj: Document) -> str:
        return f"/api/documents/{obj.pk}/download/"
