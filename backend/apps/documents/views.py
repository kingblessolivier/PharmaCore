"""Documents API: list/retrieve/download (org-scoped) + public QR verification."""

from __future__ import annotations

import hashlib
from typing import cast

from django.db.models import QuerySet
from django.http import FileResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.documents.models import Document
from apps.documents.permissions import visible_doc_types
from apps.documents.serializers import DocumentSerializer
from apps.iam.models import User
from apps.iam.scoping import organizations_visible_to


class DocumentViewSet(viewsets.ReadOnlyModelViewSet):
    """The document vault — read + download, scoped to organizations you can see."""

    serializer_class = DocumentSerializer
    queryset = Document.objects.select_related("organization")

    permission_classes = [IsAuthenticated]

    def get_queryset(self) -> QuerySet[Document]:
        user = cast(User, self.request.user)
        qs = Document.objects.select_related("organization")
        if not (user.is_superuser or user.has_role("SYS_ADMIN")):
            qs = qs.filter(organization__in=organizations_visible_to(user))
            # Org scoping alone let a cashier download a colleague's payslip.
            # A document's type decides who may read it, not only which pharmacy
            # produced it. See apps/documents/permissions.py.
            allowed = visible_doc_types(user)
            if allowed is not None:
                qs = qs.filter(doc_type__in=allowed)
        params = self.request.query_params
        if params.get("reference_type"):
            qs = qs.filter(reference_type=params["reference_type"])
        if params.get("reference_id"):
            qs = qs.filter(reference_id=params["reference_id"])
        if params.get("doc_type"):
            qs = qs.filter(doc_type=params["doc_type"])
        return qs

    @action(detail=True, methods=["get"])
    def download(self, request: Request, pk: str | None = None) -> FileResponse:
        doc = self.get_object()
        return FileResponse(
            doc.file.open("rb"), as_attachment=True, filename=f"{doc.doc_number}.pdf"
        )


class DocumentVerifyView(APIView):
    """Public: verify a document by its QR token — recompute the hash and compare."""

    permission_classes = [AllowAny]
    authentication_classes: list[type] = []

    def get(self, request: Request, token: str) -> Response:
        doc = Document.objects.filter(qr_token=token).first()
        if doc is None:
            return Response({"authentic": False, "reason": "not_found"}, status=404)
        recomputed = hashlib.sha256(doc.file.open("rb").read()).hexdigest()
        return Response(
            {
                "authentic": recomputed == doc.content_hash,
                "doc_number": doc.doc_number,
                "doc_type": doc.doc_type,
                "organization": doc.organization.name,
                "generated_at": doc.generated_at,
            }
        )
