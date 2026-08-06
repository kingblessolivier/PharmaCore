"""Root URL configuration.

Module routers (iam, catalog, inventory, …) are included here as they are built.
"""

from __future__ import annotations

from apps.core.views import DashboardView
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/dashboard/", DashboardView.as_view(), name="dashboard"),
    path("", include("apps.core.urls")),
    path("api/", include("apps.iam.urls")),
    path("api/catalog/", include("apps.catalog.urls")),
    path("api/inventory/", include("apps.inventory.urls")),
    path("api/distribution/", include("apps.distribution.urls")),
    path("api/documents/", include("apps.documents.urls")),
    path("api/retail/", include("apps.retail.urls")),
    path("api/workspace/", include("apps.workspace.urls")),
    path("api/approvals/", include("apps.approvals.urls")),
    path("api/finance/", include("apps.finance.urls")),
    path("api/hr/", include("apps.hr.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
