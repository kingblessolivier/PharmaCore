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
import { AdminHome } from "./pages/apps/AdminHome";
import { RetailHome } from "./pages/apps/RetailHome";
import { CatalogHome } from "./pages/apps/CatalogHome";
import { DistributionHome } from "./pages/apps/DistributionHome";
import { FinanceHome } from "./pages/apps/FinanceHome";
import { PeopleHome } from "./pages/apps/PeopleHome";

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
              <Route path="/distribution" element={forPharmacy(<DistributionHome />)} />
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
              <Route path="/people" element={forHR(<PeopleHome />)} />
              <Route path="/people/employees" element={forHR(<EmployeesPage />)} />
              <Route path="/people/employees/:id" element={forHR(<EmployeeDetailPage />)} />
              <Route path="/people/payroll" element={forHR(<PayrollPage />)} />
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
