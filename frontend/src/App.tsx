import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { Spinner } from "./components/ui";
import { AuthProvider, useAuth } from "./lib/auth";
import { isAdmin } from "./lib/roles";
import { DashboardPage } from "./pages/DashboardPage";
import { DepartmentsPage } from "./pages/DepartmentsPage";
import { DocumentsPage } from "./pages/DocumentsPage";
import { LoginPage } from "./pages/LoginPage";
import { OrganizationDetailPage } from "./pages/OrganizationDetailPage";
import { OrdersPage } from "./pages/OrdersPage";
import { PosPage } from "./pages/PosPage";
import { ProductDetailPage } from "./pages/ProductDetailPage";
import { ProductsPage } from "./pages/ProductsPage";
import { SuppliersPage } from "./pages/SuppliersPage";
import { ActivityPage } from "./pages/ActivityPage";
import { CompaniesPage } from "./pages/CompaniesPage";
import { ApprovalsInboxPage } from "./pages/ApprovalsInboxPage";
import { ChartOfAccountsPage } from "./pages/ChartOfAccountsPage";
import { JournalPage } from "./pages/JournalPage";
import { EmployeesPage } from "./pages/EmployeesPage";
import { EmployeeDetailPage } from "./pages/EmployeeDetailPage";
import { PayrollPage } from "./pages/PayrollPage";
import { SupplierBillsPage } from "./pages/SupplierBillsPage";
import { FinanceStatementsPage } from "./pages/FinanceStatementsPage";
import { PaymentRunsPage } from "./pages/PaymentRunsPage";
import { FixedAssetsPage } from "./pages/FixedAssetsPage";
import { BudgetsPage } from "./pages/BudgetsPage";
import { TenantSettingsPage } from "./pages/TenantSettingsPage";
import { LeavePage } from "./pages/LeavePage";
import { DemandBoardPage } from "./pages/DemandBoardPage";
import { DepotListingsPage } from "./pages/DepotListingsPage";
import { B2BOrderingPortalPage } from "./pages/B2BOrderingPortalPage";
import { FieldSalesPage } from "./pages/FieldSalesPage";
import { InstitutionalTendersPage } from "./pages/InstitutionalTendersPage";
import { CustomerReturnsPage } from "./pages/CustomerReturnsPage";
import { PrescriptionsPage } from "./pages/PrescriptionsPage";
import { ControlledSubstancesPage } from "./pages/ControlledSubstancesPage";
import { PromotionsPage } from "./pages/PromotionsPage";
import { ClinicalServicesPage } from "./pages/ClinicalServicesPage";
import { AdminHome } from "./pages/apps/AdminHome";
import { RetailHome } from "./pages/apps/RetailHome";
import { CatalogHome } from "./pages/apps/CatalogHome";
import { InsuranceHome } from "./pages/apps/InsuranceHome";
import { InsuranceClaimsPage } from "./pages/InsuranceClaimsPage";
import { InsuranceSchemesPage } from "./pages/InsuranceSchemesPage";
import { InsuranceMembersPage } from "./pages/InsuranceMembersPage";
import { InsuranceRemittancesPage } from "./pages/InsuranceRemittancesPage";
import { ChatPage } from "./pages/ChatPage";
import { MailPage } from "./pages/MailPage";
import { DistributionHome } from "./pages/apps/DistributionHome";
import { FinanceHome } from "./pages/apps/FinanceHome";
import { CostCentresPage } from "./pages/CostCentresPage";
import { SchedulesPage } from "./pages/SchedulesPage";
import { PeopleHome } from "./pages/apps/PeopleHome";

import { LowStockPage } from "./pages/LowStockPage";
import { ExpiryPage } from "./pages/ExpiryPage";
import { PriceListsPage } from "./pages/PriceListsPage";
import { FormulariesPage } from "./pages/FormulariesPage";

import { InventoryHome } from "./pages/apps/InventoryHome";
import { ConsignmentPage } from "./pages/ConsignmentPage";
import { PickWavesPage } from "./pages/PickWavesPage";
import { ReplenishmentPage } from "./pages/ReplenishmentPage";
import { SerialisationPage } from "./pages/SerialisationPage";
import { QualityControlPage } from "./pages/QualityControlPage";
import { BatchRecallsPage } from "./pages/BatchRecallsPage";
import { StockCountsPage } from "./pages/StockCountsPage";
import { StockDisposalPage } from "./pages/StockDisposalPage";
import { PurchaseOrdersPage } from "./pages/PurchaseOrdersPage";
import { ClaimWorkbenchPage } from "./pages/ClaimWorkbenchPage";
import { GrnWorkbenchPage } from "./pages/GrnWorkbenchPage";
import { RequisitionWorkbenchPage } from "./pages/RequisitionWorkbenchPage";
import { SupplierWorkbenchPage } from "./pages/SupplierWorkbenchPage";
import { OrderComposePage } from "./pages/OrderComposePage";
import {
  AccessWorkspace,
  CashBankWorkspace,
  ColdChainWorkspace,
  ReceivablesWorkspace,
  ReferenceDataWorkspace,
  StatutoryWorkspace,
  TaxWorkspace,
  TimeWorkspace,
  WarehouseSetupWorkspace,
} from "./pages/workspaces";
import { OrderWorkbenchPage } from "./pages/OrderWorkbenchPage";
import { GrnPage } from "./pages/GrnPage";
import { InTransitPage } from "./pages/InTransitPage";

import { ProcurementHome } from "./pages/apps/ProcurementHome";
import { SupplierMasterPage } from "./pages/SupplierMasterPage";
import { RequisitionsPage } from "./pages/RequisitionsPage";
import { RfqPage } from "./pages/RfqPage";
import { SupplierOrdersPage } from "./pages/SupplierOrdersPage";
import { ImportsPage } from "./pages/ImportsPage";
import { GoodsReceiptsPage } from "./pages/GoodsReceiptsPage";
import { SupplierInvoicesPage } from "./pages/SupplierInvoicesPage";

import { LoansPage } from "./pages/LoansPage";
import { RecruitmentPage } from "./pages/RecruitmentPage";
import { OffboardingPage } from "./pages/OffboardingPage";
import { FinanceCockpitPage } from "./pages/FinanceCockpitPage";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
});

function Protected() {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface-100">
        <Spinner />
      </div>
    );
  }
  return user ? <AppShell /> : <Navigate to="/login" replace />;
}

/** Route guard: a page is reachable only if the user is an admin or holds one of
 * `roles`. Others are bounced to the dashboard — so admin pages can't be opened by
 * typing the URL, mirroring what the nav already hides. */
function RequireRoles({ roles, children }: { roles: string[]; children: ReactNode }) {
  const { user } = useAuth();
  const allowed = isAdmin(user) || roles.some((r) => user?.roles.includes(r));
  return allowed ? <>{children}</> : <Navigate to="/" replace />;
}
const adminOnly = (el: ReactNode) => <RequireRoles roles={[]}>{el}</RequireRoles>;
const forPharmacy = (el: ReactNode) => <RequireRoles roles={["PHARMACIST"]}>{el}</RequireRoles>;
// ORG_ADMIN is included so an organisation without a dedicated accountant or HR manager
// can still reach the area via their admin role. The list is also where the sidebar
// mirrors it (AppShell.tsx), so a user opening Finance from a tile and a link are
// gated consistently.
const forFinance = (el: ReactNode) => (
  <RequireRoles roles={["ACCOUNTANT", "ORG_ADMIN"]}>{el}</RequireRoles>
);
const forHR = (el: ReactNode) => (
  <RequireRoles roles={["HR_MANAGER", "ORG_ADMIN"]}>{el}</RequireRoles>
);
const forProcurement = (el: ReactNode) => (
  <RequireRoles roles={["PROCUREMENT_OFFICER", "ACCOUNTANT", "WAREHOUSE_CLERK", "PHARMACIST"]}>
    {el}
  </RequireRoles>
);

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route element={<Protected />}>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/retail" element={<RetailHome />} />
              <Route path="/retail/prescriptions" element={forPharmacy(<PrescriptionsPage />)} />
              <Route path="/retail/controlled-drugs" element={forPharmacy(<ControlledSubstancesPage />)} />
              <Route path="/retail/promotions" element={forPharmacy(<PromotionsPage />)} />
              <Route path="/retail/clinical-services" element={forPharmacy(<ClinicalServicesPage />)} />
              <Route path="/catalog" element={forPharmacy(<CatalogHome />)} />
              <Route path="/catalog/low-stock" element={forPharmacy(<LowStockPage />)} />
              <Route path="/catalog/expiry" element={forPharmacy(<ExpiryPage />)} />
              <Route path="/catalog/price-lists" element={forPharmacy(<PriceListsPage />)} />
              <Route path="/catalog/formularies" element={forPharmacy(<FormulariesPage />)} />
              <Route path="/catalog/interactions" element={<Navigate to="/catalog/manufacturers?tab=interactions" replace />} />
              <Route path="/catalog/uom" element={<Navigate to="/catalog/manufacturers?tab=uom" replace />} />
              <Route path="/catalog/substitutes" element={<Navigate to="/catalog/manufacturers?tab=substitutes" replace />} />
              <Route path="/catalog/manufacturers" element={forPharmacy(<ReferenceDataWorkspace />)} />
              <Route path="/catalog/ingredients" element={<Navigate to="/catalog/manufacturers?tab=ingredients" replace />} />
              <Route path="/inventory" element={forPharmacy(<InventoryHome />)} />
              <Route path="/inventory/warehouses" element={forPharmacy(<WarehouseSetupWorkspace />)} />
              <Route path="/inventory/zones" element={<Navigate to="/inventory/warehouses?tab=zones" replace />} />
              <Route path="/inventory/putaway" element={<Navigate to="/inventory/warehouses?tab=putaway" replace />} />
              <Route path="/inventory/picking" element={forPharmacy(<PickWavesPage />)} />
              <Route path="/inventory/replenishment" element={forPharmacy(<ReplenishmentPage />)} />
              <Route path="/inventory/serialisation" element={forPharmacy(<SerialisationPage />)} />
              <Route path="/inventory/consignment" element={forPharmacy(<ConsignmentPage />)} />
              <Route path="/inventory/coldchain" element={forPharmacy(<ColdChainWorkspace />)} />
              <Route path="/inventory/temperature" element={<Navigate to="/inventory/coldchain?tab=logs" replace />} />
              <Route path="/inventory/qc" element={forPharmacy(<QualityControlPage />)} />
              <Route path="/inventory/recalls" element={forPharmacy(<BatchRecallsPage />)} />
              <Route path="/inventory/counts" element={forPharmacy(<StockCountsPage />)} />
              <Route path="/inventory/disposal" element={forPharmacy(<StockDisposalPage />)} />
              {/* Insurance */}
              <Route path="/insurance" element={forPharmacy(<InsuranceHome />)} />
              <Route path="/insurance/claims" element={forPharmacy(<InsuranceClaimsPage />)} />
              <Route path="/insurance/claims/:id" element={forPharmacy(<ClaimWorkbenchPage />)} />
              <Route path="/insurance/schemes" element={forPharmacy(<InsuranceSchemesPage />)} />
              <Route path="/insurance/members" element={forPharmacy(<InsuranceMembersPage />)} />
              <Route
                path="/insurance/remittances"
                element={forPharmacy(<InsuranceRemittancesPage />)}
              />
              {/* Connect — chat and mail, open to everyone signed in. */}
              <Route path="/connect/chat" element={<ChatPage />} />
              <Route path="/connect/mail" element={<MailPage />} />
              <Route path="/distribution" element={forPharmacy(<DistributionHome />)} />
              <Route path="/distribution/orders" element={forPharmacy(<PurchaseOrdersPage />)} />
              <Route path="/distribution/orders/new" element={forPharmacy(<OrderComposePage />)} />
              <Route path="/distribution/orders/:id" element={forPharmacy(<OrderWorkbenchPage />)} />
              <Route path="/distribution/grn" element={forPharmacy(<GrnPage />)} />
              <Route path="/distribution/in-transit" element={forPharmacy(<InTransitPage />)} />
              <Route path="/distribution/listings" element={forPharmacy(<DepotListingsPage />)} />
              <Route path="/distribution/demand" element={forPharmacy(<DemandBoardPage />)} />
              <Route path="/distribution/portal" element={forPharmacy(<B2BOrderingPortalPage />)} />
              <Route path="/distribution/sales-reps" element={forPharmacy(<FieldSalesPage />)} />
              <Route path="/distribution/tenders" element={forPharmacy(<InstitutionalTendersPage />)} />
              <Route path="/distribution/returns" element={forPharmacy(<CustomerReturnsPage />)} />
              <Route path="/procurement" element={forProcurement(<ProcurementHome />)} />
              <Route path="/procurement/requisitions" element={forProcurement(<RequisitionsPage />)} />
              <Route path="/procurement/requisitions/:id" element={forProcurement(<RequisitionWorkbenchPage />)} />
              <Route path="/procurement/rfqs" element={forProcurement(<RfqPage />)} />
              <Route path="/procurement/orders" element={forProcurement(<SupplierOrdersPage />)} />
              <Route path="/procurement/imports" element={forProcurement(<ImportsPage />)} />
              <Route path="/procurement/receipts" element={forProcurement(<GoodsReceiptsPage />)} />
              <Route path="/procurement/receipts/:id" element={forProcurement(<GrnWorkbenchPage />)} />
              <Route path="/procurement/invoices" element={forProcurement(<SupplierInvoicesPage />)} />
              <Route path="/procurement/suppliers" element={forProcurement(<SupplierMasterPage />)} />
              <Route path="/procurement/suppliers/:id" element={forProcurement(<SupplierWorkbenchPage />)} />
              <Route path="/admin" element={adminOnly(<AdminHome />)} />
              <Route path="/companies" element={adminOnly(<CompaniesPage />)} />
              {/* Retired: a strict subset of "Organizations & branches", which sat directly
                  above it in the same Admin menu and read the same endpoint. */}
              <Route path="/organizations" element={<Navigate to="/companies" replace />} />
              <Route path="/organizations/:id" element={adminOnly(<OrganizationDetailPage />)} />
              <Route path="/departments" element={adminOnly(<DepartmentsPage />)} />
              <Route path="/users" element={adminOnly(<AccessWorkspace />)} />
              <Route path="/permissions" element={<Navigate to="/users?tab=permissions" replace />} />
              <Route path="/activity" element={adminOnly(<ActivityPage />)} />
              <Route path="/products" element={forPharmacy(<ProductsPage />)} />
              <Route path="/products/:id" element={forPharmacy(<ProductDetailPage />)} />
              <Route path="/suppliers" element={adminOnly(<SuppliersPage />)} />
              <Route path="/orders" element={forPharmacy(<OrdersPage />)} />
              <Route path="/pos" element={<PosPage />} />
              <Route path="/finance" element={forFinance(<FinanceHome />)} />
              <Route path="/finance/cockpit" element={forFinance(<FinanceCockpitPage />)} />
              <Route path="/finance/aging" element={<Navigate to="/finance/receivables?tab=aging" replace />} />
              <Route path="/finance/accounts" element={forFinance(<ChartOfAccountsPage />)} />
              <Route path="/finance/journal" element={forFinance(<JournalPage />)} />
              <Route path="/finance/cost-centres" element={forFinance(<CostCentresPage />)} />
              <Route path="/finance/credit" element={<Navigate to="/finance/receivables?tab=credit" replace />} />
              <Route path="/finance/payables" element={forFinance(<SupplierBillsPage />)} />
              <Route path="/finance/payment-runs" element={forFinance(<PaymentRunsPage />)} />
              <Route path="/finance/receivables" element={forFinance(<ReceivablesWorkspace />)} />
              <Route path="/finance/dunning" element={<Navigate to="/finance/receivables?tab=dunning" replace />} />
              <Route path="/finance/statement" element={<Navigate to="/finance/receivables?tab=statements" replace />} />
              <Route path="/finance/banking" element={forFinance(<CashBankWorkspace />)} />
              <Route path="/finance/reconciliation" element={<Navigate to="/finance/banking?tab=reconciliation" replace />} />
              <Route path="/finance/statements" element={forFinance(<FinanceStatementsPage />)} />
              <Route path="/finance/assets" element={forFinance(<FixedAssetsPage />)} />
              <Route path="/finance/tax-ebm" element={<Navigate to="/finance/tax?tab=ebm" replace />} />
              <Route path="/finance/tax" element={forFinance(<TaxWorkspace />)} />
              <Route path="/finance/tax/payments" element={<Navigate to="/finance/tax?tab=payments" replace />} />
              <Route path="/finance/budgets" element={forFinance(<BudgetsPage />)} />
              <Route path="/finance/schedules" element={forFinance(<SchedulesPage />)} />
              <Route path="/finance/tax-codes" element={<Navigate to="/finance/tax?tab=codes" replace />} />
              <Route
                path="/finance/tenant-settings"
                element={forFinance(<TenantSettingsPage />)}
              />
              <Route path="/people" element={forHR(<PeopleHome />)} />
              <Route path="/people/employees" element={forHR(<EmployeesPage />)} />
              <Route path="/people/employees/:id" element={forHR(<EmployeeDetailPage />)} />
              <Route path="/people/payroll" element={forHR(<PayrollPage />)} />
              <Route path="/people/attendance" element={forHR(<TimeWorkspace />)} />
              <Route path="/people/roster" element={<Navigate to="/people/attendance?tab=roster" replace />} />
              <Route path="/people/leave" element={forHR(<LeavePage />)} />
              <Route path="/people/timesheets" element={<Navigate to="/people/attendance?tab=timesheets" replace />} />
              <Route path="/people/loans" element={forHR(<LoansPage />)} />
              <Route path="/people/recruitment" element={forHR(<RecruitmentPage />)} />
              <Route path="/people/offboarding" element={forHR(<OffboardingPage />)} />
              <Route path="/people/filings" element={forHR(<StatutoryWorkspace />)} />
              <Route path="/people/statutory-rates" element={<Navigate to="/people/filings?tab=rates" replace />} />
              <Route path="/approvals" element={<ApprovalsInboxPage />} />
              <Route path="/documents" element={<DocumentsPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}


export default App;
