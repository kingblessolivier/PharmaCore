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
import { FinancePage } from "./pages/FinancePage";
import { OrganizationsPage } from "./pages/OrganizationsPage";
import { PosPage } from "./pages/PosPage";
import { ProductDetailPage } from "./pages/ProductDetailPage";
import { ProductsPage } from "./pages/ProductsPage";
import { SuppliersPage } from "./pages/SuppliersPage";
import { UsersPage } from "./pages/UsersPage";
import { ActivityPage } from "./pages/ActivityPage";
import { CompaniesPage } from "./pages/CompaniesPage";
import { PermissionMatrixPage } from "./pages/PermissionMatrixPage";
import { ApprovalsInboxPage } from "./pages/ApprovalsInboxPage";
import { ChartOfAccountsPage } from "./pages/ChartOfAccountsPage";
import { JournalPage } from "./pages/JournalPage";
import { CreditProfilesPage } from "./pages/CreditProfilesPage";
import { EmployeesPage } from "./pages/EmployeesPage";
import { EmployeeDetailPage } from "./pages/EmployeeDetailPage";
import { PayrollPage } from "./pages/PayrollPage";
import { SupplierBillsPage } from "./pages/SupplierBillsPage";
import { BankingPage } from "./pages/BankingPage";
import { FinanceStatementsPage } from "./pages/FinanceStatementsPage";
import { ReceivablesPage } from "./pages/ReceivablesPage";
import { DunningPage } from "./pages/DunningPage";
import { CustomerStatementPage } from "./pages/CustomerStatementPage";
import { PaymentRunsPage } from "./pages/PaymentRunsPage";
import { FixedAssetsPage } from "./pages/FixedAssetsPage";
import { TaxEbmPage } from "./pages/TaxEbmPage";
import { VatPage } from "./pages/VatPage";
import { TaxPaymentsPage } from "./pages/TaxPaymentsPage";
import { BudgetsPage } from "./pages/BudgetsPage";
import { AttendancePage } from "./pages/AttendancePage";
import { ShiftRosterPage } from "./pages/ShiftRosterPage";
import { LeavePage } from "./pages/LeavePage";
import { DepotListingsPage } from "./pages/DepotListingsPage";
import { B2BOrderingPortalPage } from "./pages/B2BOrderingPortalPage";
import { FieldSalesPage } from "./pages/FieldSalesPage";
import { InstitutionalTendersPage } from "./pages/InstitutionalTendersPage";
import { CustomerReturnsPage } from "./pages/CustomerReturnsPage";
import { AdminHome } from "./pages/apps/AdminHome";
import { RetailHome } from "./pages/apps/RetailHome";
import { CatalogHome } from "./pages/apps/CatalogHome";
import { DistributionHome } from "./pages/apps/DistributionHome";
import { FinanceHome } from "./pages/apps/FinanceHome";
import { PeopleHome } from "./pages/apps/PeopleHome";

import { LowStockPage } from "./pages/LowStockPage";
import { ExpiryPage } from "./pages/ExpiryPage";
import { PriceListsPage } from "./pages/PriceListsPage";
import { FormulariesPage } from "./pages/FormulariesPage";
import { InteractionsPage } from "./pages/InteractionsPage";
import { UomPage } from "./pages/UomPage";
import { SubstitutesPage } from "./pages/SubstitutesPage";
import { ManufacturersPage } from "./pages/ManufacturersPage";
import { IngredientsPage } from "./pages/IngredientsPage";

import { InventoryHome } from "./pages/apps/InventoryHome";
import { ColdChainCompliancePage } from "./pages/ColdChainCompliancePage";
import { ConsignmentPage } from "./pages/ConsignmentPage";
import { PickWavesPage } from "./pages/PickWavesPage";
import { PutawayRulesPage } from "./pages/PutawayRulesPage";
import { ReplenishmentPage } from "./pages/ReplenishmentPage";
import { SerialisationPage } from "./pages/SerialisationPage";
import { StorageZonesPage } from "./pages/StorageZonesPage";
import { WarehousesPage } from "./pages/WarehousesPage";
import { TemperatureLogsPage } from "./pages/TemperatureLogsPage";
import { QualityControlPage } from "./pages/QualityControlPage";
import { BatchRecallsPage } from "./pages/BatchRecallsPage";
import { StockCountsPage } from "./pages/StockCountsPage";
import { StockDisposalPage } from "./pages/StockDisposalPage";
import { PurchaseOrdersPage } from "./pages/PurchaseOrdersPage";
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
const forFinance = (el: ReactNode) => <RequireRoles roles={["ACCOUNTANT"]}>{el}</RequireRoles>;
const forHR = (el: ReactNode) => <RequireRoles roles={["HR_MANAGER"]}>{el}</RequireRoles>;
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
              <Route path="/catalog" element={forPharmacy(<CatalogHome />)} />
              <Route path="/catalog/low-stock" element={forPharmacy(<LowStockPage />)} />
              <Route path="/catalog/expiry" element={forPharmacy(<ExpiryPage />)} />
              <Route path="/catalog/price-lists" element={forPharmacy(<PriceListsPage />)} />
              <Route path="/catalog/formularies" element={forPharmacy(<FormulariesPage />)} />
              <Route path="/catalog/interactions" element={forPharmacy(<InteractionsPage />)} />
              <Route path="/catalog/uom" element={forPharmacy(<UomPage />)} />
              <Route path="/catalog/substitutes" element={forPharmacy(<SubstitutesPage />)} />
              <Route path="/catalog/manufacturers" element={forPharmacy(<ManufacturersPage />)} />
              <Route path="/catalog/ingredients" element={forPharmacy(<IngredientsPage />)} />
              <Route path="/inventory" element={forPharmacy(<InventoryHome />)} />
              <Route path="/inventory/warehouses" element={forPharmacy(<WarehousesPage />)} />
              <Route path="/inventory/zones" element={forPharmacy(<StorageZonesPage />)} />
              <Route path="/inventory/putaway" element={forPharmacy(<PutawayRulesPage />)} />
              <Route path="/inventory/picking" element={forPharmacy(<PickWavesPage />)} />
              <Route path="/inventory/replenishment" element={forPharmacy(<ReplenishmentPage />)} />
              <Route path="/inventory/serialisation" element={forPharmacy(<SerialisationPage />)} />
              <Route path="/inventory/consignment" element={forPharmacy(<ConsignmentPage />)} />
              <Route path="/inventory/coldchain" element={forPharmacy(<ColdChainCompliancePage />)} />
              <Route path="/inventory/temperature" element={forPharmacy(<TemperatureLogsPage />)} />
              <Route path="/inventory/qc" element={forPharmacy(<QualityControlPage />)} />
              <Route path="/inventory/recalls" element={forPharmacy(<BatchRecallsPage />)} />
              <Route path="/inventory/counts" element={forPharmacy(<StockCountsPage />)} />
              <Route path="/inventory/disposal" element={forPharmacy(<StockDisposalPage />)} />
              <Route path="/distribution" element={forPharmacy(<DistributionHome />)} />
              <Route path="/distribution/orders" element={forPharmacy(<PurchaseOrdersPage />)} />
              <Route path="/distribution/grn" element={forPharmacy(<GrnPage />)} />
              <Route path="/distribution/in-transit" element={forPharmacy(<InTransitPage />)} />
              <Route path="/distribution/listings" element={forPharmacy(<DepotListingsPage />)} />
              <Route path="/distribution/portal" element={forPharmacy(<B2BOrderingPortalPage />)} />
              <Route path="/distribution/sales-reps" element={forPharmacy(<FieldSalesPage />)} />
              <Route path="/distribution/tenders" element={forPharmacy(<InstitutionalTendersPage />)} />
              <Route path="/distribution/returns" element={forPharmacy(<CustomerReturnsPage />)} />
              <Route path="/procurement" element={forProcurement(<ProcurementHome />)} />
              <Route path="/procurement/requisitions" element={forProcurement(<RequisitionsPage />)} />
              <Route path="/procurement/rfqs" element={forProcurement(<RfqPage />)} />
              <Route path="/procurement/orders" element={forProcurement(<SupplierOrdersPage />)} />
              <Route path="/procurement/imports" element={forProcurement(<ImportsPage />)} />
              <Route path="/procurement/receipts" element={forProcurement(<GoodsReceiptsPage />)} />
              <Route path="/procurement/invoices" element={forProcurement(<SupplierInvoicesPage />)} />
              <Route path="/procurement/suppliers" element={forProcurement(<SupplierMasterPage />)} />
              <Route path="/admin" element={adminOnly(<AdminHome />)} />
              <Route path="/companies" element={adminOnly(<CompaniesPage />)} />
              <Route path="/organizations" element={adminOnly(<OrganizationsPage />)} />
              <Route path="/organizations/:id" element={adminOnly(<OrganizationDetailPage />)} />
              <Route path="/departments" element={adminOnly(<DepartmentsPage />)} />
              <Route path="/users" element={adminOnly(<UsersPage />)} />
              <Route path="/permissions" element={adminOnly(<PermissionMatrixPage />)} />
              <Route path="/activity" element={adminOnly(<ActivityPage />)} />
              <Route path="/products" element={forPharmacy(<ProductsPage />)} />
              <Route path="/products/:id" element={forPharmacy(<ProductDetailPage />)} />
              <Route path="/suppliers" element={adminOnly(<SuppliersPage />)} />
              <Route path="/orders" element={forPharmacy(<OrdersPage />)} />
              <Route path="/pos" element={<PosPage />} />
              <Route path="/finance" element={forFinance(<FinanceHome />)} />
              <Route path="/finance/aging" element={forFinance(<FinancePage />)} />
              <Route path="/finance/accounts" element={forFinance(<ChartOfAccountsPage />)} />
              <Route path="/finance/journal" element={forFinance(<JournalPage />)} />
              <Route path="/finance/credit" element={forFinance(<CreditProfilesPage />)} />
              <Route path="/finance/payables" element={forFinance(<SupplierBillsPage />)} />
              <Route path="/finance/payment-runs" element={forFinance(<PaymentRunsPage />)} />
              <Route path="/finance/receivables" element={forFinance(<ReceivablesPage />)} />
              <Route path="/finance/dunning" element={forFinance(<DunningPage />)} />
              <Route path="/finance/statement" element={forFinance(<CustomerStatementPage />)} />
              <Route path="/finance/banking" element={forFinance(<BankingPage />)} />
              <Route path="/finance/statements" element={forFinance(<FinanceStatementsPage />)} />
              <Route path="/finance/assets" element={forFinance(<FixedAssetsPage />)} />
              <Route path="/finance/tax-ebm" element={forFinance(<TaxEbmPage />)} />
              <Route path="/finance/tax" element={forFinance(<VatPage />)} />
              <Route path="/finance/tax/payments" element={forFinance(<TaxPaymentsPage />)} />
              <Route path="/finance/budgets" element={forFinance(<BudgetsPage />)} />
              <Route path="/people" element={forHR(<PeopleHome />)} />
              <Route path="/people/employees" element={forHR(<EmployeesPage />)} />
              <Route path="/people/employees/:id" element={forHR(<EmployeeDetailPage />)} />
              <Route path="/people/payroll" element={forHR(<PayrollPage />)} />
              <Route path="/people/attendance" element={forHR(<AttendancePage />)} />
              <Route path="/people/roster" element={forHR(<ShiftRosterPage />)} />
              <Route path="/people/leave" element={forHR(<LeavePage />)} />
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
