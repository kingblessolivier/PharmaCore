<!-- GENERATED FILE — do not edit by hand.
     Run `python manage.py generate_docs` after changing models or routes.
     The narrative lives in docs/02-data-model.md and docs/07-api-design.md. -->

# API reference


**969 routes.**

Every route the project serves, generated from the URL resolver.
For conventions — pagination, errors, auth, idempotency — read
[docs/07-api-design.md](../07-api-design.md).


## `/api/`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/` | — | `APIRootView` | The default basic root view for DefaultRouter |


## `/api/<drf_format_suffix:format>`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/<drf_format_suffix:format>` | — | `APIRootView` | The default basic root view for DefaultRouter |


## `/api/^api-keys`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/^api-keys/$` | GET,POST | `ApiKeyViewSet` | Service-account API keys. |
| `/api/^api-keys/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `ApiKeyViewSet` | Service-account API keys. |
| `/api/^api-keys/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `ApiKeyViewSet` | Service-account API keys. |


## `/api/^api-keys\.(?P<format>[a-z0-9]+)`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/^api-keys\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `ApiKeyViewSet` | Service-account API keys. |


## `/api/^audit-logs`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/^audit-logs/$` | GET | `AuditLogViewSet` | Read-only activity log, admin-only, org-scoped (?organization=<id>). |
| `/api/^audit-logs/(?P<pk>[^/.]+)/$` | GET | `AuditLogViewSet` | Read-only activity log, admin-only, org-scoped (?organization=<id>). |
| `/api/^audit-logs/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | GET | `AuditLogViewSet` | Read-only activity log, admin-only, org-scoped (?organization=<id>). |
| `/api/^audit-logs/export/$` | GET | `AuditLogViewSet` | Download the (filtered) audit trail as CSV — same filters as the list. |
| `/api/^audit-logs/export\.(?P<format>[a-z0-9]+)/?$` | GET | `AuditLogViewSet` | Download the (filtered) audit trail as CSV — same filters as the list. |


## `/api/^audit-logs\.(?P<format>[a-z0-9]+)`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/^audit-logs\.(?P<format>[a-z0-9]+)/?$` | GET | `AuditLogViewSet` | Read-only activity log, admin-only, org-scoped (?organization=<id>). |


## `/api/^companies`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/^companies/$` | GET,POST | `CompanyViewSet` | The legal business entities that own branches. |
| `/api/^companies/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `CompanyViewSet` | The legal business entities that own branches. |
| `/api/^companies/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `CompanyViewSet` | The legal business entities that own branches. |


## `/api/^companies\.(?P<format>[a-z0-9]+)`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/^companies\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `CompanyViewSet` | The legal business entities that own branches. |


## `/api/^departments`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/^departments/$` | GET,POST | `DepartmentViewSet` | Departments within visible organizations. |
| `/api/^departments/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `DepartmentViewSet` | Departments within visible organizations. |
| `/api/^departments/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `DepartmentViewSet` | Departments within visible organizations. |


## `/api/^departments\.(?P<format>[a-z0-9]+)`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/^departments\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `DepartmentViewSet` | Departments within visible organizations. |


## `/api/^licenses`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/^licenses/$` | GET,POST | `LicenseViewSet` | Org + staff licences, org-scoped; admin-gated writes, audited. |
| `/api/^licenses/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `LicenseViewSet` | Org + staff licences, org-scoped; admin-gated writes, audited. |
| `/api/^licenses/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `LicenseViewSet` | Org + staff licences, org-scoped; admin-gated writes, audited. |


## `/api/^licenses\.(?P<format>[a-z0-9]+)`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/^licenses\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `LicenseViewSet` | Org + staff licences, org-scoped; admin-gated writes, audited. |


## `/api/^organization-documents`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/^organization-documents/$` | GET,POST | `OrganizationDocumentViewSet` | Registration / compliance documents for organizations. |
| `/api/^organization-documents/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `OrganizationDocumentViewSet` | Registration / compliance documents for organizations. |
| `/api/^organization-documents/(?P<pk>[^/.]+)/verify/$` | POST | `OrganizationDocumentViewSet` | Registration / compliance documents for organizations. |
| `/api/^organization-documents/(?P<pk>[^/.]+)/verify\.(?P<format>[a-z0-9]+)/?$` | POST | `OrganizationDocumentViewSet` | Registration / compliance documents for organizations. |
| `/api/^organization-documents/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `OrganizationDocumentViewSet` | Registration / compliance documents for organizations. |


## `/api/^organization-documents\.(?P<format>[a-z0-9]+)`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/^organization-documents\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `OrganizationDocumentViewSet` | Registration / compliance documents for organizations. |


## `/api/^organizations`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/^organizations/$` | GET,POST | `OrganizationViewSet` | Organizations, tenant-scoped. |
| `/api/^organizations/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `OrganizationViewSet` | Organizations, tenant-scoped. |
| `/api/^organizations/(?P<pk>[^/.]+)/activate/$` | POST | `OrganizationViewSet` | Pass the activation gate — the organization may now trade. |
| `/api/^organizations/(?P<pk>[^/.]+)/activate\.(?P<format>[a-z0-9]+)/?$` | POST | `OrganizationViewSet` | Pass the activation gate — the organization may now trade. |
| `/api/^organizations/(?P<pk>[^/.]+)/performance/$` | GET | `OrganizationViewSet` | How a branch is performing: sales, dispensing, and its staff headcount. |
| `/api/^organizations/(?P<pk>[^/.]+)/performance\.(?P<format>[a-z0-9]+)/?$` | GET | `OrganizationViewSet` | How a branch is performing: sales, dispensing, and its staff headcount. |
| `/api/^organizations/(?P<pk>[^/.]+)/suspend/$` | POST | `OrganizationViewSet` | Suspend an organization (stops it trading) — reversible via activate. |
| `/api/^organizations/(?P<pk>[^/.]+)/suspend\.(?P<format>[a-z0-9]+)/?$` | POST | `OrganizationViewSet` | Suspend an organization (stops it trading) — reversible via activate. |
| `/api/^organizations/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `OrganizationViewSet` | Organizations, tenant-scoped. |


## `/api/^organizations\.(?P<format>[a-z0-9]+)`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/^organizations\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `OrganizationViewSet` | Organizations, tenant-scoped. |


## `/api/^permissions`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/^permissions/$` | GET | `PermissionViewSet` | The full permission catalogue (resource × action) for the matrix. |
| `/api/^permissions/(?P<pk>[^/.]+)/$` | GET | `PermissionViewSet` | The full permission catalogue (resource × action) for the matrix. |
| `/api/^permissions/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | GET | `PermissionViewSet` | The full permission catalogue (resource × action) for the matrix. |


## `/api/^permissions\.(?P<format>[a-z0-9]+)`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/^permissions\.(?P<format>[a-z0-9]+)/?$` | GET | `PermissionViewSet` | The full permission catalogue (resource × action) for the matrix. |


## `/api/^roles`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/^roles/$` | GET,POST | `RoleViewSet` | Roles = bundles of permissions. |
| `/api/^roles/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `RoleViewSet` | Roles = bundles of permissions. |
| `/api/^roles/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `RoleViewSet` | Roles = bundles of permissions. |


## `/api/^roles\.(?P<format>[a-z0-9]+)`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/^roles\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `RoleViewSet` | Roles = bundles of permissions. |


## `/api/^user-documents`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/^user-documents/$` | GET,POST | `UserDocumentViewSet` | Identity documents attached to a user account. |
| `/api/^user-documents/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `UserDocumentViewSet` | Identity documents attached to a user account. |
| `/api/^user-documents/(?P<pk>[^/.]+)/verify/$` | POST | `UserDocumentViewSet` | Mark a document as verified (identity confirmed) by the acting admin. |
| `/api/^user-documents/(?P<pk>[^/.]+)/verify\.(?P<format>[a-z0-9]+)/?$` | POST | `UserDocumentViewSet` | Mark a document as verified (identity confirmed) by the acting admin. |
| `/api/^user-documents/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `UserDocumentViewSet` | Identity documents attached to a user account. |


## `/api/^user-documents\.(?P<format>[a-z0-9]+)`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/^user-documents\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `UserDocumentViewSet` | Identity documents attached to a user account. |


## `/api/^users`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/^users/$` | GET,POST | `UserViewSet` | Admin management of users, org-scoped. |
| `/api/^users/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `UserViewSet` | Admin management of users, org-scoped. |
| `/api/^users/(?P<pk>[^/.]+)/activity/$` | GET | `UserViewSet` | What this user has been doing: recent audit trail + action counts + last login. |
| `/api/^users/(?P<pk>[^/.]+)/activity\.(?P<format>[a-z0-9]+)/?$` | GET | `UserViewSet` | What this user has been doing: recent audit trail + action counts + last login. |
| `/api/^users/(?P<pk>[^/.]+)/force-logout/$` | POST | `UserViewSet` | Revoke all of a user's sessions: bump token_version so every outstanding token (access + refresh) is rejected on next use. |
| `/api/^users/(?P<pk>[^/.]+)/force-logout\.(?P<format>[a-z0-9]+)/?$` | POST | `UserViewSet` | Revoke all of a user's sessions: bump token_version so every outstanding token (access + refresh) is rejected on next use. |
| `/api/^users/(?P<pk>[^/.]+)/performance/$` | GET | `UserViewSet` | How a person is performing: sales rung, items dispensed, returns/voids, logins, last login. |
| `/api/^users/(?P<pk>[^/.]+)/performance\.(?P<format>[a-z0-9]+)/?$` | GET | `UserViewSet` | How a person is performing: sales rung, items dispensed, returns/voids, logins, last login. |
| `/api/^users/(?P<pk>[^/.]+)/set-password/$` | POST | `UserViewSet` | Admin resets a user's password (strength-checked); the user must then change it on next sign-in (``must_change_password``). |
| `/api/^users/(?P<pk>[^/.]+)/set-password\.(?P<format>[a-z0-9]+)/?$` | POST | `UserViewSet` | Admin resets a user's password (strength-checked); the user must then change it on next sign-in (``must_change_password``). |
| `/api/^users/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `UserViewSet` | Admin management of users, org-scoped. |


## `/api/^users\.(?P<format>[a-z0-9]+)`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/^users\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `UserViewSet` | Admin management of users, org-scoped. |


## `/api/approvals`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/approvals/` | — | `APIRootView` | The default basic root view for DefaultRouter |
| `/api/approvals/<drf_format_suffix:format>` | — | `APIRootView` | The default basic root view for DefaultRouter |
| `/api/approvals/^requests/$` | GET | `ApprovalRequestViewSet` | Read-only listing + action endpoints (claim/approve/reject/reassign). |
| `/api/approvals/^requests/(?P<pk>[^/.]+)/$` | GET | `ApprovalRequestViewSet` | Read-only listing + action endpoints (claim/approve/reject/reassign). |
| `/api/approvals/^requests/(?P<pk>[^/.]+)/approve/$` | POST | `ApprovalRequestViewSet` | Read-only listing + action endpoints (claim/approve/reject/reassign). |
| `/api/approvals/^requests/(?P<pk>[^/.]+)/approve\.(?P<format>[a-z0-9]+)/?$` | POST | `ApprovalRequestViewSet` | Read-only listing + action endpoints (claim/approve/reject/reassign). |
| `/api/approvals/^requests/(?P<pk>[^/.]+)/claim/$` | POST | `ApprovalRequestViewSet` | Read-only listing + action endpoints (claim/approve/reject/reassign). |
| `/api/approvals/^requests/(?P<pk>[^/.]+)/claim\.(?P<format>[a-z0-9]+)/?$` | POST | `ApprovalRequestViewSet` | Read-only listing + action endpoints (claim/approve/reject/reassign). |
| `/api/approvals/^requests/(?P<pk>[^/.]+)/reassign/$` | POST | `ApprovalRequestViewSet` | Senior oversight: forward a claim to another approver. |
| `/api/approvals/^requests/(?P<pk>[^/.]+)/reassign\.(?P<format>[a-z0-9]+)/?$` | POST | `ApprovalRequestViewSet` | Senior oversight: forward a claim to another approver. |
| `/api/approvals/^requests/(?P<pk>[^/.]+)/reject/$` | POST | `ApprovalRequestViewSet` | Read-only listing + action endpoints (claim/approve/reject/reassign). |
| `/api/approvals/^requests/(?P<pk>[^/.]+)/reject\.(?P<format>[a-z0-9]+)/?$` | POST | `ApprovalRequestViewSet` | Read-only listing + action endpoints (claim/approve/reject/reassign). |
| `/api/approvals/^requests/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | GET | `ApprovalRequestViewSet` | Read-only listing + action endpoints (claim/approve/reject/reassign). |
| `/api/approvals/^requests\.(?P<format>[a-z0-9]+)/?$` | GET | `ApprovalRequestViewSet` | Read-only listing + action endpoints (claim/approve/reject/reassign). |


## `/api/auth`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/auth/change-password` | — | `ChangePasswordView` | Let the signed-in user change their own password (old + new, strength-checked). |
| `/api/auth/impersonate` | — | `ImpersonateView` | Admin **view-as**: start a session and return an access token *for the target user*, carrying the admin's id + session id so the app can show a banner and the action is fully audited. |
| `/api/auth/impersonate/stop` | — | `StopImpersonateView` | End the current view-as session (called with the impersonation token). |
| `/api/auth/login` | — | `LoginView` | Obtain a JWT access/refresh pair; records an audit entry on success. |
| `/api/auth/me` | — | `MeView` | Return the authenticated user's profile (plus the impersonator, if any). |
| `/api/auth/refresh` | — | `TokenRefreshView` | Takes a refresh type JSON web token and returns an access type JSON web token if the refresh token is valid. |


## `/api/catalog`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/catalog/` | — | `APIRootView` | The default basic root view for DefaultRouter |
| `/api/catalog/<drf_format_suffix:format>` | — | `APIRootView` | The default basic root view for DefaultRouter |
| `/api/catalog/^formulary-items/$` | GET,POST | `FormularyItemViewSet` |  |
| `/api/catalog/^formulary-items/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `FormularyItemViewSet` |  |
| `/api/catalog/^formulary-items/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `FormularyItemViewSet` |  |
| `/api/catalog/^formulary-items\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `FormularyItemViewSet` |  |
| `/api/catalog/^ingredients/$` | GET,POST | `ActiveIngredientViewSet` |  |
| `/api/catalog/^ingredients/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `ActiveIngredientViewSet` |  |
| `/api/catalog/^ingredients/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `ActiveIngredientViewSet` |  |
| `/api/catalog/^ingredients\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `ActiveIngredientViewSet` |  |
| `/api/catalog/^manufacturers/$` | GET,POST | `ManufacturerViewSet` |  |
| `/api/catalog/^manufacturers/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `ManufacturerViewSet` |  |
| `/api/catalog/^manufacturers/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `ManufacturerViewSet` |  |
| `/api/catalog/^manufacturers\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `ManufacturerViewSet` |  |
| `/api/catalog/^price-lists/$` | GET,POST | `PriceListViewSet` |  |
| `/api/catalog/^price-lists/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `PriceListViewSet` |  |
| `/api/catalog/^price-lists/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `PriceListViewSet` |  |
| `/api/catalog/^price-lists\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `PriceListViewSet` |  |
| `/api/catalog/^product-barcodes/$` | GET,POST | `ProductBarcodeViewSet` |  |
| `/api/catalog/^product-barcodes/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `ProductBarcodeViewSet` |  |
| `/api/catalog/^product-barcodes/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `ProductBarcodeViewSet` |  |
| `/api/catalog/^product-barcodes\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `ProductBarcodeViewSet` |  |
| `/api/catalog/^product-contraindications/$` | GET,POST | `ProductContraindicationViewSet` |  |
| `/api/catalog/^product-contraindications/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `ProductContraindicationViewSet` |  |
| `/api/catalog/^product-contraindications/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `ProductContraindicationViewSet` |  |
| `/api/catalog/^product-contraindications\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `ProductContraindicationViewSet` |  |
| `/api/catalog/^product-ingredients/$` | GET,POST | `ProductIngredientViewSet` |  |
| `/api/catalog/^product-ingredients/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `ProductIngredientViewSet` |  |
| `/api/catalog/^product-ingredients/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `ProductIngredientViewSet` |  |
| `/api/catalog/^product-ingredients\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `ProductIngredientViewSet` |  |
| `/api/catalog/^product-interactions/$` | GET,POST | `ProductInteractionViewSet` |  |
| `/api/catalog/^product-interactions/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `ProductInteractionViewSet` |  |
| `/api/catalog/^product-interactions/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `ProductInteractionViewSet` |  |
| `/api/catalog/^product-interactions\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `ProductInteractionViewSet` |  |
| `/api/catalog/^product-prices/$` | GET,POST | `ProductPriceViewSet` |  |
| `/api/catalog/^product-prices/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `ProductPriceViewSet` |  |
| `/api/catalog/^product-prices/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `ProductPriceViewSet` |  |
| `/api/catalog/^product-prices\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `ProductPriceViewSet` |  |
| `/api/catalog/^product-substitutes/$` | GET,POST | `ProductSubstituteViewSet` |  |
| `/api/catalog/^product-substitutes/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `ProductSubstituteViewSet` |  |
| `/api/catalog/^product-substitutes/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `ProductSubstituteViewSet` |  |
| `/api/catalog/^product-substitutes\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `ProductSubstituteViewSet` |  |
| `/api/catalog/^product-uom-conversions/$` | GET,POST | `ProductUomConversionViewSet` |  |
| `/api/catalog/^product-uom-conversions/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `ProductUomConversionViewSet` |  |
| `/api/catalog/^product-uom-conversions/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `ProductUomConversionViewSet` |  |
| `/api/catalog/^product-uom-conversions\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `ProductUomConversionViewSet` |  |
| `/api/catalog/^products/$` | GET,POST | `ProductViewSet` |  |
| `/api/catalog/^products/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `ProductViewSet` |  |
| `/api/catalog/^products/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `ProductViewSet` |  |
| `/api/catalog/^products/import/$` | POST | `ProductViewSet` | Bulk create/update products from CSV rows. |
| `/api/catalog/^products/import\.(?P<format>[a-z0-9]+)/?$` | POST | `ProductViewSet` | Bulk create/update products from CSV rows. |
| `/api/catalog/^products\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `ProductViewSet` |  |
| `/api/catalog/^suppliers/$` | GET,POST | `SupplierViewSet` |  |
| `/api/catalog/^suppliers/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `SupplierViewSet` |  |
| `/api/catalog/^suppliers/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `SupplierViewSet` |  |
| `/api/catalog/^suppliers\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `SupplierViewSet` |  |


## `/api/dashboard`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/dashboard/` | — | `DashboardView` | Operational summary scoped to the orgs the user can see — the home screen. |


## `/api/distribution`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/distribution/` | — | `APIRootView` | The default basic root view for DefaultRouter |
| `/api/distribution/<drf_format_suffix:format>` | — | `APIRootView` | The default basic root view for DefaultRouter |
| `/api/distribution/^backorders/$` | GET | `BackorderViewSet` | Unmet demand — read-only here; it is created by the ordering flow. |
| `/api/distribution/^backorders/(?P<pk>[^/.]+)/$` | GET | `BackorderViewSet` | Unmet demand — read-only here; it is created by the ordering flow. |
| `/api/distribution/^backorders/(?P<pk>[^/.]+)/cancel/$` | POST | `BackorderViewSet` | Unmet demand — read-only here; it is created by the ordering flow. |
| `/api/distribution/^backorders/(?P<pk>[^/.]+)/cancel\.(?P<format>[a-z0-9]+)/?$` | POST | `BackorderViewSet` | Unmet demand — read-only here; it is created by the ordering flow. |
| `/api/distribution/^backorders/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | GET | `BackorderViewSet` | Unmet demand — read-only here; it is created by the ordering flow. |
| `/api/distribution/^backorders\.(?P<format>[a-z0-9]+)/?$` | GET | `BackorderViewSet` | Unmet demand — read-only here; it is created by the ordering flow. |
| `/api/distribution/^grns/$` | GET | `GRNViewSet` | Goods Received Notes — read-only record of what a pharmacy received. |
| `/api/distribution/^grns/(?P<pk>[^/.]+)/$` | GET | `GRNViewSet` | Goods Received Notes — read-only record of what a pharmacy received. |
| `/api/distribution/^grns/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | GET | `GRNViewSet` | Goods Received Notes — read-only record of what a pharmacy received. |
| `/api/distribution/^grns\.(?P<format>[a-z0-9]+)/?$` | GET | `GRNViewSet` | Goods Received Notes — read-only record of what a pharmacy received. |
| `/api/distribution/^in-transit/$` | GET | `InTransitStockViewSet` | Live view of stock on trucks — units dispatched but not yet received. |
| `/api/distribution/^in-transit/(?P<pk>[^/.]+)/$` | GET | `InTransitStockViewSet` | Live view of stock on trucks — units dispatched but not yet received. |
| `/api/distribution/^in-transit/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | GET | `InTransitStockViewSet` | Live view of stock on trucks — units dispatched but not yet received. |
| `/api/distribution/^in-transit\.(?P<format>[a-z0-9]+)/?$` | GET | `InTransitStockViewSet` | Live view of stock on trucks — units dispatched but not yet received. |
| `/api/distribution/^journey-plans/$` | GET,POST | `JourneyPlanViewSet` |  |
| `/api/distribution/^journey-plans/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `JourneyPlanViewSet` |  |
| `/api/distribution/^journey-plans/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `JourneyPlanViewSet` |  |
| `/api/distribution/^journey-plans\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `JourneyPlanViewSet` |  |
| `/api/distribution/^listings/$` | GET,POST | `DepotProductListingViewSet` |  |
| `/api/distribution/^listings/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `DepotProductListingViewSet` |  |
| `/api/distribution/^listings/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `DepotProductListingViewSet` |  |
| `/api/distribution/^listings\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `DepotProductListingViewSet` |  |
| `/api/distribution/^orders/$` | GET,POST | `StockOrderViewSet` | Purchase orders. |
| `/api/distribution/^orders/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `StockOrderViewSet` | Purchase orders. |
| `/api/distribution/^orders/(?P<pk>[^/.]+)/approve/$` | POST | `StockOrderViewSet` | Depot approves a pending order — and the stock leaves in the same step. |
| `/api/distribution/^orders/(?P<pk>[^/.]+)/approve\.(?P<format>[a-z0-9]+)/?$` | POST | `StockOrderViewSet` | Depot approves a pending order — and the stock leaves in the same step. |
| `/api/distribution/^orders/(?P<pk>[^/.]+)/cancel/$` | POST | `StockOrderViewSet` | Purchase orders. |
| `/api/distribution/^orders/(?P<pk>[^/.]+)/cancel\.(?P<format>[a-z0-9]+)/?$` | POST | `StockOrderViewSet` | Purchase orders. |
| `/api/distribution/^orders/(?P<pk>[^/.]+)/receive/$` | POST | `StockOrderViewSet` | Pharmacy confirms the goods arrived; stock lands in one click. |
| `/api/distribution/^orders/(?P<pk>[^/.]+)/receive\.(?P<format>[a-z0-9]+)/?$` | POST | `StockOrderViewSet` | Pharmacy confirms the goods arrived; stock lands in one click. |
| `/api/distribution/^orders/(?P<pk>[^/.]+)/record-payment/$` | POST | `StockOrderViewSet` | Record a payment the pharmacy made to the wholesaler for this order. |
| `/api/distribution/^orders/(?P<pk>[^/.]+)/record-payment\.(?P<format>[a-z0-9]+)/?$` | POST | `StockOrderViewSet` | Record a payment the pharmacy made to the wholesaler for this order. |
| `/api/distribution/^orders/(?P<pk>[^/.]+)/submit/$` | POST | `StockOrderViewSet` | Purchase orders. |
| `/api/distribution/^orders/(?P<pk>[^/.]+)/submit\.(?P<format>[a-z0-9]+)/?$` | POST | `StockOrderViewSet` | Purchase orders. |
| `/api/distribution/^orders/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `StockOrderViewSet` | Purchase orders. |
| `/api/distribution/^orders\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `StockOrderViewSet` | Purchase orders. |
| `/api/distribution/^returns/$` | GET,POST | `CustomerReturnViewSet` |  |
| `/api/distribution/^returns/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `CustomerReturnViewSet` |  |
| `/api/distribution/^returns/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `CustomerReturnViewSet` |  |
| `/api/distribution/^returns\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `CustomerReturnViewSet` |  |
| `/api/distribution/^sales-reps/$` | GET,POST | `SalesRepresentativeViewSet` |  |
| `/api/distribution/^sales-reps/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `SalesRepresentativeViewSet` |  |
| `/api/distribution/^sales-reps/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `SalesRepresentativeViewSet` |  |
| `/api/distribution/^sales-reps\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `SalesRepresentativeViewSet` |  |
| `/api/distribution/^tenders/$` | GET,POST | `TenderContractViewSet` |  |
| `/api/distribution/^tenders/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `TenderContractViewSet` |  |
| `/api/distribution/^tenders/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `TenderContractViewSet` |  |
| `/api/distribution/^tenders\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `TenderContractViewSet` |  |
| `/api/distribution/^van-movements/$` | GET | `VanMovementViewSet` | The audit trail behind every van quantity. |
| `/api/distribution/^van-movements/(?P<pk>[^/.]+)/$` | GET | `VanMovementViewSet` | The audit trail behind every van quantity. |
| `/api/distribution/^van-movements/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | GET | `VanMovementViewSet` | The audit trail behind every van quantity. |
| `/api/distribution/^van-movements\.(?P<format>[a-z0-9]+)/?$` | GET | `VanMovementViewSet` | The audit trail behind every van quantity. |
| `/api/distribution/^van-stock/$` | GET | `VanStockViewSet` | What is on each van. |
| `/api/distribution/^van-stock/(?P<pk>[^/.]+)/$` | GET | `VanStockViewSet` | What is on each van. |
| `/api/distribution/^van-stock/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | GET | `VanStockViewSet` | What is on each van. |
| `/api/distribution/^van-stock\.(?P<format>[a-z0-9]+)/?$` | GET | `VanStockViewSet` | What is on each van. |
| `/api/distribution/^visit-logs/$` | GET,POST | `SalesVisitLogViewSet` |  |
| `/api/distribution/^visit-logs/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `SalesVisitLogViewSet` |  |
| `/api/distribution/^visit-logs/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `SalesVisitLogViewSet` |  |
| `/api/distribution/^visit-logs\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `SalesVisitLogViewSet` |  |
| `/api/distribution/aging/` | — | `AgingView` | Aged receivables (owed to you) and payables (you owe) across visible orgs, bucketed by how overdue each unpaid order is, and grouped by trading partner. |
| `/api/distribution/demand/` | — | `DemandBoardView` | Aggregated demand at a depot — the import shopping list. |
| `/api/distribution/demand/source/` | — | `SourceDemandView` | Turn open demand into a purchase requisition and hand it to procurement. |
| `/api/distribution/overview/` | — | `DistributionOverviewView` | The distribution home: is the storefront healthy, and what is unmet. |
| `/api/distribution/rep-performance/` | — | `RepPerformanceView` | A rep's attainment and commission over a period. |
| `/api/distribution/returns/<int:pk>/<str:verb>/` | — | `ReturnActionsView` | Inspect, approve or reject a customer return. |
| `/api/distribution/sales-reps/<int:pk>/van/` | — | `VanManifestView` | The van's current contents and whether it reconciles. |
| `/api/distribution/sales-reps/<int:pk>/van/<str:verb>/` | — | `VanActionsView` | Load, sell from, or return stock to the depot for a rep's van. |
| `/api/distribution/storefront/` | — | `StorefrontView` | What a buyer may order from a depot right now. |
| `/api/distribution/storefront/availability/` | — | `AvailabilityView` | Resolve one product's availability and price for one buyer. |
| `/api/distribution/storefront/publish/` | — | `PublishListingView` | Create or update what a depot offers — including withdrawing it from sale. |


## `/api/docs`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/docs/` | — | `SpectacularSwaggerView` |  |


## `/api/documents`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/documents/` | — | `APIRootView` | The default basic root view for DefaultRouter |
| `/api/documents/<drf_format_suffix:format>` | — | `APIRootView` | The default basic root view for DefaultRouter |
| `/api/documents/^$` | GET | `DocumentViewSet` | The document vault — read + download, scoped to organizations you can see. |
| `/api/documents/^(?P<pk>[^/.]+)/$` | GET | `DocumentViewSet` | The document vault — read + download, scoped to organizations you can see. |
| `/api/documents/^(?P<pk>[^/.]+)/download/$` | GET | `DocumentViewSet` | The document vault — read + download, scoped to organizations you can see. |
| `/api/documents/^(?P<pk>[^/.]+)/download\.(?P<format>[a-z0-9]+)/?$` | GET | `DocumentViewSet` | The document vault — read + download, scoped to organizations you can see. |
| `/api/documents/^(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | GET | `DocumentViewSet` | The document vault — read + download, scoped to organizations you can see. |
| `/api/documents/^\.(?P<format>[a-z0-9]+)/?$` | GET | `DocumentViewSet` | The document vault — read + download, scoped to organizations you can see. |
| `/api/documents/verify/<str:token>/` | — | `DocumentVerifyView` | Public: verify a document by its QR token — recompute the hash and compare. |


## `/api/events`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/events/health/` | — | `health` | Trivial endpoint — proves the app is mounted. |


## `/api/finance`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/finance/` | — | `APIRootView` | The default basic root view for DefaultRouter |
| `/api/finance/<drf_format_suffix:format>` | — | `APIRootView` | The default basic root view for DefaultRouter |
| `/api/finance/^accounts/$` | GET,POST | `AccountViewSet` |  |
| `/api/finance/^accounts/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `AccountViewSet` |  |
| `/api/finance/^accounts/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `AccountViewSet` |  |
| `/api/finance/^accounts\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `AccountViewSet` |  |
| `/api/finance/^bank-accounts/$` | GET,POST | `BankAccountViewSet` | Bank/MoMo/Airtel/cash accounts — each has its own GL sub-account, cash-book, and reconciliation state. |
| `/api/finance/^bank-accounts/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `BankAccountViewSet` | Bank/MoMo/Airtel/cash accounts — each has its own GL sub-account, cash-book, and reconciliation state. |
| `/api/finance/^bank-accounts/(?P<pk>[^/.]+)/cash-book/$` | GET | `BankAccountViewSet` | Bank/MoMo/Airtel/cash accounts — each has its own GL sub-account, cash-book, and reconciliation state. |
| `/api/finance/^bank-accounts/(?P<pk>[^/.]+)/cash-book\.(?P<format>[a-z0-9]+)/?$` | GET | `BankAccountViewSet` | Bank/MoMo/Airtel/cash accounts — each has its own GL sub-account, cash-book, and reconciliation state. |
| `/api/finance/^bank-accounts/(?P<pk>[^/.]+)/reconcile/$` | POST | `BankAccountViewSet` | Bank/MoMo/Airtel/cash accounts — each has its own GL sub-account, cash-book, and reconciliation state. |
| `/api/finance/^bank-accounts/(?P<pk>[^/.]+)/reconcile\.(?P<format>[a-z0-9]+)/?$` | POST | `BankAccountViewSet` | Bank/MoMo/Airtel/cash accounts — each has its own GL sub-account, cash-book, and reconciliation state. |
| `/api/finance/^bank-accounts/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `BankAccountViewSet` | Bank/MoMo/Airtel/cash accounts — each has its own GL sub-account, cash-book, and reconciliation state. |
| `/api/finance/^bank-accounts\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `BankAccountViewSet` | Bank/MoMo/Airtel/cash accounts — each has its own GL sub-account, cash-book, and reconciliation state. |
| `/api/finance/^bank-statements/$` | GET,POST | `BankStatementViewSet` |  |
| `/api/finance/^bank-statements/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `BankStatementViewSet` |  |
| `/api/finance/^bank-statements/(?P<pk>[^/.]+)/auto-match/$` | POST | `BankStatementViewSet` |  |
| `/api/finance/^bank-statements/(?P<pk>[^/.]+)/auto-match\.(?P<format>[a-z0-9]+)/?$` | POST | `BankStatementViewSet` |  |
| `/api/finance/^bank-statements/(?P<pk>[^/.]+)/close/$` | POST | `BankStatementViewSet` | Sign the reconciliation off, only if it actually reconciles. |
| `/api/finance/^bank-statements/(?P<pk>[^/.]+)/close\.(?P<format>[a-z0-9]+)/?$` | POST | `BankStatementViewSet` | Sign the reconciliation off, only if it actually reconciles. |
| `/api/finance/^bank-statements/(?P<pk>[^/.]+)/lines/$` | GET | `BankStatementViewSet` |  |
| `/api/finance/^bank-statements/(?P<pk>[^/.]+)/lines/(?P<line_id>[^/.]+)/explain/$` | POST | `BankStatementViewSet` | Post a bank line the books never knew about: charges, interest, direct debits. |
| `/api/finance/^bank-statements/(?P<pk>[^/.]+)/lines/(?P<line_id>[^/.]+)/explain\.(?P<format>[a-z0-9]+)/?$` | POST | `BankStatementViewSet` | Post a bank line the books never knew about: charges, interest, direct debits. |
| `/api/finance/^bank-statements/(?P<pk>[^/.]+)/lines/(?P<line_id>[^/.]+)/ignore/$` | POST | `BankStatementViewSet` |  |
| `/api/finance/^bank-statements/(?P<pk>[^/.]+)/lines/(?P<line_id>[^/.]+)/ignore\.(?P<format>[a-z0-9]+)/?$` | POST | `BankStatementViewSet` |  |
| `/api/finance/^bank-statements/(?P<pk>[^/.]+)/lines/(?P<line_id>[^/.]+)/match/$` | POST | `BankStatementViewSet` |  |
| `/api/finance/^bank-statements/(?P<pk>[^/.]+)/lines/(?P<line_id>[^/.]+)/match\.(?P<format>[a-z0-9]+)/?$` | POST | `BankStatementViewSet` |  |
| `/api/finance/^bank-statements/(?P<pk>[^/.]+)/lines/(?P<line_id>[^/.]+)/unmatch/$` | POST | `BankStatementViewSet` |  |
| `/api/finance/^bank-statements/(?P<pk>[^/.]+)/lines/(?P<line_id>[^/.]+)/unmatch\.(?P<format>[a-z0-9]+)/?$` | POST | `BankStatementViewSet` |  |
| `/api/finance/^bank-statements/(?P<pk>[^/.]+)/lines\.(?P<format>[a-z0-9]+)/?$` | GET | `BankStatementViewSet` |  |
| `/api/finance/^bank-statements/(?P<pk>[^/.]+)/suggestions/$` | GET | `BankStatementViewSet` | Candidate ledger lines for each unmatched bank line, best first. |
| `/api/finance/^bank-statements/(?P<pk>[^/.]+)/suggestions\.(?P<format>[a-z0-9]+)/?$` | GET | `BankStatementViewSet` | Candidate ledger lines for each unmatched bank line, best first. |
| `/api/finance/^bank-statements/(?P<pk>[^/.]+)/summary/$` | GET | `BankStatementViewSet` | The four-line reconciliation statement plus the unexplained difference. |
| `/api/finance/^bank-statements/(?P<pk>[^/.]+)/summary\.(?P<format>[a-z0-9]+)/?$` | GET | `BankStatementViewSet` | The four-line reconciliation statement plus the unexplained difference. |
| `/api/finance/^bank-statements/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `BankStatementViewSet` |  |
| `/api/finance/^bank-statements/import-csv/$` | POST | `BankStatementViewSet` | Import a bank CSV. |
| `/api/finance/^bank-statements/import-csv\.(?P<format>[a-z0-9]+)/?$` | POST | `BankStatementViewSet` | Import a bank CSV. |
| `/api/finance/^bank-statements/unexplained/$` | GET | `BankStatementViewSet` | Everything still unaccounted for on one account, across all its statements. |
| `/api/finance/^bank-statements/unexplained\.(?P<format>[a-z0-9]+)/?$` | GET | `BankStatementViewSet` | Everything still unaccounted for on one account, across all its statements. |
| `/api/finance/^bank-statements\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `BankStatementViewSet` |  |
| `/api/finance/^budgets/$` | GET,POST | `BudgetViewSet` | Budget plans and their lines. |
| `/api/finance/^budgets/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `BudgetViewSet` | Budget plans and their lines. |
| `/api/finance/^budgets/(?P<pk>[^/.]+)/approve/$` | POST | `BudgetViewSet` | Approve the plan. |
| `/api/finance/^budgets/(?P<pk>[^/.]+)/approve\.(?P<format>[a-z0-9]+)/?$` | POST | `BudgetViewSet` | Approve the plan. |
| `/api/finance/^budgets/(?P<pk>[^/.]+)/lock/$` | POST | `BudgetViewSet` | Freeze the plan. |
| `/api/finance/^budgets/(?P<pk>[^/.]+)/lock\.(?P<format>[a-z0-9]+)/?$` | POST | `BudgetViewSet` | Freeze the plan. |
| `/api/finance/^budgets/(?P<pk>[^/.]+)/variance/$` | GET | `BudgetViewSet` | Budget vs actual, with actuals read from the general ledger. |
| `/api/finance/^budgets/(?P<pk>[^/.]+)/variance\.(?P<format>[a-z0-9]+)/?$` | GET | `BudgetViewSet` | Budget vs actual, with actuals read from the general ledger. |
| `/api/finance/^budgets/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `BudgetViewSet` | Budget plans and their lines. |
| `/api/finance/^budgets\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `BudgetViewSet` | Budget plans and their lines. |
| `/api/finance/^cash-flow-forecast/$` | GET | `CashFlowForecastView` | A real cash-flow projection built from unpaid B2B receivables and supplier-bill payables due, bucketed by how soon they're due. |
| `/api/finance/^cash-flow-forecast\.(?P<format>[a-z0-9]+)/?$` | GET | `CashFlowForecastView` | A real cash-flow projection built from unpaid B2B receivables and supplier-bill payables due, bucketed by how soon they're due. |
| `/api/finance/^cost-centres/$` | GET,POST | `CostCentreViewSet` | The ledger's analysis dimension — branches, departments, functions. |
| `/api/finance/^cost-centres/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `CostCentreViewSet` | The ledger's analysis dimension — branches, departments, functions. |
| `/api/finance/^cost-centres/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `CostCentreViewSet` | The ledger's analysis dimension — branches, departments, functions. |
| `/api/finance/^cost-centres/pnl/$` | GET | `CostCentreViewSet` | Contribution by cost centre — revenue, cost of sales and opex per centre. |
| `/api/finance/^cost-centres/pnl\.(?P<format>[a-z0-9]+)/?$` | GET | `CostCentreViewSet` | Contribution by cost centre — revenue, cost of sales and opex per centre. |
| `/api/finance/^cost-centres\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `CostCentreViewSet` | The ledger's analysis dimension — branches, departments, functions. |
| `/api/finance/^credit-profiles/$` | GET,POST | `CreditProfileViewSet` | Customer-credit profiles. |
| `/api/finance/^credit-profiles/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `CreditProfileViewSet` | Customer-credit profiles. |
| `/api/finance/^credit-profiles/(?P<pk>[^/.]+)/request-override/$` | POST | `CreditProfileViewSet` | Customer-credit profiles. |
| `/api/finance/^credit-profiles/(?P<pk>[^/.]+)/request-override\.(?P<format>[a-z0-9]+)/?$` | POST | `CreditProfileViewSet` | Customer-credit profiles. |
| `/api/finance/^credit-profiles/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `CreditProfileViewSet` | Customer-credit profiles. |
| `/api/finance/^credit-profiles\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `CreditProfileViewSet` | Customer-credit profiles. |
| `/api/finance/^customer-credits/$` | GET | `CustomerCreditViewSet` | On-account credits (overpayments, credit notes, returns) held for a customer. |
| `/api/finance/^customer-credits/(?P<pk>[^/.]+)/$` | GET | `CustomerCreditViewSet` | On-account credits (overpayments, credit notes, returns) held for a customer. |
| `/api/finance/^customer-credits/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | GET | `CustomerCreditViewSet` | On-account credits (overpayments, credit notes, returns) held for a customer. |
| `/api/finance/^customer-credits\.(?P<format>[a-z0-9]+)/?$` | GET | `CustomerCreditViewSet` | On-account credits (overpayments, credit notes, returns) held for a customer. |
| `/api/finance/^customer-invoices/$` | GET,POST | `CustomerInvoiceViewSet` | AR: invoices raised on B2B customers, plus the receipts against them. |
| `/api/finance/^customer-invoices/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `CustomerInvoiceViewSet` | AR: invoices raised on B2B customers, plus the receipts against them. |
| `/api/finance/^customer-invoices/(?P<pk>[^/.]+)/cancel/$` | POST | `CustomerInvoiceViewSet` | Void a customer invoice and post the reversal entry. |
| `/api/finance/^customer-invoices/(?P<pk>[^/.]+)/cancel\.(?P<format>[a-z0-9]+)/?$` | POST | `CustomerInvoiceViewSet` | Void a customer invoice and post the reversal entry. |
| `/api/finance/^customer-invoices/(?P<pk>[^/.]+)/record-receipt/$` | POST | `CustomerInvoiceViewSet` | AR: invoices raised on B2B customers, plus the receipts against them. |
| `/api/finance/^customer-invoices/(?P<pk>[^/.]+)/record-receipt\.(?P<format>[a-z0-9]+)/?$` | POST | `CustomerInvoiceViewSet` | AR: invoices raised on B2B customers, plus the receipts against them. |
| `/api/finance/^customer-invoices/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `CustomerInvoiceViewSet` | AR: invoices raised on B2B customers, plus the receipts against them. |
| `/api/finance/^customer-invoices\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `CustomerInvoiceViewSet` | AR: invoices raised on B2B customers, plus the receipts against them. |
| `/api/finance/^customer-receipts/$` | GET | `CustomerReceiptViewSet` | Receipt register. |
| `/api/finance/^customer-receipts/(?P<pk>[^/.]+)/$` | GET | `CustomerReceiptViewSet` | Receipt register. |
| `/api/finance/^customer-receipts/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | GET | `CustomerReceiptViewSet` | Receipt register. |
| `/api/finance/^customer-receipts\.(?P<format>[a-z0-9]+)/?$` | GET | `CustomerReceiptViewSet` | Receipt register. |
| `/api/finance/^documents/credit-note/$` | POST | `FinanceDocumentsView` | Turn finance records into numbered, hashed, QR-verified PDFs. |
| `/api/finance/^documents/credit-note\.(?P<format>[a-z0-9]+)/?$` | POST | `FinanceDocumentsView` | Turn finance records into numbered, hashed, QR-verified PDFs. |
| `/api/finance/^documents/financial-statements/$` | POST | `FinanceDocumentsView` | P&L, balance sheet and trial balance as one filed pack. |
| `/api/finance/^documents/financial-statements\.(?P<format>[a-z0-9]+)/?$` | POST | `FinanceDocumentsView` | P&L, balance sheet and trial balance as one filed pack. |
| `/api/finance/^documents/invoice/$` | POST | `FinanceDocumentsView` | Turn finance records into numbered, hashed, QR-verified PDFs. |
| `/api/finance/^documents/invoice\.(?P<format>[a-z0-9]+)/?$` | POST | `FinanceDocumentsView` | Turn finance records into numbered, hashed, QR-verified PDFs. |
| `/api/finance/^documents/journal-voucher/$` | POST | `FinanceDocumentsView` | Turn finance records into numbered, hashed, QR-verified PDFs. |
| `/api/finance/^documents/journal-voucher\.(?P<format>[a-z0-9]+)/?$` | POST | `FinanceDocumentsView` | Turn finance records into numbered, hashed, QR-verified PDFs. |
| `/api/finance/^documents/payment-voucher/$` | POST | `FinanceDocumentsView` | Turn finance records into numbered, hashed, QR-verified PDFs. |
| `/api/finance/^documents/payment-voucher\.(?P<format>[a-z0-9]+)/?$` | POST | `FinanceDocumentsView` | Turn finance records into numbered, hashed, QR-verified PDFs. |
| `/api/finance/^documents/receipt/$` | POST | `FinanceDocumentsView` | Turn finance records into numbered, hashed, QR-verified PDFs. |
| `/api/finance/^documents/receipt\.(?P<format>[a-z0-9]+)/?$` | POST | `FinanceDocumentsView` | Turn finance records into numbered, hashed, QR-verified PDFs. |
| `/api/finance/^documents/remittance-advice/$` | POST | `FinanceDocumentsView` | Tell a supplier which invoices a bulk payment settled. |
| `/api/finance/^documents/remittance-advice\.(?P<format>[a-z0-9]+)/?$` | POST | `FinanceDocumentsView` | Tell a supplier which invoices a bulk payment settled. |
| `/api/finance/^documents/statement/$` | POST | `FinanceDocumentsView` | The statement of account — what a customer disputing a balance needs. |
| `/api/finance/^documents/statement\.(?P<format>[a-z0-9]+)/?$` | POST | `FinanceDocumentsView` | The statement of account — what a customer disputing a balance needs. |
| `/api/finance/^documents/vat-return/$` | POST | `FinanceDocumentsView` | The filed copy — a CSV draft proves nothing after the fact. |
| `/api/finance/^documents/vat-return\.(?P<format>[a-z0-9]+)/?$` | POST | `FinanceDocumentsView` | The filed copy — a CSV draft proves nothing after the fact. |
| `/api/finance/^dunning-notices/$` | GET | `DunningNoticeViewSet` | The collections queue. |
| `/api/finance/^dunning-notices/(?P<pk>[^/.]+)/$` | GET | `DunningNoticeViewSet` | The collections queue. |
| `/api/finance/^dunning-notices/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | GET | `DunningNoticeViewSet` | The collections queue. |
| `/api/finance/^dunning-notices/run/$` | POST | `DunningNoticeViewSet` | The collections queue. |
| `/api/finance/^dunning-notices/run\.(?P<format>[a-z0-9]+)/?$` | POST | `DunningNoticeViewSet` | The collections queue. |
| `/api/finance/^dunning-notices\.(?P<format>[a-z0-9]+)/?$` | GET | `DunningNoticeViewSet` | The collections queue. |
| `/api/finance/^fixed-assets/$` | GET,POST | `FixedAssetViewSet` |  |
| `/api/finance/^fixed-assets/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `FixedAssetViewSet` |  |
| `/api/finance/^fixed-assets/(?P<pk>[^/.]+)/dispose/$` | POST | `FixedAssetViewSet` | Mark an asset disposed and post the disposal entry to the GL. |
| `/api/finance/^fixed-assets/(?P<pk>[^/.]+)/dispose\.(?P<format>[a-z0-9]+)/?$` | POST | `FixedAssetViewSet` | Mark an asset disposed and post the disposal entry to the GL. |
| `/api/finance/^fixed-assets/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `FixedAssetViewSet` |  |
| `/api/finance/^fixed-assets\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `FixedAssetViewSet` |  |
| `/api/finance/^journal-entries/$` | GET,POST | `JournalEntryViewSet` | Journal entries: read for anyone with finance.view; posting a manual entry requires finance.manage. |
| `/api/finance/^journal-entries/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `JournalEntryViewSet` | Journal entries: read for anyone with finance.view; posting a manual entry requires finance.manage. |
| `/api/finance/^journal-entries/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `JournalEntryViewSet` | Journal entries: read for anyone with finance.view; posting a manual entry requires finance.manage. |
| `/api/finance/^journal-entries\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `JournalEntryViewSet` | Journal entries: read for anyone with finance.view; posting a manual entry requires finance.manage. |
| `/api/finance/^operations/card-settlement/$` | POST | `FinanceOperationsView` | The month-end and treasury postings that keep the ledger faithful to operations: depreciation, the IAS 2 stock provision, and card settlement. |
| `/api/finance/^operations/card-settlement\.(?P<format>[a-z0-9]+)/?$` | POST | `FinanceOperationsView` | The month-end and treasury postings that keep the ledger faithful to operations: depreciation, the IAS 2 stock provision, and card settlement. |
| `/api/finance/^operations/depreciation/$` | POST | `FinanceOperationsView` | The month-end and treasury postings that keep the ledger faithful to operations: depreciation, the IAS 2 stock provision, and card settlement. |
| `/api/finance/^operations/depreciation\.(?P<format>[a-z0-9]+)/?$` | POST | `FinanceOperationsView` | The month-end and treasury postings that keep the ledger faithful to operations: depreciation, the IAS 2 stock provision, and card settlement. |
| `/api/finance/^operations/exchange-rate/$` | POST | `FinanceOperationsView` | Record a published rate. |
| `/api/finance/^operations/exchange-rate\.(?P<format>[a-z0-9]+)/?$` | POST | `FinanceOperationsView` | Record a published rate. |
| `/api/finance/^operations/expiry-provision/$` | POST | `FinanceOperationsView` | The month-end and treasury postings that keep the ledger faithful to operations: depreciation, the IAS 2 stock provision, and card settlement. |
| `/api/finance/^operations/expiry-provision\.(?P<format>[a-z0-9]+)/?$` | POST | `FinanceOperationsView` | The month-end and treasury postings that keep the ledger faithful to operations: depreciation, the IAS 2 stock provision, and card settlement. |
| `/api/finance/^operations/fx-exposure/$` | GET | `FinanceOperationsView` | What the currency is doing to open foreign balances, before posting. |
| `/api/finance/^operations/fx-exposure\.(?P<format>[a-z0-9]+)/?$` | GET | `FinanceOperationsView` | What the currency is doing to open foreign balances, before posting. |
| `/api/finance/^operations/fx-revaluation/$` | POST | `FinanceOperationsView` | Restate open foreign monetary balances at the closing rate (IAS 21). |
| `/api/finance/^operations/fx-revaluation\.(?P<format>[a-z0-9]+)/?$` | POST | `FinanceOperationsView` | Restate open foreign monetary balances at the closing rate (IAS 21). |
| `/api/finance/^operations/money-map/$` | GET | `FinanceOperationsView` | Every money source in the business and whether it reached the ledger. |
| `/api/finance/^operations/money-map\.(?P<format>[a-z0-9]+)/?$` | GET | `FinanceOperationsView` | Every money source in the business and whether it reached the ledger. |
| `/api/finance/^payment-runs/$` | GET,POST | `PaymentRunViewSet` | Batch supplier settlement: build a run, get it signed off, hand the file to the bank, then post the payments. |
| `/api/finance/^payment-runs/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `PaymentRunViewSet` | Batch supplier settlement: build a run, get it signed off, hand the file to the bank, then post the payments. |
| `/api/finance/^payment-runs/(?P<pk>[^/.]+)/cancel/$` | POST | `PaymentRunViewSet` | Batch supplier settlement: build a run, get it signed off, hand the file to the bank, then post the payments. |
| `/api/finance/^payment-runs/(?P<pk>[^/.]+)/cancel\.(?P<format>[a-z0-9]+)/?$` | POST | `PaymentRunViewSet` | Batch supplier settlement: build a run, get it signed off, hand the file to the bank, then post the payments. |
| `/api/finance/^payment-runs/(?P<pk>[^/.]+)/disburse/$` | POST | `PaymentRunViewSet` | Batch supplier settlement: build a run, get it signed off, hand the file to the bank, then post the payments. |
| `/api/finance/^payment-runs/(?P<pk>[^/.]+)/disburse\.(?P<format>[a-z0-9]+)/?$` | POST | `PaymentRunViewSet` | Batch supplier settlement: build a run, get it signed off, hand the file to the bank, then post the payments. |
| `/api/finance/^payment-runs/(?P<pk>[^/.]+)/disbursement-file/$` | GET | `PaymentRunViewSet` | Download the CSV the bank or MoMo aggregator expects. |
| `/api/finance/^payment-runs/(?P<pk>[^/.]+)/disbursement-file\.(?P<format>[a-z0-9]+)/?$` | GET | `PaymentRunViewSet` | Download the CSV the bank or MoMo aggregator expects. |
| `/api/finance/^payment-runs/(?P<pk>[^/.]+)/lock/$` | POST | `PaymentRunViewSet` | Batch supplier settlement: build a run, get it signed off, hand the file to the bank, then post the payments. |
| `/api/finance/^payment-runs/(?P<pk>[^/.]+)/lock\.(?P<format>[a-z0-9]+)/?$` | POST | `PaymentRunViewSet` | Batch supplier settlement: build a run, get it signed off, hand the file to the bank, then post the payments. |
| `/api/finance/^payment-runs/(?P<pk>[^/.]+)/submit/$` | POST | `PaymentRunViewSet` | Batch supplier settlement: build a run, get it signed off, hand the file to the bank, then post the payments. |
| `/api/finance/^payment-runs/(?P<pk>[^/.]+)/submit\.(?P<format>[a-z0-9]+)/?$` | POST | `PaymentRunViewSet` | Batch supplier settlement: build a run, get it signed off, hand the file to the bank, then post the payments. |
| `/api/finance/^payment-runs/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `PaymentRunViewSet` | Batch supplier settlement: build a run, get it signed off, hand the file to the bank, then post the payments. |
| `/api/finance/^payment-runs\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `PaymentRunViewSet` | Batch supplier settlement: build a run, get it signed off, hand the file to the bank, then post the payments. |
| `/api/finance/^periods/$` | GET,POST | `AccountingPeriodViewSet` | EOD/EOM/annual closeouts. |
| `/api/finance/^periods/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `AccountingPeriodViewSet` | EOD/EOM/annual closeouts. |
| `/api/finance/^periods/(?P<pk>[^/.]+)/checklist/$` | GET,POST | `AccountingPeriodViewSet` | The close checklist for this period, seeded on first request. |
| `/api/finance/^periods/(?P<pk>[^/.]+)/checklist/(?P<task_id>[^/.]+)/$` | POST | `AccountingPeriodViewSet` | Mark one checklist item done, or waive it with a reason. |
| `/api/finance/^periods/(?P<pk>[^/.]+)/checklist/(?P<task_id>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | POST | `AccountingPeriodViewSet` | Mark one checklist item done, or waive it with a reason. |
| `/api/finance/^periods/(?P<pk>[^/.]+)/checklist\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `AccountingPeriodViewSet` | The close checklist for this period, seeded on first request. |
| `/api/finance/^periods/(?P<pk>[^/.]+)/reopen/$` | POST | `AccountingPeriodViewSet` | EOD/EOM/annual closeouts. |
| `/api/finance/^periods/(?P<pk>[^/.]+)/reopen\.(?P<format>[a-z0-9]+)/?$` | POST | `AccountingPeriodViewSet` | EOD/EOM/annual closeouts. |
| `/api/finance/^periods/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `AccountingPeriodViewSet` | EOD/EOM/annual closeouts. |
| `/api/finance/^periods\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `AccountingPeriodViewSet` | EOD/EOM/annual closeouts. |
| `/api/finance/^reports/ar-aging/$` | GET | `FinanceReportsView` | Open receivables bucketed by how far past due they are, per customer. |
| `/api/finance/^reports/ar-aging\.(?P<format>[a-z0-9]+)/?$` | GET | `FinanceReportsView` | Open receivables bucketed by how far past due they are, per customer. |
| `/api/finance/^reports/balance-sheet/$` | GET | `FinanceReportsView` | Statements over the ledger: trial balance, P&L, balance sheet, cash-flow, the performance cockpit, and HQ consolidation. |
| `/api/finance/^reports/balance-sheet\.(?P<format>[a-z0-9]+)/?$` | GET | `FinanceReportsView` | Statements over the ledger: trial balance, P&L, balance sheet, cash-flow, the performance cockpit, and HQ consolidation. |
| `/api/finance/^reports/branch-comparison/$` | GET | `FinanceReportsView` | HQ's view: every visible branch side by side on the numbers that matter. |
| `/api/finance/^reports/branch-comparison\.(?P<format>[a-z0-9]+)/?$` | GET | `FinanceReportsView` | HQ's view: every visible branch side by side on the numbers that matter. |
| `/api/finance/^reports/break-even/$` | GET | `FinanceReportsView` | Revenue needed to cover fixed costs, and the margin of safety on it. |
| `/api/finance/^reports/break-even\.(?P<format>[a-z0-9]+)/?$` | GET | `FinanceReportsView` | Revenue needed to cover fixed costs, and the margin of safety on it. |
| `/api/finance/^reports/cash-flow/$` | GET | `FinanceReportsView` | Statements over the ledger: trial balance, P&L, balance sheet, cash-flow, the performance cockpit, and HQ consolidation. |
| `/api/finance/^reports/cash-flow\.(?P<format>[a-z0-9]+)/?$` | GET | `FinanceReportsView` | Statements over the ledger: trial balance, P&L, balance sheet, cash-flow, the performance cockpit, and HQ consolidation. |
| `/api/finance/^reports/consolidated/$` | GET | `FinanceReportsView` | Group view across every branch the caller can see (HQ consolidation). |
| `/api/finance/^reports/consolidated\.(?P<format>[a-z0-9]+)/?$` | GET | `FinanceReportsView` | Group view across every branch the caller can see (HQ consolidation). |
| `/api/finance/^reports/expiry-exposure/$` | GET | `FinanceReportsView` | Stock at risk of expiring, banded, with the IAS 2 provision it implies. |
| `/api/finance/^reports/expiry-exposure\.(?P<format>[a-z0-9]+)/?$` | GET | `FinanceReportsView` | Stock at risk of expiring, banded, with the IAS 2 provision it implies. |
| `/api/finance/^reports/inventory-valuation/$` | GET | `FinanceReportsView` | Live on-hand × wholesale cost by product. |
| `/api/finance/^reports/inventory-valuation\.(?P<format>[a-z0-9]+)/?$` | GET | `FinanceReportsView` | Live on-hand × wholesale cost by product. |
| `/api/finance/^reports/performance/$` | GET | `FinanceReportsView` | Statements over the ledger: trial balance, P&L, balance sheet, cash-flow, the performance cockpit, and HQ consolidation. |
| `/api/finance/^reports/performance\.(?P<format>[a-z0-9]+)/?$` | GET | `FinanceReportsView` | Statements over the ledger: trial balance, P&L, balance sheet, cash-flow, the performance cockpit, and HQ consolidation. |
| `/api/finance/^reports/pharmacy-cockpit/$` | GET | `FinanceReportsView` | Profit, cash cycle, expiry risk, break-even and margin mix in one call. |
| `/api/finance/^reports/pharmacy-cockpit\.(?P<format>[a-z0-9]+)/?$` | GET | `FinanceReportsView` | Profit, cash cycle, expiry risk, break-even and margin mix in one call. |
| `/api/finance/^reports/profit-and-loss/$` | GET | `FinanceReportsView` | Statements over the ledger: trial balance, P&L, balance sheet, cash-flow, the performance cockpit, and HQ consolidation. |
| `/api/finance/^reports/profit-and-loss\.(?P<format>[a-z0-9]+)/?$` | GET | `FinanceReportsView` | Statements over the ledger: trial balance, P&L, balance sheet, cash-flow, the performance cockpit, and HQ consolidation. |
| `/api/finance/^reports/statement/$` | GET | `FinanceReportsView` | A printable statement of account for one customer over a period. |
| `/api/finance/^reports/statement\.(?P<format>[a-z0-9]+)/?$` | GET | `FinanceReportsView` | A printable statement of account for one customer over a period. |
| `/api/finance/^reports/trial-balance/$` | GET | `FinanceReportsView` | Statements over the ledger: trial balance, P&L, balance sheet, cash-flow, the performance cockpit, and HQ consolidation. |
| `/api/finance/^reports/trial-balance\.(?P<format>[a-z0-9]+)/?$` | GET | `FinanceReportsView` | Statements over the ledger: trial balance, P&L, balance sheet, cash-flow, the performance cockpit, and HQ consolidation. |
| `/api/finance/^reports/vat-return/$` | GET | `FinanceReportsView` | Rwanda VAT return draft for the period: per-class Output/Input, withholding, net payable, paid in period, amount due, plus a CSV body ready for the accountant to file via RRA e-Tax. |
| `/api/finance/^reports/vat-return\.(?P<format>[a-z0-9]+)/?$` | GET | `FinanceReportsView` | Rwanda VAT return draft for the period: per-class Output/Input, withholding, net payable, paid in period, amount due, plus a CSV body ready for the accountant to file via RRA e-Tax. |
| `/api/finance/^reports/working-capital/$` | GET | `FinanceReportsView` | DIO + DSO − DPO: how many days of cash the business has to fund. |
| `/api/finance/^reports/working-capital\.(?P<format>[a-z0-9]+)/?$` | GET | `FinanceReportsView` | DIO + DSO − DPO: how many days of cash the business has to fund. |
| `/api/finance/^schedules/$` | GET,POST | `RecurringScheduleViewSet` | Prepayments and accruals. |
| `/api/finance/^schedules/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `RecurringScheduleViewSet` | Prepayments and accruals. |
| `/api/finance/^schedules/(?P<pk>[^/.]+)/cancel/$` | POST | `RecurringScheduleViewSet` | Stop future charges. |
| `/api/finance/^schedules/(?P<pk>[^/.]+)/cancel\.(?P<format>[a-z0-9]+)/?$` | POST | `RecurringScheduleViewSet` | Stop future charges. |
| `/api/finance/^schedules/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `RecurringScheduleViewSet` | Prepayments and accruals. |
| `/api/finance/^schedules/run/$` | POST | `RecurringScheduleViewSet` | Post every schedule due up to the given month, catching up if behind. |
| `/api/finance/^schedules/run\.(?P<format>[a-z0-9]+)/?$` | POST | `RecurringScheduleViewSet` | Post every schedule due up to the given month, catching up if behind. |
| `/api/finance/^schedules/summary/$` | GET | `RecurringScheduleViewSet` | What is still sitting in prepayments and accruals, and what is overdue to post. |
| `/api/finance/^schedules/summary\.(?P<format>[a-z0-9]+)/?$` | GET | `RecurringScheduleViewSet` | What is still sitting in prepayments and accruals, and what is overdue to post. |
| `/api/finance/^schedules\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `RecurringScheduleViewSet` | Prepayments and accruals. |
| `/api/finance/^supplier-bills/$` | GET,POST | `SupplierBillViewSet` | AP: supplier bills + payments. |
| `/api/finance/^supplier-bills/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `SupplierBillViewSet` | AP: supplier bills + payments. |
| `/api/finance/^supplier-bills/(?P<pk>[^/.]+)/record-payment/$` | POST | `SupplierBillViewSet` | AP: supplier bills + payments. |
| `/api/finance/^supplier-bills/(?P<pk>[^/.]+)/record-payment\.(?P<format>[a-z0-9]+)/?$` | POST | `SupplierBillViewSet` | AP: supplier bills + payments. |
| `/api/finance/^supplier-bills/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `SupplierBillViewSet` | AP: supplier bills + payments. |
| `/api/finance/^supplier-bills\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `SupplierBillViewSet` | AP: supplier bills + payments. |
| `/api/finance/^tax-codes/$` | GET,POST | `TaxCodeViewSet` | Rwanda VAT tax codes (A/B/C/D). |
| `/api/finance/^tax-codes/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `TaxCodeViewSet` | Rwanda VAT tax codes (A/B/C/D). |
| `/api/finance/^tax-codes/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `TaxCodeViewSet` | Rwanda VAT tax codes (A/B/C/D). |
| `/api/finance/^tax-codes\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `TaxCodeViewSet` | Rwanda VAT tax codes (A/B/C/D). |
| `/api/finance/^tax-payments/$` | GET,POST | `TaxPaymentViewSet` | Register of RRA remittances. |
| `/api/finance/^tax-payments/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `TaxPaymentViewSet` | Register of RRA remittances. |
| `/api/finance/^tax-payments/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `TaxPaymentViewSet` | Register of RRA remittances. |
| `/api/finance/^tax-payments\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `TaxPaymentViewSet` | Register of RRA remittances. |
| `/api/finance/^tax-records/$` | GET | `TaxRecordViewSet` |  |
| `/api/finance/^tax-records/(?P<pk>[^/.]+)/$` | GET | `TaxRecordViewSet` |  |
| `/api/finance/^tax-records/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | GET | `TaxRecordViewSet` |  |
| `/api/finance/^tax-records\.(?P<format>[a-z0-9]+)/?$` | GET | `TaxRecordViewSet` |  |
| `/api/finance/^tenant-settings/$` | GET | `TenantSettingsViewSet` | Return the singleton for the resolved org. |
| `/api/finance/^tenant-settings/(?P<pk>[^/.]+)/$` | GET,PATCH | `TenantSettingsViewSet` | Per-tenant configuration singleton (costing method, FX provider, pay period, statutory remittance day, PIT deadline). |
| `/api/finance/^tenant-settings/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | GET,PATCH | `TenantSettingsViewSet` | Per-tenant configuration singleton (costing method, FX provider, pay period, statutory remittance day, PIT deadline). |
| `/api/finance/^tenant-settings\.(?P<format>[a-z0-9]+)/?$` | GET | `TenantSettingsViewSet` | Return the singleton for the resolved org. |


## `/api/hr`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/hr/` | — | `APIRootView` | The default basic root view for DefaultRouter |
| `/api/hr/<drf_format_suffix:format>` | — | `APIRootView` | The default basic root view for DefaultRouter |
| `/api/hr/^applicants/$` | GET,POST | `ApplicantViewSet` |  |
| `/api/hr/^applicants/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `ApplicantViewSet` |  |
| `/api/hr/^applicants/(?P<pk>[^/.]+)/advance/$` | POST | `ApplicantViewSet` | Move the applicant to the next stage of the funnel. |
| `/api/hr/^applicants/(?P<pk>[^/.]+)/advance\.(?P<format>[a-z0-9]+)/?$` | POST | `ApplicantViewSet` | Move the applicant to the next stage of the funnel. |
| `/api/hr/^applicants/(?P<pk>[^/.]+)/hire/$` | POST | `ApplicantViewSet` | Convert the applicant into an employee, contract and onboarding. |
| `/api/hr/^applicants/(?P<pk>[^/.]+)/hire\.(?P<format>[a-z0-9]+)/?$` | POST | `ApplicantViewSet` | Convert the applicant into an employee, contract and onboarding. |
| `/api/hr/^applicants/(?P<pk>[^/.]+)/reject/$` | POST | `ApplicantViewSet` |  |
| `/api/hr/^applicants/(?P<pk>[^/.]+)/reject\.(?P<format>[a-z0-9]+)/?$` | POST | `ApplicantViewSet` |  |
| `/api/hr/^applicants/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `ApplicantViewSet` |  |
| `/api/hr/^applicants\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `ApplicantViewSet` |  |
| `/api/hr/^attendance/$` | GET,POST | `AttendanceLogViewSet` |  |
| `/api/hr/^attendance/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `AttendanceLogViewSet` |  |
| `/api/hr/^attendance/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `AttendanceLogViewSet` |  |
| `/api/hr/^attendance/clock/$` | POST | `AttendanceLogViewSet` | Toggle today's attendance for the caller. |
| `/api/hr/^attendance/clock\.(?P<format>[a-z0-9]+)/?$` | POST | `AttendanceLogViewSet` | Toggle today's attendance for the caller. |
| `/api/hr/^attendance\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `AttendanceLogViewSet` |  |
| `/api/hr/^checklist-items/$` | GET,POST | `ChecklistItemViewSet` |  |
| `/api/hr/^checklist-items/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `ChecklistItemViewSet` |  |
| `/api/hr/^checklist-items/(?P<pk>[^/.]+)/toggle/$` | POST | `ChecklistItemViewSet` |  |
| `/api/hr/^checklist-items/(?P<pk>[^/.]+)/toggle\.(?P<format>[a-z0-9]+)/?$` | POST | `ChecklistItemViewSet` |  |
| `/api/hr/^checklist-items/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `ChecklistItemViewSet` |  |
| `/api/hr/^checklist-items\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `ChecklistItemViewSet` |  |
| `/api/hr/^competencies/$` | GET,POST | `CompetencyAssessmentViewSet` |  |
| `/api/hr/^competencies/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `CompetencyAssessmentViewSet` |  |
| `/api/hr/^competencies/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `CompetencyAssessmentViewSet` |  |
| `/api/hr/^competencies\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `CompetencyAssessmentViewSet` |  |
| `/api/hr/^contracts/$` | GET,POST | `EmploymentContractViewSet` |  |
| `/api/hr/^contracts/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `EmploymentContractViewSet` |  |
| `/api/hr/^contracts/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `EmploymentContractViewSet` |  |
| `/api/hr/^contracts/issue/$` | POST | `EmploymentContractViewSet` | Open a new contract, superseding whatever was current. |
| `/api/hr/^contracts/issue\.(?P<format>[a-z0-9]+)/?$` | POST | `EmploymentContractViewSet` | Open a new contract, superseding whatever was current. |
| `/api/hr/^contracts\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `EmploymentContractViewSet` |  |
| `/api/hr/^cpd/$` | GET,POST | `CPDRecordViewSet` |  |
| `/api/hr/^cpd/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `CPDRecordViewSet` |  |
| `/api/hr/^cpd/(?P<pk>[^/.]+)/verify/$` | POST | `CPDRecordViewSet` |  |
| `/api/hr/^cpd/(?P<pk>[^/.]+)/verify\.(?P<format>[a-z0-9]+)/?$` | POST | `CPDRecordViewSet` |  |
| `/api/hr/^cpd/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `CPDRecordViewSet` |  |
| `/api/hr/^cpd\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `CPDRecordViewSet` |  |
| `/api/hr/^disciplinary/$` | GET,POST | `DisciplinaryActionViewSet` |  |
| `/api/hr/^disciplinary/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `DisciplinaryActionViewSet` |  |
| `/api/hr/^disciplinary/(?P<pk>[^/.]+)/issue/$` | POST | `DisciplinaryActionViewSet` |  |
| `/api/hr/^disciplinary/(?P<pk>[^/.]+)/issue\.(?P<format>[a-z0-9]+)/?$` | POST | `DisciplinaryActionViewSet` |  |
| `/api/hr/^disciplinary/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `DisciplinaryActionViewSet` |  |
| `/api/hr/^disciplinary\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `DisciplinaryActionViewSet` |  |
| `/api/hr/^employees/$` | GET,POST | `EmployeeViewSet` |  |
| `/api/hr/^employees/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `EmployeeViewSet` |  |
| `/api/hr/^employees/(?P<pk>[^/.]+)/documents/$` | POST | `EmployeeViewSet` |  |
| `/api/hr/^employees/(?P<pk>[^/.]+)/documents\.(?P<format>[a-z0-9]+)/?$` | POST | `EmployeeViewSet` |  |
| `/api/hr/^employees/(?P<pk>[^/.]+)/request-termination/$` | POST | `EmployeeViewSet` | Propose ending this employee's employment — routed through the approvals engine (no self-approval, senior sign-off required). |
| `/api/hr/^employees/(?P<pk>[^/.]+)/request-termination\.(?P<format>[a-z0-9]+)/?$` | POST | `EmployeeViewSet` | Propose ending this employee's employment — routed through the approvals engine (no self-approval, senior sign-off required). |
| `/api/hr/^employees/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `EmployeeViewSet` |  |
| `/api/hr/^employees\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `EmployeeViewSet` |  |
| `/api/hr/^filings/$` | GET,POST | `StatutoryFilingViewSet` |  |
| `/api/hr/^filings/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `StatutoryFilingViewSet` |  |
| `/api/hr/^filings/(?P<pk>[^/.]+)/mark-filed/$` | POST | `StatutoryFilingViewSet` |  |
| `/api/hr/^filings/(?P<pk>[^/.]+)/mark-filed\.(?P<format>[a-z0-9]+)/?$` | POST | `StatutoryFilingViewSet` |  |
| `/api/hr/^filings/(?P<pk>[^/.]+)/mark-paid/$` | POST | `StatutoryFilingViewSet` |  |
| `/api/hr/^filings/(?P<pk>[^/.]+)/mark-paid\.(?P<format>[a-z0-9]+)/?$` | POST | `StatutoryFilingViewSet` |  |
| `/api/hr/^filings/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `StatutoryFilingViewSet` |  |
| `/api/hr/^filings/generate/$` | POST | `StatutoryFilingViewSet` | Aggregate the period's payroll into a return, ready to file. |
| `/api/hr/^filings/generate\.(?P<format>[a-z0-9]+)/?$` | POST | `StatutoryFilingViewSet` | Aggregate the period's payroll into a return, ready to file. |
| `/api/hr/^filings\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `StatutoryFilingViewSet` |  |
| `/api/hr/^interviews/$` | GET,POST | `InterviewSlotViewSet` |  |
| `/api/hr/^interviews/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `InterviewSlotViewSet` |  |
| `/api/hr/^interviews/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `InterviewSlotViewSet` |  |
| `/api/hr/^interviews\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `InterviewSlotViewSet` |  |
| `/api/hr/^leave-balances/$` | GET,POST | `LeaveBalanceViewSet` |  |
| `/api/hr/^leave-balances/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `LeaveBalanceViewSet` |  |
| `/api/hr/^leave-balances/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `LeaveBalanceViewSet` |  |
| `/api/hr/^leave-balances/accrue/$` | POST | `LeaveBalanceViewSet` | Post this month's accrual across the organization (idempotent). |
| `/api/hr/^leave-balances/accrue\.(?P<format>[a-z0-9]+)/?$` | POST | `LeaveBalanceViewSet` | Post this month's accrual across the organization (idempotent). |
| `/api/hr/^leave-balances\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `LeaveBalanceViewSet` |  |
| `/api/hr/^leave-types/$` | GET,POST | `LeaveTypeViewSet` |  |
| `/api/hr/^leave-types/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `LeaveTypeViewSet` |  |
| `/api/hr/^leave-types/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `LeaveTypeViewSet` |  |
| `/api/hr/^leave-types/seed_defaults/$` | POST | `LeaveTypeViewSet` | Create the Rwanda Labour Code leave types for an organization. |
| `/api/hr/^leave-types/seed_defaults\.(?P<format>[a-z0-9]+)/?$` | POST | `LeaveTypeViewSet` | Create the Rwanda Labour Code leave types for an organization. |
| `/api/hr/^leave-types\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `LeaveTypeViewSet` |  |
| `/api/hr/^leave/$` | GET,POST | `LeaveRequestViewSet` |  |
| `/api/hr/^leave/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `LeaveRequestViewSet` |  |
| `/api/hr/^leave/(?P<pk>[^/.]+)/approve/$` | POST | `LeaveRequestViewSet` |  |
| `/api/hr/^leave/(?P<pk>[^/.]+)/approve\.(?P<format>[a-z0-9]+)/?$` | POST | `LeaveRequestViewSet` |  |
| `/api/hr/^leave/(?P<pk>[^/.]+)/reject/$` | POST | `LeaveRequestViewSet` |  |
| `/api/hr/^leave/(?P<pk>[^/.]+)/reject\.(?P<format>[a-z0-9]+)/?$` | POST | `LeaveRequestViewSet` |  |
| `/api/hr/^leave/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `LeaveRequestViewSet` |  |
| `/api/hr/^leave\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `LeaveRequestViewSet` |  |
| `/api/hr/^loans/$` | GET,POST | `LoanAdvanceViewSet` |  |
| `/api/hr/^loans/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `LoanAdvanceViewSet` |  |
| `/api/hr/^loans/(?P<pk>[^/.]+)/approve/$` | POST | `LoanAdvanceViewSet` |  |
| `/api/hr/^loans/(?P<pk>[^/.]+)/approve\.(?P<format>[a-z0-9]+)/?$` | POST | `LoanAdvanceViewSet` |  |
| `/api/hr/^loans/(?P<pk>[^/.]+)/disburse/$` | POST | `LoanAdvanceViewSet` |  |
| `/api/hr/^loans/(?P<pk>[^/.]+)/disburse\.(?P<format>[a-z0-9]+)/?$` | POST | `LoanAdvanceViewSet` |  |
| `/api/hr/^loans/(?P<pk>[^/.]+)/write_off/$` | POST | `LoanAdvanceViewSet` |  |
| `/api/hr/^loans/(?P<pk>[^/.]+)/write_off\.(?P<format>[a-z0-9]+)/?$` | POST | `LoanAdvanceViewSet` |  |
| `/api/hr/^loans/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `LoanAdvanceViewSet` |  |
| `/api/hr/^loans\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `LoanAdvanceViewSet` |  |
| `/api/hr/^onboarding/$` | GET,POST | `OnboardingViewSet` |  |
| `/api/hr/^onboarding/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `OnboardingViewSet` |  |
| `/api/hr/^onboarding/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `OnboardingViewSet` |  |
| `/api/hr/^onboarding/start/$` | POST | `OnboardingViewSet` |  |
| `/api/hr/^onboarding/start\.(?P<format>[a-z0-9]+)/?$` | POST | `OnboardingViewSet` |  |
| `/api/hr/^onboarding\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `OnboardingViewSet` |  |
| `/api/hr/^payroll-adjustments/$` | GET,POST | `PayrollAdjustmentViewSet` |  |
| `/api/hr/^payroll-adjustments/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `PayrollAdjustmentViewSet` |  |
| `/api/hr/^payroll-adjustments/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `PayrollAdjustmentViewSet` |  |
| `/api/hr/^payroll-adjustments\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `PayrollAdjustmentViewSet` |  |
| `/api/hr/^payroll-runs/$` | GET,POST | `PayrollRunViewSet` | Payroll runs: build (compute) → submit (approval-gated) → the approvals engine's approve/reject decides it → mark paid (bank/MoMo disbursement). |
| `/api/hr/^payroll-runs/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `PayrollRunViewSet` | Payroll runs: build (compute) → submit (approval-gated) → the approvals engine's approve/reject decides it → mark paid (bank/MoMo disbursement). |
| `/api/hr/^payroll-runs/(?P<pk>[^/.]+)/mark-paid/$` | POST | `PayrollRunViewSet` | Payroll runs: build (compute) → submit (approval-gated) → the approvals engine's approve/reject decides it → mark paid (bank/MoMo disbursement). |
| `/api/hr/^payroll-runs/(?P<pk>[^/.]+)/mark-paid\.(?P<format>[a-z0-9]+)/?$` | POST | `PayrollRunViewSet` | Payroll runs: build (compute) → submit (approval-gated) → the approvals engine's approve/reject decides it → mark paid (bank/MoMo disbursement). |
| `/api/hr/^payroll-runs/(?P<pk>[^/.]+)/submit/$` | POST | `PayrollRunViewSet` | Payroll runs: build (compute) → submit (approval-gated) → the approvals engine's approve/reject decides it → mark paid (bank/MoMo disbursement). |
| `/api/hr/^payroll-runs/(?P<pk>[^/.]+)/submit\.(?P<format>[a-z0-9]+)/?$` | POST | `PayrollRunViewSet` | Payroll runs: build (compute) → submit (approval-gated) → the approvals engine's approve/reject decides it → mark paid (bank/MoMo disbursement). |
| `/api/hr/^payroll-runs/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `PayrollRunViewSet` | Payroll runs: build (compute) → submit (approval-gated) → the approvals engine's approve/reject decides it → mark paid (bank/MoMo disbursement). |
| `/api/hr/^payroll-runs\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `PayrollRunViewSet` | Payroll runs: build (compute) → submit (approval-gated) → the approvals engine's approve/reject decides it → mark paid (bank/MoMo disbursement). |
| `/api/hr/^requisitions/$` | GET,POST | `JobRequisitionViewSet` |  |
| `/api/hr/^requisitions/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `JobRequisitionViewSet` |  |
| `/api/hr/^requisitions/(?P<pk>[^/.]+)/close/$` | POST | `JobRequisitionViewSet` |  |
| `/api/hr/^requisitions/(?P<pk>[^/.]+)/close\.(?P<format>[a-z0-9]+)/?$` | POST | `JobRequisitionViewSet` |  |
| `/api/hr/^requisitions/(?P<pk>[^/.]+)/open/$` | POST | `JobRequisitionViewSet` |  |
| `/api/hr/^requisitions/(?P<pk>[^/.]+)/open\.(?P<format>[a-z0-9]+)/?$` | POST | `JobRequisitionViewSet` |  |
| `/api/hr/^requisitions/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `JobRequisitionViewSet` |  |
| `/api/hr/^requisitions\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `JobRequisitionViewSet` |  |
| `/api/hr/^reviews/$` | GET,POST | `PerformanceReviewViewSet` |  |
| `/api/hr/^reviews/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `PerformanceReviewViewSet` |  |
| `/api/hr/^reviews/(?P<pk>[^/.]+)/acknowledge/$` | POST | `PerformanceReviewViewSet` |  |
| `/api/hr/^reviews/(?P<pk>[^/.]+)/acknowledge\.(?P<format>[a-z0-9]+)/?$` | POST | `PerformanceReviewViewSet` |  |
| `/api/hr/^reviews/(?P<pk>[^/.]+)/complete/$` | POST | `PerformanceReviewViewSet` |  |
| `/api/hr/^reviews/(?P<pk>[^/.]+)/complete\.(?P<format>[a-z0-9]+)/?$` | POST | `PerformanceReviewViewSet` |  |
| `/api/hr/^reviews/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `PerformanceReviewViewSet` |  |
| `/api/hr/^reviews\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `PerformanceReviewViewSet` |  |
| `/api/hr/^roster/$` | GET,POST | `ShiftRosterViewSet` |  |
| `/api/hr/^roster/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `ShiftRosterViewSet` |  |
| `/api/hr/^roster/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `ShiftRosterViewSet` |  |
| `/api/hr/^roster\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `ShiftRosterViewSet` |  |
| `/api/hr/^salary-revisions/$` | GET,POST | `SalaryRevisionViewSet` |  |
| `/api/hr/^salary-revisions/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `SalaryRevisionViewSet` |  |
| `/api/hr/^salary-revisions/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `SalaryRevisionViewSet` |  |
| `/api/hr/^salary-revisions\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `SalaryRevisionViewSet` |  |
| `/api/hr/^salary-structures/$` | GET,POST | `SalaryStructureViewSet` |  |
| `/api/hr/^salary-structures/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `SalaryStructureViewSet` |  |
| `/api/hr/^salary-structures/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `SalaryStructureViewSet` |  |
| `/api/hr/^salary-structures/set_for_employee/$` | POST | `SalaryStructureViewSet` | Open a new effective-dated structure and record the revision. |
| `/api/hr/^salary-structures/set_for_employee\.(?P<format>[a-z0-9]+)/?$` | POST | `SalaryStructureViewSet` | Open a new effective-dated structure and record the revision. |
| `/api/hr/^salary-structures\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `SalaryStructureViewSet` |  |
| `/api/hr/^statutory-rates/$` | GET | `StatutoryRateViewSet` | The versioned PAYE/RSSB/CBHI rate table the payroll engine reads from. |
| `/api/hr/^statutory-rates/(?P<pk>[^/.]+)/$` | GET | `StatutoryRateViewSet` | The versioned PAYE/RSSB/CBHI rate table the payroll engine reads from. |
| `/api/hr/^statutory-rates/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | GET | `StatutoryRateViewSet` | The versioned PAYE/RSSB/CBHI rate table the payroll engine reads from. |
| `/api/hr/^statutory-rates\.(?P<format>[a-z0-9]+)/?$` | GET | `StatutoryRateViewSet` | The versioned PAYE/RSSB/CBHI rate table the payroll engine reads from. |
| `/api/hr/^terminations/$` | GET,POST | `TerminationViewSet` |  |
| `/api/hr/^terminations/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `TerminationViewSet` |  |
| `/api/hr/^terminations/(?P<pk>[^/.]+)/approve/$` | POST | `TerminationViewSet` |  |
| `/api/hr/^terminations/(?P<pk>[^/.]+)/approve\.(?P<format>[a-z0-9]+)/?$` | POST | `TerminationViewSet` |  |
| `/api/hr/^terminations/(?P<pk>[^/.]+)/mark-paid/$` | POST | `TerminationViewSet` |  |
| `/api/hr/^terminations/(?P<pk>[^/.]+)/mark-paid\.(?P<format>[a-z0-9]+)/?$` | POST | `TerminationViewSet` |  |
| `/api/hr/^terminations/(?P<pk>[^/.]+)/recompute/$` | POST | `TerminationViewSet` | Re-run the final settlement (after clearing a loan, say). |
| `/api/hr/^terminations/(?P<pk>[^/.]+)/recompute\.(?P<format>[a-z0-9]+)/?$` | POST | `TerminationViewSet` | Re-run the final settlement (after clearing a loan, say). |
| `/api/hr/^terminations/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `TerminationViewSet` |  |
| `/api/hr/^terminations/initiate/$` | POST | `TerminationViewSet` |  |
| `/api/hr/^terminations/initiate\.(?P<format>[a-z0-9]+)/?$` | POST | `TerminationViewSet` |  |
| `/api/hr/^terminations\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `TerminationViewSet` |  |
| `/api/hr/^timesheets/$` | GET,POST | `TimesheetViewSet` |  |
| `/api/hr/^timesheets/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `TimesheetViewSet` |  |
| `/api/hr/^timesheets/(?P<pk>[^/.]+)/approve/$` | POST | `TimesheetViewSet` |  |
| `/api/hr/^timesheets/(?P<pk>[^/.]+)/approve\.(?P<format>[a-z0-9]+)/?$` | POST | `TimesheetViewSet` |  |
| `/api/hr/^timesheets/(?P<pk>[^/.]+)/reject/$` | POST | `TimesheetViewSet` |  |
| `/api/hr/^timesheets/(?P<pk>[^/.]+)/reject\.(?P<format>[a-z0-9]+)/?$` | POST | `TimesheetViewSet` |  |
| `/api/hr/^timesheets/(?P<pk>[^/.]+)/submit/$` | POST | `TimesheetViewSet` |  |
| `/api/hr/^timesheets/(?P<pk>[^/.]+)/submit\.(?P<format>[a-z0-9]+)/?$` | POST | `TimesheetViewSet` |  |
| `/api/hr/^timesheets/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `TimesheetViewSet` |  |
| `/api/hr/^timesheets/build/$` | POST | `TimesheetViewSet` | Derive timesheets for a period from attendance, roster and leave. |
| `/api/hr/^timesheets/build\.(?P<format>[a-z0-9]+)/?$` | POST | `TimesheetViewSet` | Derive timesheets for a period from attendance, roster and leave. |
| `/api/hr/^timesheets\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `TimesheetViewSet` |  |
| `/api/hr/^training/$` | GET,POST | `TrainingRecordViewSet` |  |
| `/api/hr/^training/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `TrainingRecordViewSet` |  |
| `/api/hr/^training/(?P<pk>[^/.]+)/acknowledge/$` | POST | `TrainingRecordViewSet` |  |
| `/api/hr/^training/(?P<pk>[^/.]+)/acknowledge\.(?P<format>[a-z0-9]+)/?$` | POST | `TrainingRecordViewSet` |  |
| `/api/hr/^training/(?P<pk>[^/.]+)/complete/$` | POST | `TrainingRecordViewSet` |  |
| `/api/hr/^training/(?P<pk>[^/.]+)/complete\.(?P<format>[a-z0-9]+)/?$` | POST | `TrainingRecordViewSet` |  |
| `/api/hr/^training/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `TrainingRecordViewSet` |  |
| `/api/hr/^training\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `TrainingRecordViewSet` |  |
| `/api/hr/overview/` | — | `PeopleOverviewView` | Headline numbers and the compliance warning list for the People home. |


## `/api/inventory`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/inventory/` | — | `APIRootView` | The default basic root view for DefaultRouter |
| `/api/inventory/<drf_format_suffix:format>` | — | `APIRootView` | The default basic root view for DefaultRouter |
| `/api/inventory/^batches/$` | GET | `InventoryBatchViewSet` | Batch stock-on-hand, org-scoped, FEFO-ordered (soonest expiry first). |
| `/api/inventory/^batches/(?P<pk>[^/.]+)/$` | GET | `InventoryBatchViewSet` | Batch stock-on-hand, org-scoped, FEFO-ordered (soonest expiry first). |
| `/api/inventory/^batches/(?P<pk>[^/.]+)/adjust/$` | POST | `InventoryBatchViewSet` | Batch stock-on-hand, org-scoped, FEFO-ordered (soonest expiry first). |
| `/api/inventory/^batches/(?P<pk>[^/.]+)/adjust\.(?P<format>[a-z0-9]+)/?$` | POST | `InventoryBatchViewSet` | Batch stock-on-hand, org-scoped, FEFO-ordered (soonest expiry first). |
| `/api/inventory/^batches/(?P<pk>[^/.]+)/putaway/$` | POST | `InventoryBatchViewSet` | Commit the put-away — move the lot into a concrete bin. |
| `/api/inventory/^batches/(?P<pk>[^/.]+)/putaway\.(?P<format>[a-z0-9]+)/?$` | POST | `InventoryBatchViewSet` | Commit the put-away — move the lot into a concrete bin. |
| `/api/inventory/^batches/(?P<pk>[^/.]+)/putaway_suggestion/$` | GET | `InventoryBatchViewSet` | Where this lot should go, and the rule that decided it. |
| `/api/inventory/^batches/(?P<pk>[^/.]+)/putaway_suggestion\.(?P<format>[a-z0-9]+)/?$` | GET | `InventoryBatchViewSet` | Where this lot should go, and the rule that decided it. |
| `/api/inventory/^batches/(?P<pk>[^/.]+)/waste/$` | POST | `InventoryBatchViewSet` | Batch stock-on-hand, org-scoped, FEFO-ordered (soonest expiry first). |
| `/api/inventory/^batches/(?P<pk>[^/.]+)/waste\.(?P<format>[a-z0-9]+)/?$` | POST | `InventoryBatchViewSet` | Batch stock-on-hand, org-scoped, FEFO-ordered (soonest expiry first). |
| `/api/inventory/^batches/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | GET | `InventoryBatchViewSet` | Batch stock-on-hand, org-scoped, FEFO-ordered (soonest expiry first). |
| `/api/inventory/^batches\.(?P<format>[a-z0-9]+)/?$` | GET | `InventoryBatchViewSet` | Batch stock-on-hand, org-scoped, FEFO-ordered (soonest expiry first). |
| `/api/inventory/^bin-locations/$` | GET,POST | `BinLocationViewSet` |  |
| `/api/inventory/^bin-locations/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `BinLocationViewSet` |  |
| `/api/inventory/^bin-locations/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `BinLocationViewSet` |  |
| `/api/inventory/^bin-locations\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `BinLocationViewSet` |  |
| `/api/inventory/^calibrations/$` | GET,POST | `SensorCalibrationViewSet` |  |
| `/api/inventory/^calibrations/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `SensorCalibrationViewSet` |  |
| `/api/inventory/^calibrations/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `SensorCalibrationViewSet` |  |
| `/api/inventory/^calibrations\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `SensorCalibrationViewSet` |  |
| `/api/inventory/^consignment-consumptions/$` | GET | `ConsignmentConsumptionViewSet` |  |
| `/api/inventory/^consignment-consumptions/(?P<pk>[^/.]+)/$` | GET | `ConsignmentConsumptionViewSet` |  |
| `/api/inventory/^consignment-consumptions/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | GET | `ConsignmentConsumptionViewSet` |  |
| `/api/inventory/^consignment-consumptions\.(?P<format>[a-z0-9]+)/?$` | GET | `ConsignmentConsumptionViewSet` |  |
| `/api/inventory/^consignment-settlements/$` | GET | `ConsignmentSettlementViewSet` |  |
| `/api/inventory/^consignment-settlements/(?P<pk>[^/.]+)/$` | GET | `ConsignmentSettlementViewSet` |  |
| `/api/inventory/^consignment-settlements/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | GET | `ConsignmentSettlementViewSet` |  |
| `/api/inventory/^consignment-settlements\.(?P<format>[a-z0-9]+)/?$` | GET | `ConsignmentSettlementViewSet` |  |
| `/api/inventory/^consignments/$` | GET,POST | `ConsignmentAgreementViewSet` | Supplier-owned stock held on our shelves: ownership only transfers on use. |
| `/api/inventory/^consignments/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `ConsignmentAgreementViewSet` | Supplier-owned stock held on our shelves: ownership only transfers on use. |
| `/api/inventory/^consignments/(?P<pk>[^/.]+)/position/$` | GET | `ConsignmentAgreementViewSet` | Stock held under the agreement plus the unsettled liability. |
| `/api/inventory/^consignments/(?P<pk>[^/.]+)/position\.(?P<format>[a-z0-9]+)/?$` | GET | `ConsignmentAgreementViewSet` | Stock held under the agreement plus the unsettled liability. |
| `/api/inventory/^consignments/(?P<pk>[^/.]+)/settle/$` | POST | `ConsignmentAgreementViewSet` | Roll a period's consumptions into a settlement (and an AP bill if owed). |
| `/api/inventory/^consignments/(?P<pk>[^/.]+)/settle\.(?P<format>[a-z0-9]+)/?$` | POST | `ConsignmentAgreementViewSet` | Roll a period's consumptions into a settlement (and an AP bill if owed). |
| `/api/inventory/^consignments/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `ConsignmentAgreementViewSet` | Supplier-owned stock held on our shelves: ownership only transfers on use. |
| `/api/inventory/^consignments\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `ConsignmentAgreementViewSet` | Supplier-owned stock held on our shelves: ownership only transfers on use. |
| `/api/inventory/^disposals/$` | GET,POST | `StockDisposalViewSet` |  |
| `/api/inventory/^disposals/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `StockDisposalViewSet` |  |
| `/api/inventory/^disposals/(?P<pk>[^/.]+)/confirm_destruction/$` | POST | `StockDisposalViewSet` |  |
| `/api/inventory/^disposals/(?P<pk>[^/.]+)/confirm_destruction\.(?P<format>[a-z0-9]+)/?$` | POST | `StockDisposalViewSet` |  |
| `/api/inventory/^disposals/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `StockDisposalViewSet` |  |
| `/api/inventory/^disposals\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `StockDisposalViewSet` |  |
| `/api/inventory/^epcis-events/$` | GET | `EpcisEventViewSet` | EPCIS events are an evidentiary record — readable and exportable, never edited. |
| `/api/inventory/^epcis-events/(?P<pk>[^/.]+)/$` | GET | `EpcisEventViewSet` | EPCIS events are an evidentiary record — readable and exportable, never edited. |
| `/api/inventory/^epcis-events/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | GET | `EpcisEventViewSet` | EPCIS events are an evidentiary record — readable and exportable, never edited. |
| `/api/inventory/^epcis-events/export/$` | GET | `EpcisEventViewSet` | EPCIS 2.0 JSON-LD document for a regulator or trading partner. |
| `/api/inventory/^epcis-events/export\.(?P<format>[a-z0-9]+)/?$` | GET | `EpcisEventViewSet` | EPCIS 2.0 JSON-LD document for a regulator or trading partner. |
| `/api/inventory/^epcis-events\.(?P<format>[a-z0-9]+)/?$` | GET | `EpcisEventViewSet` | EPCIS events are an evidentiary record — readable and exportable, never edited. |
| `/api/inventory/^excursions/$` | GET,POST | `ExcursionInvestigationViewSet` |  |
| `/api/inventory/^excursions/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `ExcursionInvestigationViewSet` |  |
| `/api/inventory/^excursions/(?P<pk>[^/.]+)/close/$` | POST | `ExcursionInvestigationViewSet` | Apply QA's disposition to the affected lots and close the record. |
| `/api/inventory/^excursions/(?P<pk>[^/.]+)/close\.(?P<format>[a-z0-9]+)/?$` | POST | `ExcursionInvestigationViewSet` | Apply QA's disposition to the affected lots and close the record. |
| `/api/inventory/^excursions/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `ExcursionInvestigationViewSet` |  |
| `/api/inventory/^excursions/open_from_window/$` | POST | `ExcursionInvestigationViewSet` | Open an investigation over a time window, populated from the sensor log. |
| `/api/inventory/^excursions/open_from_window\.(?P<format>[a-z0-9]+)/?$` | POST | `ExcursionInvestigationViewSet` | Open an investigation over a time window, populated from the sensor log. |
| `/api/inventory/^excursions\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `ExcursionInvestigationViewSet` |  |
| `/api/inventory/^movements/$` | GET | `StockMovementViewSet` |  |
| `/api/inventory/^movements/(?P<pk>[^/.]+)/$` | GET | `StockMovementViewSet` |  |
| `/api/inventory/^movements/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | GET | `StockMovementViewSet` |  |
| `/api/inventory/^movements\.(?P<format>[a-z0-9]+)/?$` | GET | `StockMovementViewSet` |  |
| `/api/inventory/^pharmacy-products/$` | GET,POST | `PharmacyProductViewSet` |  |
| `/api/inventory/^pharmacy-products/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `PharmacyProductViewSet` |  |
| `/api/inventory/^pharmacy-products/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `PharmacyProductViewSet` |  |
| `/api/inventory/^pharmacy-products\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `PharmacyProductViewSet` |  |
| `/api/inventory/^pick-tasks/$` | GET,POST | `PickTaskViewSet` |  |
| `/api/inventory/^pick-tasks/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `PickTaskViewSet` |  |
| `/api/inventory/^pick-tasks/(?P<pk>[^/.]+)/confirm/$` | POST | `PickTaskViewSet` | Confirm what actually came off the shelf; a short pick is recorded as short. |
| `/api/inventory/^pick-tasks/(?P<pk>[^/.]+)/confirm\.(?P<format>[a-z0-9]+)/?$` | POST | `PickTaskViewSet` | Confirm what actually came off the shelf; a short pick is recorded as short. |
| `/api/inventory/^pick-tasks/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `PickTaskViewSet` |  |
| `/api/inventory/^pick-tasks\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `PickTaskViewSet` |  |
| `/api/inventory/^pick-waves/$` | GET,POST | `PickWaveViewSet` |  |
| `/api/inventory/^pick-waves/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `PickWaveViewSet` |  |
| `/api/inventory/^pick-waves/(?P<pk>[^/.]+)/build_tasks/$` | POST | `PickWaveViewSet` | Turn demand lines into FEFO pick tasks, ordered along the picker's walk. |
| `/api/inventory/^pick-waves/(?P<pk>[^/.]+)/build_tasks\.(?P<format>[a-z0-9]+)/?$` | POST | `PickWaveViewSet` | Turn demand lines into FEFO pick tasks, ordered along the picker's walk. |
| `/api/inventory/^pick-waves/(?P<pk>[^/.]+)/cancel/$` | POST | `PickWaveViewSet` | Cancel the wave and hand every un-picked reservation back to free stock. |
| `/api/inventory/^pick-waves/(?P<pk>[^/.]+)/cancel\.(?P<format>[a-z0-9]+)/?$` | POST | `PickWaveViewSet` | Cancel the wave and hand every un-picked reservation back to free stock. |
| `/api/inventory/^pick-waves/(?P<pk>[^/.]+)/release/$` | POST | `PickWaveViewSet` | Release to the floor, reserving each task's stock as it goes. |
| `/api/inventory/^pick-waves/(?P<pk>[^/.]+)/release\.(?P<format>[a-z0-9]+)/?$` | POST | `PickWaveViewSet` | Release to the floor, reserving each task's stock as it goes. |
| `/api/inventory/^pick-waves/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `PickWaveViewSet` |  |
| `/api/inventory/^pick-waves\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `PickWaveViewSet` |  |
| `/api/inventory/^putaway-rules/$` | GET,POST | `PutawayRuleViewSet` |  |
| `/api/inventory/^putaway-rules/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `PutawayRuleViewSet` |  |
| `/api/inventory/^putaway-rules/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `PutawayRuleViewSet` |  |
| `/api/inventory/^putaway-rules/simulate/$` | GET | `PutawayRuleViewSet` | Dry-run the rule set against a product — which rule wins, and which bin. |
| `/api/inventory/^putaway-rules/simulate\.(?P<format>[a-z0-9]+)/?$` | GET | `PutawayRuleViewSet` | Dry-run the rule set against a product — which rule wins, and which bin. |
| `/api/inventory/^putaway-rules\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `PutawayRuleViewSet` |  |
| `/api/inventory/^quality-checks/$` | GET,POST | `QualityCheckViewSet` |  |
| `/api/inventory/^quality-checks/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `QualityCheckViewSet` |  |
| `/api/inventory/^quality-checks/(?P<pk>[^/.]+)/fail_qc/$` | POST | `QualityCheckViewSet` |  |
| `/api/inventory/^quality-checks/(?P<pk>[^/.]+)/fail_qc\.(?P<format>[a-z0-9]+)/?$` | POST | `QualityCheckViewSet` |  |
| `/api/inventory/^quality-checks/(?P<pk>[^/.]+)/pass_qc/$` | POST | `QualityCheckViewSet` |  |
| `/api/inventory/^quality-checks/(?P<pk>[^/.]+)/pass_qc\.(?P<format>[a-z0-9]+)/?$` | POST | `QualityCheckViewSet` |  |
| `/api/inventory/^quality-checks/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `QualityCheckViewSet` |  |
| `/api/inventory/^quality-checks\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `QualityCheckViewSet` |  |
| `/api/inventory/^recalls/$` | GET,POST | `BatchRecallViewSet` |  |
| `/api/inventory/^recalls/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `BatchRecallViewSet` |  |
| `/api/inventory/^recalls/(?P<pk>[^/.]+)/execute_freeze/$` | POST | `BatchRecallViewSet` |  |
| `/api/inventory/^recalls/(?P<pk>[^/.]+)/execute_freeze\.(?P<format>[a-z0-9]+)/?$` | POST | `BatchRecallViewSet` |  |
| `/api/inventory/^recalls/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `BatchRecallViewSet` |  |
| `/api/inventory/^recalls\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `BatchRecallViewSet` |  |
| `/api/inventory/^reorder-rules/$` | GET,POST | `ReorderRuleViewSet` |  |
| `/api/inventory/^reorder-rules/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `ReorderRuleViewSet` |  |
| `/api/inventory/^reorder-rules/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `ReorderRuleViewSet` |  |
| `/api/inventory/^reorder-rules/abc_xyz/$` | GET | `ReorderRuleViewSet` | The 3x3 ABC/XYZ grid — counts and stock value in each cell. |
| `/api/inventory/^reorder-rules/abc_xyz\.(?P<format>[a-z0-9]+)/?$` | GET | `ReorderRuleViewSet` | The 3x3 ABC/XYZ grid — counts and stock value in each cell. |
| `/api/inventory/^reorder-rules/near_expiry/$` | GET | `ReorderRuleViewSet` | Batches approaching expiry, each with the action still open to it. |
| `/api/inventory/^reorder-rules/near_expiry\.(?P<format>[a-z0-9]+)/?$` | GET | `ReorderRuleViewSet` | Batches approaching expiry, each with the action still open to it. |
| `/api/inventory/^reorder-rules/recompute/$` | POST | `ReorderRuleViewSet` | Refresh demand stats, ABC/XYZ and the reorder levers from movement history. |
| `/api/inventory/^reorder-rules/recompute\.(?P<format>[a-z0-9]+)/?$` | POST | `ReorderRuleViewSet` | Refresh demand stats, ABC/XYZ and the reorder levers from movement history. |
| `/api/inventory/^reorder-rules/slow_dead/$` | GET | `ReorderRuleViewSet` | Batches that have not moved, with the capital they are tying up. |
| `/api/inventory/^reorder-rules/slow_dead\.(?P<format>[a-z0-9]+)/?$` | GET | `ReorderRuleViewSet` | Batches that have not moved, with the capital they are tying up. |
| `/api/inventory/^reorder-rules/suggestions/$` | GET | `ReorderRuleViewSet` | Everything at or below its reorder point, with the quantity to buy. |
| `/api/inventory/^reorder-rules/suggestions\.(?P<format>[a-z0-9]+)/?$` | GET | `ReorderRuleViewSet` | Everything at or below its reorder point, with the quantity to buy. |
| `/api/inventory/^reorder-rules\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `ReorderRuleViewSet` |  |
| `/api/inventory/^serial-units/$` | GET,POST | `SerialUnitViewSet` | Serialised units are created by scanning, not by posting a form. |
| `/api/inventory/^serial-units/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `SerialUnitViewSet` | Serialised units are created by scanning, not by posting a form. |
| `/api/inventory/^serial-units/(?P<pk>[^/.]+)/aggregate/$` | POST | `SerialUnitViewSet` | Pack the named units into this one (each -> case -> pallet). |
| `/api/inventory/^serial-units/(?P<pk>[^/.]+)/aggregate\.(?P<format>[a-z0-9]+)/?$` | POST | `SerialUnitViewSet` | Pack the named units into this one (each -> case -> pallet). |
| `/api/inventory/^serial-units/(?P<pk>[^/.]+)/disaggregate/$` | POST | `SerialUnitViewSet` | Unpack — all children, or only the named ones. |
| `/api/inventory/^serial-units/(?P<pk>[^/.]+)/disaggregate\.(?P<format>[a-z0-9]+)/?$` | POST | `SerialUnitViewSet` | Unpack — all children, or only the named ones. |
| `/api/inventory/^serial-units/(?P<pk>[^/.]+)/trace/$` | GET | `SerialUnitViewSet` | Full chain-of-custody: identity, parents, children, every event. |
| `/api/inventory/^serial-units/(?P<pk>[^/.]+)/trace\.(?P<format>[a-z0-9]+)/?$` | GET | `SerialUnitViewSet` | Full chain-of-custody: identity, parents, children, every event. |
| `/api/inventory/^serial-units/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `SerialUnitViewSet` | Serialised units are created by scanning, not by posting a form. |
| `/api/inventory/^serial-units/observe/$` | POST | `SerialUnitViewSet` | Record a business step (ship / receive / dispense / hold) against units. |
| `/api/inventory/^serial-units/observe\.(?P<format>[a-z0-9]+)/?$` | POST | `SerialUnitViewSet` | Record a business step (ship / receive / dispense / hold) against units. |
| `/api/inventory/^serial-units/parse/$` | POST | `SerialUnitViewSet` | Decode a barcode without touching stock — the 'what is this?' button. |
| `/api/inventory/^serial-units/parse\.(?P<format>[a-z0-9]+)/?$` | POST | `SerialUnitViewSet` | Decode a barcode without touching stock — the 'what is this?' button. |
| `/api/inventory/^serial-units/scan/$` | POST | `SerialUnitViewSet` | Parse a scanned DataMatrix and commission (or re-find) the unit it names. |
| `/api/inventory/^serial-units/scan\.(?P<format>[a-z0-9]+)/?$` | POST | `SerialUnitViewSet` | Parse a scanned DataMatrix and commission (or re-find) the unit it names. |
| `/api/inventory/^serial-units\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `SerialUnitViewSet` | Serialised units are created by scanning, not by posting a form. |
| `/api/inventory/^stock-counts/$` | GET,POST | `StockCountViewSet` |  |
| `/api/inventory/^stock-counts/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `StockCountViewSet` |  |
| `/api/inventory/^stock-counts/(?P<pk>[^/.]+)/approve_count/$` | POST | `StockCountViewSet` |  |
| `/api/inventory/^stock-counts/(?P<pk>[^/.]+)/approve_count\.(?P<format>[a-z0-9]+)/?$` | POST | `StockCountViewSet` |  |
| `/api/inventory/^stock-counts/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `StockCountViewSet` |  |
| `/api/inventory/^stock-counts\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `StockCountViewSet` |  |
| `/api/inventory/^storage-zones/$` | GET,POST | `StorageZoneViewSet` |  |
| `/api/inventory/^storage-zones/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `StorageZoneViewSet` |  |
| `/api/inventory/^storage-zones/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `StorageZoneViewSet` |  |
| `/api/inventory/^storage-zones\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `StorageZoneViewSet` |  |
| `/api/inventory/^temp-logs/$` | GET,POST | `TemperatureLogViewSet` |  |
| `/api/inventory/^temp-logs/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `TemperatureLogViewSet` |  |
| `/api/inventory/^temp-logs/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `TemperatureLogViewSet` |  |
| `/api/inventory/^temp-logs\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `TemperatureLogViewSet` |  |
| `/api/inventory/^temp-sensors/$` | GET,POST | `TemperatureSensorViewSet` |  |
| `/api/inventory/^temp-sensors/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `TemperatureSensorViewSet` |  |
| `/api/inventory/^temp-sensors/(?P<pk>[^/.]+)/record_calibration/$` | POST | `TemperatureSensorViewSet` | File a calibration certificate against the sensor's register. |
| `/api/inventory/^temp-sensors/(?P<pk>[^/.]+)/record_calibration\.(?P<format>[a-z0-9]+)/?$` | POST | `TemperatureSensorViewSet` | File a calibration certificate against the sensor's register. |
| `/api/inventory/^temp-sensors/(?P<pk>[^/.]+)/thermal_profile/$` | GET | `TemperatureSensorViewSet` | MKT, min/mean/max and excursion counts over a window (default 30 days). |
| `/api/inventory/^temp-sensors/(?P<pk>[^/.]+)/thermal_profile\.(?P<format>[a-z0-9]+)/?$` | GET | `TemperatureSensorViewSet` | MKT, min/mean/max and excursion counts over a window (default 30 days). |
| `/api/inventory/^temp-sensors/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `TemperatureSensorViewSet` |  |
| `/api/inventory/^temp-sensors/calibration_register/$` | GET | `TemperatureSensorViewSet` | Every sensor with its calibration state — what an inspector asks to see. |
| `/api/inventory/^temp-sensors/calibration_register\.(?P<format>[a-z0-9]+)/?$` | GET | `TemperatureSensorViewSet` | Every sensor with its calibration state — what an inspector asks to see. |
| `/api/inventory/^temp-sensors\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `TemperatureSensorViewSet` |  |
| `/api/inventory/^warehouses/$` | GET,POST | `WarehouseViewSet` |  |
| `/api/inventory/^warehouses/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `WarehouseViewSet` |  |
| `/api/inventory/^warehouses/(?P<pk>[^/.]+)/occupancy/$` | GET | `WarehouseViewSet` | Bin utilisation and stock value per zone — what the facility is holding. |
| `/api/inventory/^warehouses/(?P<pk>[^/.]+)/occupancy\.(?P<format>[a-z0-9]+)/?$` | GET | `WarehouseViewSet` | Bin utilisation and stock value per zone — what the facility is holding. |
| `/api/inventory/^warehouses/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `WarehouseViewSet` |  |
| `/api/inventory/^warehouses\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `WarehouseViewSet` |  |
| `/api/inventory/intake` | — | `IntakeView` |  |


## `/api/procurement`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/procurement/` | — | `APIRootView` | The default basic root view for DefaultRouter |
| `/api/procurement/<drf_format_suffix:format>` | — | `APIRootView` | The default basic root view for DefaultRouter |
| `/api/procurement/^consignments/$` | GET,POST | `ImportConsignmentViewSet` |  |
| `/api/procurement/^consignments/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `ImportConsignmentViewSet` |  |
| `/api/procurement/^consignments/(?P<pk>[^/.]+)/allocate_costs/$` | POST | `ImportConsignmentViewSet` | Spread duty/freight/insurance/clearing into each line's unit cost. |
| `/api/procurement/^consignments/(?P<pk>[^/.]+)/allocate_costs\.(?P<format>[a-z0-9]+)/?$` | POST | `ImportConsignmentViewSet` | Spread duty/freight/insurance/clearing into each line's unit cost. |
| `/api/procurement/^consignments/(?P<pk>[^/.]+)/attach_order/$` | POST | `ImportConsignmentViewSet` |  |
| `/api/procurement/^consignments/(?P<pk>[^/.]+)/attach_order\.(?P<format>[a-z0-9]+)/?$` | POST | `ImportConsignmentViewSet` |  |
| `/api/procurement/^consignments/(?P<pk>[^/.]+)/detach_order/$` | POST | `ImportConsignmentViewSet` |  |
| `/api/procurement/^consignments/(?P<pk>[^/.]+)/detach_order\.(?P<format>[a-z0-9]+)/?$` | POST | `ImportConsignmentViewSet` |  |
| `/api/procurement/^consignments/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `ImportConsignmentViewSet` |  |
| `/api/procurement/^consignments\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `ImportConsignmentViewSet` |  |
| `/api/procurement/^evaluations/$` | GET | `SupplierEvaluationViewSet` |  |
| `/api/procurement/^evaluations/(?P<pk>[^/.]+)/$` | GET | `SupplierEvaluationViewSet` |  |
| `/api/procurement/^evaluations/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | GET | `SupplierEvaluationViewSet` |  |
| `/api/procurement/^evaluations\.(?P<format>[a-z0-9]+)/?$` | GET | `SupplierEvaluationViewSet` |  |
| `/api/procurement/^invoices/$` | GET,POST | `SupplierInvoiceViewSet` |  |
| `/api/procurement/^invoices/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `SupplierInvoiceViewSet` |  |
| `/api/procurement/^invoices/(?P<pk>[^/.]+)/match/$` | POST | `SupplierInvoiceViewSet` | Run the 3-way match (PO ↔ GRN ↔ invoice) and return the line detail. |
| `/api/procurement/^invoices/(?P<pk>[^/.]+)/match\.(?P<format>[a-z0-9]+)/?$` | POST | `SupplierInvoiceViewSet` | Run the 3-way match (PO ↔ GRN ↔ invoice) and return the line detail. |
| `/api/procurement/^invoices/(?P<pk>[^/.]+)/submit/$` | POST | `SupplierInvoiceViewSet` |  |
| `/api/procurement/^invoices/(?P<pk>[^/.]+)/submit\.(?P<format>[a-z0-9]+)/?$` | POST | `SupplierInvoiceViewSet` |  |
| `/api/procurement/^invoices/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `SupplierInvoiceViewSet` |  |
| `/api/procurement/^invoices\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `SupplierInvoiceViewSet` |  |
| `/api/procurement/^landed-costs/$` | GET,POST | `LandedCostComponentViewSet` |  |
| `/api/procurement/^landed-costs/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `LandedCostComponentViewSet` |  |
| `/api/procurement/^landed-costs/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `LandedCostComponentViewSet` |  |
| `/api/procurement/^landed-costs\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `LandedCostComponentViewSet` |  |
| `/api/procurement/^orders/$` | GET,POST | `PurchaseOrderViewSet` |  |
| `/api/procurement/^orders/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `PurchaseOrderViewSet` |  |
| `/api/procurement/^orders/(?P<pk>[^/.]+)/cancel/$` | POST | `PurchaseOrderViewSet` |  |
| `/api/procurement/^orders/(?P<pk>[^/.]+)/cancel\.(?P<format>[a-z0-9]+)/?$` | POST | `PurchaseOrderViewSet` |  |
| `/api/procurement/^orders/(?P<pk>[^/.]+)/close/$` | POST | `PurchaseOrderViewSet` |  |
| `/api/procurement/^orders/(?P<pk>[^/.]+)/close\.(?P<format>[a-z0-9]+)/?$` | POST | `PurchaseOrderViewSet` |  |
| `/api/procurement/^orders/(?P<pk>[^/.]+)/send/$` | POST | `PurchaseOrderViewSet` |  |
| `/api/procurement/^orders/(?P<pk>[^/.]+)/send\.(?P<format>[a-z0-9]+)/?$` | POST | `PurchaseOrderViewSet` |  |
| `/api/procurement/^orders/(?P<pk>[^/.]+)/start_receipt/$` | POST | `PurchaseOrderViewSet` | Open a draft GRN pre-filled with everything still outstanding. |
| `/api/procurement/^orders/(?P<pk>[^/.]+)/start_receipt\.(?P<format>[a-z0-9]+)/?$` | POST | `PurchaseOrderViewSet` | Open a draft GRN pre-filled with everything still outstanding. |
| `/api/procurement/^orders/(?P<pk>[^/.]+)/submit/$` | POST | `PurchaseOrderViewSet` |  |
| `/api/procurement/^orders/(?P<pk>[^/.]+)/submit\.(?P<format>[a-z0-9]+)/?$` | POST | `PurchaseOrderViewSet` |  |
| `/api/procurement/^orders/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `PurchaseOrderViewSet` |  |
| `/api/procurement/^orders\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `PurchaseOrderViewSet` |  |
| `/api/procurement/^price-agreements/$` | GET,POST | `SupplierPriceAgreementViewSet` |  |
| `/api/procurement/^price-agreements/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `SupplierPriceAgreementViewSet` |  |
| `/api/procurement/^price-agreements/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `SupplierPriceAgreementViewSet` |  |
| `/api/procurement/^price-agreements\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `SupplierPriceAgreementViewSet` |  |
| `/api/procurement/^quotes/$` | GET,POST | `SupplierQuoteViewSet` |  |
| `/api/procurement/^quotes/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `SupplierQuoteViewSet` |  |
| `/api/procurement/^quotes/(?P<pk>[^/.]+)/award/$` | POST | `SupplierQuoteViewSet` |  |
| `/api/procurement/^quotes/(?P<pk>[^/.]+)/award\.(?P<format>[a-z0-9]+)/?$` | POST | `SupplierQuoteViewSet` |  |
| `/api/procurement/^quotes/(?P<pk>[^/.]+)/shortlist/$` | POST | `SupplierQuoteViewSet` |  |
| `/api/procurement/^quotes/(?P<pk>[^/.]+)/shortlist\.(?P<format>[a-z0-9]+)/?$` | POST | `SupplierQuoteViewSet` |  |
| `/api/procurement/^quotes/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `SupplierQuoteViewSet` |  |
| `/api/procurement/^quotes\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `SupplierQuoteViewSet` |  |
| `/api/procurement/^receipts/$` | GET,POST | `GoodsReceiptViewSet` |  |
| `/api/procurement/^receipts/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `GoodsReceiptViewSet` |  |
| `/api/procurement/^receipts/(?P<pk>[^/.]+)/cancel/$` | POST | `GoodsReceiptViewSet` |  |
| `/api/procurement/^receipts/(?P<pk>[^/.]+)/cancel\.(?P<format>[a-z0-9]+)/?$` | POST | `GoodsReceiptViewSet` |  |
| `/api/procurement/^receipts/(?P<pk>[^/.]+)/post/$` | POST | `GoodsReceiptViewSet` | Post the receipt: stock in, quarantine for QC, PO progress, GRN, GL. |
| `/api/procurement/^receipts/(?P<pk>[^/.]+)/post\.(?P<format>[a-z0-9]+)/?$` | POST | `GoodsReceiptViewSet` | Post the receipt: stock in, quarantine for QC, PO progress, GRN, GL. |
| `/api/procurement/^receipts/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `GoodsReceiptViewSet` |  |
| `/api/procurement/^receipts\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `GoodsReceiptViewSet` |  |
| `/api/procurement/^requisitions/$` | GET,POST | `PurchaseRequisitionViewSet` |  |
| `/api/procurement/^requisitions/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `PurchaseRequisitionViewSet` |  |
| `/api/procurement/^requisitions/(?P<pk>[^/.]+)/submit/$` | POST | `PurchaseRequisitionViewSet` |  |
| `/api/procurement/^requisitions/(?P<pk>[^/.]+)/submit\.(?P<format>[a-z0-9]+)/?$` | POST | `PurchaseRequisitionViewSet` |  |
| `/api/procurement/^requisitions/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `PurchaseRequisitionViewSet` |  |
| `/api/procurement/^requisitions/consolidate/$` | POST | `PurchaseRequisitionViewSet` | HQ: merge several approved requisitions into one supplier PO. |
| `/api/procurement/^requisitions/consolidate\.(?P<format>[a-z0-9]+)/?$` | POST | `PurchaseRequisitionViewSet` | HQ: merge several approved requisitions into one supplier PO. |
| `/api/procurement/^requisitions\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `PurchaseRequisitionViewSet` |  |
| `/api/procurement/^rfqs/$` | GET,POST | `RequestForQuotationViewSet` |  |
| `/api/procurement/^rfqs/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `RequestForQuotationViewSet` |  |
| `/api/procurement/^rfqs/(?P<pk>[^/.]+)/comparison/$` | GET | `RequestForQuotationViewSet` | The quote-comparison table: totals in RWF, best price flagged. |
| `/api/procurement/^rfqs/(?P<pk>[^/.]+)/comparison\.(?P<format>[a-z0-9]+)/?$` | GET | `RequestForQuotationViewSet` | The quote-comparison table: totals in RWF, best price flagged. |
| `/api/procurement/^rfqs/(?P<pk>[^/.]+)/send/$` | POST | `RequestForQuotationViewSet` |  |
| `/api/procurement/^rfqs/(?P<pk>[^/.]+)/send\.(?P<format>[a-z0-9]+)/?$` | POST | `RequestForQuotationViewSet` |  |
| `/api/procurement/^rfqs/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `RequestForQuotationViewSet` |  |
| `/api/procurement/^rfqs\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `RequestForQuotationViewSet` |  |
| `/api/procurement/^supplier-licences/$` | GET,POST | `SupplierLicenceViewSet` |  |
| `/api/procurement/^supplier-licences/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `SupplierLicenceViewSet` |  |
| `/api/procurement/^supplier-licences/(?P<pk>[^/.]+)/verify/$` | POST | `SupplierLicenceViewSet` |  |
| `/api/procurement/^supplier-licences/(?P<pk>[^/.]+)/verify\.(?P<format>[a-z0-9]+)/?$` | POST | `SupplierLicenceViewSet` |  |
| `/api/procurement/^supplier-licences/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `SupplierLicenceViewSet` |  |
| `/api/procurement/^supplier-licences\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `SupplierLicenceViewSet` |  |
| `/api/procurement/^supplier-notes/$` | GET,POST | `SupplierNoteViewSet` |  |
| `/api/procurement/^supplier-notes/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `SupplierNoteViewSet` |  |
| `/api/procurement/^supplier-notes/(?P<pk>[^/.]+)/issue/$` | POST | `SupplierNoteViewSet` |  |
| `/api/procurement/^supplier-notes/(?P<pk>[^/.]+)/issue\.(?P<format>[a-z0-9]+)/?$` | POST | `SupplierNoteViewSet` |  |
| `/api/procurement/^supplier-notes/(?P<pk>[^/.]+)/settle/$` | POST | `SupplierNoteViewSet` |  |
| `/api/procurement/^supplier-notes/(?P<pk>[^/.]+)/settle\.(?P<format>[a-z0-9]+)/?$` | POST | `SupplierNoteViewSet` |  |
| `/api/procurement/^supplier-notes/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `SupplierNoteViewSet` |  |
| `/api/procurement/^supplier-notes\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `SupplierNoteViewSet` |  |
| `/api/procurement/^supplier-profiles/$` | GET,POST | `SupplierProfileViewSet` | Supplier master: standing, trade terms, banking, scorecard, licences. |
| `/api/procurement/^supplier-profiles/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `SupplierProfileViewSet` | Supplier master: standing, trade terms, banking, scorecard, licences. |
| `/api/procurement/^supplier-profiles/(?P<pk>[^/.]+)/score/$` | POST | `SupplierProfileViewSet` | Recompute the scorecard from actual receipts over a period. |
| `/api/procurement/^supplier-profiles/(?P<pk>[^/.]+)/score\.(?P<format>[a-z0-9]+)/?$` | POST | `SupplierProfileViewSet` | Recompute the scorecard from actual receipts over a period. |
| `/api/procurement/^supplier-profiles/(?P<pk>[^/.]+)/set_standing/$` | POST | `SupplierProfileViewSet` | Supplier master: standing, trade terms, banking, scorecard, licences. |
| `/api/procurement/^supplier-profiles/(?P<pk>[^/.]+)/set_standing\.(?P<format>[a-z0-9]+)/?$` | POST | `SupplierProfileViewSet` | Supplier master: standing, trade terms, banking, scorecard, licences. |
| `/api/procurement/^supplier-profiles/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `SupplierProfileViewSet` | Supplier master: standing, trade terms, banking, scorecard, licences. |
| `/api/procurement/^supplier-profiles/ensure/$` | POST | `SupplierProfileViewSet` | Create the procurement profile for a catalog supplier that lacks one. |
| `/api/procurement/^supplier-profiles/ensure\.(?P<format>[a-z0-9]+)/?$` | POST | `SupplierProfileViewSet` | Create the procurement profile for a catalog supplier that lacks one. |
| `/api/procurement/^supplier-profiles\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `SupplierProfileViewSet` | Supplier master: standing, trade terms, banking, scorecard, licences. |
| `/api/procurement/overview/` | — | `ProcurementOverviewView` | Headline numbers for the Procurement home screen. |
| `/api/procurement/statement/` | — | `SupplierStatementView` | Statement of account for one supplier — invoices, notes, payments, balance. |


## `/api/retail`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/retail/` | — | `APIRootView` | The default basic root view for DefaultRouter |
| `/api/retail/<drf_format_suffix:format>` | — | `APIRootView` | The default basic root view for DefaultRouter |
| `/api/retail/^clinical-encounters/$` | GET,POST | `ClinicalServiceRecordViewSet` |  |
| `/api/retail/^clinical-encounters/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `ClinicalServiceRecordViewSet` |  |
| `/api/retail/^clinical-encounters/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `ClinicalServiceRecordViewSet` |  |
| `/api/retail/^clinical-encounters\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `ClinicalServiceRecordViewSet` |  |
| `/api/retail/^clinical-services/$` | GET,POST | `ClinicalServiceViewSet` |  |
| `/api/retail/^clinical-services/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `ClinicalServiceViewSet` |  |
| `/api/retail/^clinical-services/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `ClinicalServiceViewSet` |  |
| `/api/retail/^clinical-services\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `ClinicalServiceViewSet` |  |
| `/api/retail/^controlled-drugs/$` | GET,POST | `ControlledSubstanceRegisterViewSet` |  |
| `/api/retail/^controlled-drugs/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `ControlledSubstanceRegisterViewSet` |  |
| `/api/retail/^controlled-drugs/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `ControlledSubstanceRegisterViewSet` |  |
| `/api/retail/^controlled-drugs\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `ControlledSubstanceRegisterViewSet` |  |
| `/api/retail/^counter/apply-promotion/$` | POST | `CounterViewSet` | Apply a coupon to an open basket, or say plainly why it does not apply. |
| `/api/retail/^counter/apply-promotion\.(?P<format>[a-z0-9]+)/?$` | POST | `CounterViewSet` | Apply a coupon to an open basket, or say plainly why it does not apply. |
| `/api/retail/^counter/bill-clinical-service/$` | POST | `CounterViewSet` | Take payment for a clinical service and post it to the ledger. |
| `/api/retail/^counter/bill-clinical-service\.(?P<format>[a-z0-9]+)/?$` | POST | `CounterViewSet` | Take payment for a clinical service and post it to the ledger. |
| `/api/retail/^counter/clear-promotion/$` | POST | `CounterViewSet` | Actions performed at the till. |
| `/api/retail/^counter/clear-promotion\.(?P<format>[a-z0-9]+)/?$` | POST | `CounterViewSet` | Actions performed at the till. |
| `/api/retail/^counter/promotions/$` | GET | `CounterViewSet` | Coupons in force today, so the till can offer them rather than guess. |
| `/api/retail/^counter/promotions\.(?P<format>[a-z0-9]+)/?$` | GET | `CounterViewSet` | Coupons in force today, so the till can offer them rather than guess. |
| `/api/retail/^counter/scan/$` | GET | `CounterViewSet` | Resolve a scanned barcode to a product and the quantity it represents. |
| `/api/retail/^counter/scan\.(?P<format>[a-z0-9]+)/?$` | GET | `CounterViewSet` | Resolve a scanned barcode to a product and the quantity it represents. |
| `/api/retail/^dispensing/$` | GET | `DispensingViewSet` | Read-only regulatory dispensing log — every Rx / controlled sale, with the pharmacist, patient, and prescriber. |
| `/api/retail/^dispensing/(?P<pk>[^/.]+)/$` | GET | `DispensingViewSet` | Read-only regulatory dispensing log — every Rx / controlled sale, with the pharmacist, patient, and prescriber. |
| `/api/retail/^dispensing/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | GET | `DispensingViewSet` | Read-only regulatory dispensing log — every Rx / controlled sale, with the pharmacist, patient, and prescriber. |
| `/api/retail/^dispensing\.(?P<format>[a-z0-9]+)/?$` | GET | `DispensingViewSet` | Read-only regulatory dispensing log — every Rx / controlled sale, with the pharmacist, patient, and prescriber. |
| `/api/retail/^drawer-sessions/$` | GET,POST | `DrawerSessionViewSet` | Cash-drawer / till sessions: open with a float, ring up sales, then cash up (count the cash → over/short) and close. |
| `/api/retail/^drawer-sessions/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `DrawerSessionViewSet` | Cash-drawer / till sessions: open with a float, ring up sales, then cash up (count the cash → over/short) and close. |
| `/api/retail/^drawer-sessions/(?P<pk>[^/.]+)/close/$` | POST | `DrawerSessionViewSet` | Cash up: submit the counted cash → over/short, and close the drawer. |
| `/api/retail/^drawer-sessions/(?P<pk>[^/.]+)/close\.(?P<format>[a-z0-9]+)/?$` | POST | `DrawerSessionViewSet` | Cash up: submit the counted cash → over/short, and close the drawer. |
| `/api/retail/^drawer-sessions/(?P<pk>[^/.]+)/report/$` | GET | `DrawerSessionViewSet` | X/Z cash report for a drawer (running while open, final once closed). |
| `/api/retail/^drawer-sessions/(?P<pk>[^/.]+)/report\.(?P<format>[a-z0-9]+)/?$` | GET | `DrawerSessionViewSet` | X/Z cash report for a drawer (running while open, final once closed). |
| `/api/retail/^drawer-sessions/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `DrawerSessionViewSet` | Cash-drawer / till sessions: open with a float, ring up sales, then cash up (count the cash → over/short) and close. |
| `/api/retail/^drawer-sessions/current/$` | GET | `DrawerSessionViewSet` | The caller's open drawer for ?organization, with a live X-report (204 if none). |
| `/api/retail/^drawer-sessions/current\.(?P<format>[a-z0-9]+)/?$` | GET | `DrawerSessionViewSet` | The caller's open drawer for ?organization, with a live X-report (204 if none). |
| `/api/retail/^drawer-sessions\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `DrawerSessionViewSet` | Cash-drawer / till sessions: open with a float, ring up sales, then cash up (count the cash → over/short) and close. |
| `/api/retail/^offline/sync/$` | POST | `OfflineSyncViewSet` | Replay one queued sale. |
| `/api/retail/^offline/sync\.(?P<format>[a-z0-9]+)/?$` | POST | `OfflineSyncViewSet` | Replay one queued sale. |
| `/api/retail/^prescriptions/$` | GET,POST | `PrescriptionViewSet` |  |
| `/api/retail/^prescriptions/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `PrescriptionViewSet` |  |
| `/api/retail/^prescriptions/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `PrescriptionViewSet` |  |
| `/api/retail/^prescriptions\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `PrescriptionViewSet` |  |
| `/api/retail/^promotions/$` | GET,POST | `POSPromotionViewSet` |  |
| `/api/retail/^promotions/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `POSPromotionViewSet` |  |
| `/api/retail/^promotions/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `POSPromotionViewSet` |  |
| `/api/retail/^promotions\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `POSPromotionViewSet` |  |
| `/api/retail/^sales/$` | GET,POST | `SaleViewSet` |  |
| `/api/retail/^sales/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `SaleViewSet` |  |
| `/api/retail/^sales/(?P<pk>[^/.]+)/complete/$` | POST | `SaleViewSet` | Take payment for a held (OPEN) sale. |
| `/api/retail/^sales/(?P<pk>[^/.]+)/complete\.(?P<format>[a-z0-9]+)/?$` | POST | `SaleViewSet` | Take payment for a held (OPEN) sale. |
| `/api/retail/^sales/(?P<pk>[^/.]+)/return/$` | POST | `SaleViewSet` | Return some items from a completed sale — stock back, refund, credit note. |
| `/api/retail/^sales/(?P<pk>[^/.]+)/return\.(?P<format>[a-z0-9]+)/?$` | POST | `SaleViewSet` | Return some items from a completed sale — stock back, refund, credit note. |
| `/api/retail/^sales/(?P<pk>[^/.]+)/void/$` | POST | `SaleViewSet` | Reverse a completed sale, returning its stock to the pharmacy. |
| `/api/retail/^sales/(?P<pk>[^/.]+)/void\.(?P<format>[a-z0-9]+)/?$` | POST | `SaleViewSet` | Reverse a completed sale, returning its stock to the pharmacy. |
| `/api/retail/^sales/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `SaleViewSet` |  |
| `/api/retail/^sales\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `SaleViewSet` |  |


## `/api/schema`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/schema/` | — | `SpectacularAPIView` | OpenApi3 schema for this API. |


## `/api/workspace`


| Path | Methods | View | Purpose |
| --- | --- | --- | --- |
| `/api/workspace/` | — | `APIRootView` | The default basic root view for DefaultRouter |
| `/api/workspace/<drf_format_suffix:format>` | — | `APIRootView` | The default basic root view for DefaultRouter |
| `/api/workspace/^comments/$` | GET,POST | `CommentViewSet` | Threaded comments on any record; list requires ?entity_type=&entity_id=. |
| `/api/workspace/^comments/(?P<pk>[^/.]+)/$` | DELETE,GET,PATCH,PUT | `CommentViewSet` | Threaded comments on any record; list requires ?entity_type=&entity_id=. |
| `/api/workspace/^comments/(?P<pk>[^/.]+)/strike/$` | POST | `CommentViewSet` | Soft-delete (strike through) your own comment. |
| `/api/workspace/^comments/(?P<pk>[^/.]+)/strike\.(?P<format>[a-z0-9]+)/?$` | POST | `CommentViewSet` | Soft-delete (strike through) your own comment. |
| `/api/workspace/^comments/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | DELETE,GET,PATCH,PUT | `CommentViewSet` | Threaded comments on any record; list requires ?entity_type=&entity_id=. |
| `/api/workspace/^comments\.(?P<format>[a-z0-9]+)/?$` | GET,POST | `CommentViewSet` | Threaded comments on any record; list requires ?entity_type=&entity_id=. |
| `/api/workspace/^notifications/$` | GET | `NotificationViewSet` | The current user's in-app notifications. |
| `/api/workspace/^notifications/(?P<pk>[^/.]+)/$` | GET | `NotificationViewSet` | The current user's in-app notifications. |
| `/api/workspace/^notifications/(?P<pk>[^/.]+)/mark-read/$` | POST | `NotificationViewSet` | The current user's in-app notifications. |
| `/api/workspace/^notifications/(?P<pk>[^/.]+)/mark-read\.(?P<format>[a-z0-9]+)/?$` | POST | `NotificationViewSet` | The current user's in-app notifications. |
| `/api/workspace/^notifications/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` | GET | `NotificationViewSet` | The current user's in-app notifications. |
| `/api/workspace/^notifications/mark-all-read/$` | POST | `NotificationViewSet` | The current user's in-app notifications. |
| `/api/workspace/^notifications/mark-all-read\.(?P<format>[a-z0-9]+)/?$` | POST | `NotificationViewSet` | The current user's in-app notifications. |
| `/api/workspace/^notifications/unread-count/$` | GET | `NotificationViewSet` | The current user's in-app notifications. |
| `/api/workspace/^notifications/unread-count\.(?P<format>[a-z0-9]+)/?$` | GET | `NotificationViewSet` | The current user's in-app notifications. |
| `/api/workspace/^notifications\.(?P<format>[a-z0-9]+)/?$` | GET | `NotificationViewSet` | The current user's in-app notifications. |
| `/api/workspace/mentionable-users` | — | `MentionableUsersView` | Users in an organization who can be @mentioned (id + username). |

