import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  Banknote,
  BarChart3,
  Bell,
  BookOpen,
  Boxes,
  Building2,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ClipboardList,
  CreditCard,
  Eye,
  FileText,
  Globe,
  FileBarChart,
  Landmark,
  LayoutDashboard,
  LayoutGrid,
  LogOut,
  Mail,
  MessageSquare,
  Network,
  Pill,
  ScrollText,
  Search,
  Shield,
  ShieldCheck,
  ShoppingCart,
  Sliders,
  Store,
  TrendingUp,
  Truck,
  RotateCcw,
  UserCheck,
  UserCog,
  Users,
  Calendar,
  Clock,
  Wallet,
  Thermometer,
  Warehouse,
  PackageCheck,
  ShoppingBag,
  Ship,
  FileSearch,
  Gavel,
  Receipt,
  Handshake,
  ScanLine,
  Route as RouteIcon,
  RefreshCw,
  MoveRight,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { isAdmin } from "../lib/roles";
import type { AppNotification, Organization, Paginated } from "../lib/types";
import { CommandPalette } from "./CommandPalette";

function BrandMark() {
  return (
    <div className="flex h-7 w-7 items-center justify-center rounded-md bg-brand-600">
      <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="white" strokeWidth={2.2}>
        <circle cx="7" cy="12" r="3" />
        <circle cx="17" cy="12" r="3" />
        <path d="M10 12h4" strokeLinecap="round" />
      </svg>
    </div>
  );
}

// Subsystem tiles for the app-switcher springboard (Oracle-Fusion / Workspace-waffle
// pattern). Hues are the documented subsystem colours from docs/design/01 §subsystems.
interface AppTile {
  label: string;
  hue: string;
  icon: typeof LayoutDashboard;
  to: string | null; // null = not built yet ("soon")
  roles: "all" | string[];
}
const APPS: AppTile[] = [
  { label: "Retail", hue: "#0D9488", icon: ShoppingCart, to: "/retail", roles: "all" },
  { label: "Catalog", hue: "#CA8A04", icon: Pill, to: "/catalog", roles: ["ORG_ADMIN", "PHARMACIST"] },
  { label: "Distribution", hue: "#3B5BDB", icon: Truck, to: "/distribution", roles: ["ORG_ADMIN", "PHARMACIST"] },
  { label: "Inventory", hue: "#0891B2", icon: Warehouse, to: "/inventory", roles: ["ORG_ADMIN", "PHARMACIST"] },
  { label: "Procurement", hue: "#7C3AED", icon: ShoppingBag, to: "/procurement", roles: ["ORG_ADMIN", "PROCUREMENT_OFFICER"] },
  { label: "Finance", hue: "#15803D", icon: Wallet, to: "/finance", roles: ["ORG_ADMIN"] },
  { label: "Insights", hue: "#DB2777", icon: BarChart3, to: "/", roles: "all" },
  { label: "Admin", hue: "#475569", icon: ShieldCheck, to: "/admin", roles: ["ORG_ADMIN"] },
  { label: "Insurance", hue: "#7C3AED", icon: Shield, to: "/insurance", roles: ["ORG_ADMIN", "PHARMACIST"] },
  { label: "People", hue: "#EA580C", icon: Users, to: "/people", roles: ["HR_MANAGER"] },
  { label: "Online", hue: "#0EA5E9", icon: Globe, to: null, roles: "all" },
  { label: "Connect", hue: "#2563EB", icon: MessageSquare, to: "/connect/chat", roles: "all" },
];

function AppSwitcher() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const admin = isAdmin(user);
  const roles = user?.roles ?? [];
  const canSee = (r: "all" | string[]) =>
    r === "all" || admin || r.some((x) => roles.includes(x));
  const tiles = APPS.filter((t) => canSee(t.roles));

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="rounded-md p-1.5 text-ink-600 hover:bg-surface-100"
        aria-label="Open apps"
        title="PharmaCore apps"
      >
        <LayoutGrid className="h-5 w-5" />
      </button>
      {open && (
        <div className="absolute left-0 top-11 z-50 w-80 rounded-xl border border-line bg-surface-0 p-3 shadow-lg">
          <div className="px-1 pb-2 text-[11px] font-semibold uppercase tracking-wide text-ink-500">
            PharmaCore apps
          </div>
          <div className="grid grid-cols-3 gap-1">
            {tiles.map(({ label, hue, icon: Icon, to }) => {
              const soon = to === null;
              return (
                <button
                  key={label}
                  disabled={soon}
                  onClick={() => {
                    if (to) {
                      navigate(to);
                      setOpen(false);
                    }
                  }}
                  className={`flex flex-col items-center gap-1.5 rounded-lg p-2.5 text-center transition-colors ${
                    soon ? "cursor-default opacity-45" : "hover:bg-surface-100"
                  }`}
                >
                  <span
                    className="flex h-11 w-11 items-center justify-center rounded-xl text-white"
                    style={{ backgroundColor: hue }}
                  >
                    <Icon className="h-5 w-5" />
                  </span>
                  <span className="text-xs font-medium text-ink-700">{label}</span>
                  {soon && <span className="-mt-1 text-[9px] uppercase text-ink-400">soon</span>}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function OrgSwitcher() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const { data } = useQuery({
    queryKey: ["organizations"],
    queryFn: () => api<Paginated<Organization>>("/api/organizations/"),
  });

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const label = user?.is_superuser ? "All organizations" : (data?.results[0]?.name ?? "Organization");

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 rounded-full border border-line px-2.5 py-1 text-xs font-medium text-ink-700 hover:bg-surface-100"
      >
        <Building2 className="h-3.5 w-3.5" />
        {label}
        <ChevronDown className="h-3.5 w-3.5 text-ink-500" />
      </button>
      {open && (
        <div className="absolute left-0 top-9 z-50 max-h-72 w-64 overflow-y-auto rounded-lg border border-line bg-surface-0 p-1 shadow-lg">
          {(data?.results ?? []).map((o) => (
            <button
              key={o.id}
              onClick={() => {
                setOpen(false);
                navigate(`/organizations/${o.id}`);
              }}
              className="flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm text-ink-700 hover:bg-surface-100"
            >
              {o.name}
              <span className="text-[10px] uppercase text-ink-500">{o.type}</span>
            </button>
          ))}
          {data?.results.length === 0 && (
            <div className="px-3 py-3 text-sm text-ink-500">No organizations.</div>
          )}
        </div>
      )}
    </div>
  );
}

function NotificationsBell() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const unread = useQuery({
    queryKey: ["notif-unread"],
    queryFn: () => api<{ count: number }>("/api/workspace/notifications/unread-count/"),
    refetchInterval: 30000,
  });
  const list = useQuery({
    queryKey: ["notifications"],
    queryFn: () => api<Paginated<AppNotification>>("/api/workspace/notifications/"),
    enabled: open,
  });
  const markAll = useMutation({
    mutationFn: () => api<void>("/api/workspace/notifications/mark-all-read/", { method: "POST" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["notif-unread"] });
      void qc.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const count = unread.data?.count ?? 0;

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="relative rounded-md p-1.5 text-ink-600 hover:bg-surface-100"
        aria-label="Notifications"
      >
        <Bell className="h-4.5 w-4.5" />
        {count > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-semibold text-white">
            {count}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 top-10 z-50 w-80 overflow-hidden rounded-lg border border-line bg-surface-0 shadow-lg">
          <div className="flex items-center justify-between border-b border-line px-3 py-2">
            <span className="text-sm font-semibold">Notifications</span>
            {count > 0 && (
              <button onClick={() => markAll.mutate()} className="text-xs text-brand-700 hover:underline">
                Mark all read
              </button>
            )}
          </div>
          <ul className="max-h-80 overflow-y-auto">
            {(list.data?.results ?? []).map((n) => (
              <li key={n.id}>
                <button
                  onClick={() => {
                    setOpen(false);
                    const dest: Record<string, string> = {
                      stock_order: "/orders",
                      orders: "/orders",
                      dashboard: "/",
                    };
                    const to = dest[n.link_entity_type];
                    if (to) navigate(to);
                  }}
                  className={`flex w-full flex-col items-start gap-0.5 border-b border-line px-3 py-2 text-left hover:bg-surface-100 ${n.is_read ? "" : "bg-brand-50/40"}`}
                >
                  <span className="text-sm font-medium text-ink-900">{n.title}</span>
                  {n.body && <span className="line-clamp-2 text-xs text-ink-500">{n.body}</span>}
                </button>
              </li>
            ))}
            {list.data?.results.length === 0 && (
              <li className="px-3 py-6 text-center text-sm text-ink-500">No notifications.</li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}

interface NavItem {
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
  end?: boolean;
  roles?: "all" | string[]; // per-item override; else inherits the group
}

interface NavGroup {
  label: string; // "" = ungrouped (rendered without a header)
  roles: "all" | string[]; // "all" = everyone; else visible to admins + these roles
  items: NavItem[];
  /** Route prefixes that belong to this app. When the user is inside one of these,
   * the side nav shows ONLY this group (Oracle/Workspace behaviour: pick an app,
   * see that app's contents). Omit for always-visible groups (e.g. Dashboard). */
  match?: string[];
  /** Groups sharing an `app` key render together as sections of one app. An app with
   * enough surface to need sub-headings (Finance has six jobs, not one list) is still
   * one app; without this, `activeApp` picks the first matching group and the rest of
   * the app disappears from the nav. */
  app?: string;
}

// Side nav grouped by subsystem, per docs/design/04-navigation.md §3.1 — Company,
// Organizations, Departments, Users and the Audit Log all live under ADMIN (not as
// separate top-level entries).
const NAV: NavGroup[] = [
  { label: "", roles: "all", items: [{ to: "/", label: "Dashboard", icon: LayoutDashboard, end: true }] },
  {
    label: "Catalog",
    roles: ["ORG_ADMIN", "PHARMACIST"],
    match: ["/catalog", "/products"],
    items: [
      { to: "/catalog", label: "Catalog Overview", icon: Pill, end: true },
      { to: "/products", label: "Products", icon: Pill },
      { to: "/catalog/price-lists", label: "Price Lists", icon: CreditCard },
      { to: "/catalog/formularies", label: "Formularies", icon: ShieldCheck },
      { to: "/catalog/interactions", label: "Drug Interactions", icon: Shield },
      { to: "/catalog/substitutes", label: "Substitutes", icon: Pill },
      { to: "/catalog/uom", label: "UoM Conversions", icon: Boxes },
      { to: "/catalog/manufacturers", label: "Manufacturers", icon: Building2 },
      { to: "/catalog/ingredients", label: "Active Ingredients", icon: FileText },
      { to: "/catalog/low-stock", label: "Low Stock", icon: ClipboardList },
      { to: "/catalog/expiry", label: "Expiry Forecast", icon: Clock },
    ],
  },
  {
    label: "Insurance",
    roles: ["ORG_ADMIN", "PHARMACIST"],
    match: ["/insurance"],
    items: [
      { to: "/insurance", label: "Insurance Overview", icon: Shield, end: true },
      { to: "/insurance/claims", label: "Claims", icon: FileText },
      { to: "/insurance/schemes", label: "Schemes & Formulary", icon: Building2 },
      { to: "/insurance/members", label: "Member Policies", icon: Users },
      { to: "/insurance/remittances", label: "Remittances", icon: Receipt },
    ],
  },
  {
    label: "Connect",
    roles: "all",
    match: ["/connect"],
    items: [
      { to: "/connect/chat", label: "Chat", icon: MessageSquare },
      { to: "/connect/mail", label: "Mail", icon: Mail },
    ],
  },
  {
    label: "Distribution",
    roles: ["ORG_ADMIN", "PHARMACIST"],
    match: ["/distribution", "/suppliers"],
    items: [
      { to: "/distribution", label: "Distribution Overview", icon: Truck, end: true },
      { to: "/distribution/orders", label: "B2B Purchase Orders", icon: ClipboardList },
      { to: "/distribution/in-transit", label: "In-Transit Stock", icon: Truck },
      { to: "/distribution/grn", label: "Goods Received Notes", icon: PackageCheck },
      { to: "/distribution/listings", label: "Depot Offered Listings", icon: Store },
      { to: "/distribution/portal", label: "B2B Ordering Portal", icon: ShoppingCart },
      { to: "/distribution/demand", label: "Unmet Demand", icon: TrendingUp },
      { to: "/distribution/sales-reps", label: "Field Sales & Reps", icon: Users },
      { to: "/distribution/tenders", label: "Institutional Tenders", icon: FileText },
      { to: "/distribution/returns", label: "Customer Returns", icon: RotateCcw },
      { to: "/suppliers", label: "Suppliers", icon: Building2 },
    ],
  },
  {
    label: "Inventory",
    roles: ["ORG_ADMIN", "PHARMACIST"],
    match: ["/inventory"],
    items: [
      { to: "/inventory", label: "Warehouse Overview", icon: Warehouse, end: true },
      { to: "/inventory/warehouses", label: "Warehouses", icon: Building2 },
      { to: "/inventory/zones", label: "Zones & Bins", icon: Boxes },
      { to: "/inventory/putaway", label: "Put-away Rules", icon: MoveRight },
      { to: "/inventory/picking", label: "Wave Picking", icon: ClipboardList },
      { to: "/inventory/replenishment", label: "Replenishment", icon: RefreshCw },
      { to: "/inventory/serialisation", label: "Track & Trace", icon: ScanLine },
      { to: "/inventory/consignment", label: "Consignment / VMI", icon: Handshake },
      { to: "/inventory/temperature", label: "Temperature Logs", icon: Thermometer },
      { to: "/inventory/coldchain", label: "Cold-Chain Compliance", icon: RouteIcon },
      { to: "/inventory/qc", label: "Quality Control", icon: FileText },
      { to: "/inventory/recalls", label: "Batch Recalls", icon: Shield },
      { to: "/inventory/counts", label: "Physical Counts", icon: ClipboardList },
      { to: "/inventory/disposal", label: "Stock Disposal", icon: ScrollText },
    ],
  },
  {
    label: "Procurement",
    roles: ["ORG_ADMIN", "PROCUREMENT_OFFICER"],
    match: ["/procurement"],
    items: [
      { to: "/procurement", label: "Procurement Overview", icon: ShoppingBag, end: true },
      { to: "/procurement/requisitions", label: "Requisitions", icon: ClipboardList },
      { to: "/procurement/rfqs", label: "RFQ & Quotes", icon: FileSearch },
      { to: "/procurement/orders", label: "Purchase Orders", icon: ShoppingBag },
      { to: "/procurement/imports", label: "Imports & Landed Cost", icon: Ship },
      { to: "/procurement/receipts", label: "Goods Receipts", icon: PackageCheck },
      { to: "/procurement/invoices", label: "Supplier Invoices", icon: Receipt },
      { to: "/procurement/suppliers", label: "Supplier Master", icon: Handshake },
    ],
  },
  {
    label: "Retail",
    roles: "all",
    match: ["/retail", "/pos"],
    items: [
      { to: "/retail", label: "Retail Overview", icon: ShoppingCart, end: true },
      { to: "/pos", label: "Point of sale counter", icon: ShoppingCart },
      { to: "/retail/prescriptions", label: "Prescriptions & Refills", icon: FileText },
      { to: "/retail/controlled-drugs", label: "Controlled Drugs Log", icon: Shield },
      { to: "/retail/promotions", label: "Promotions & Coupons", icon: CreditCard },
      { to: "/retail/clinical-services", label: "Clinical Services", icon: ClipboardList },
    ],
  },
  {
    // Finance is one app with six jobs, not one list of twenty tables. The old nav
    // named tables — five separate receivables entries, four separate tax entries —
    // so a user could not predict where anything lived. These sections name the work
    // instead. See docs/development/finance-redesign-plan.md §2A.
    label: "Finance",
    app: "finance",
    roles: ["ACCOUNTANT", "ORG_ADMIN"],
    match: ["/finance"],
    items: [
      { to: "/finance", label: "Home", icon: Wallet, end: true },
      { to: "/finance/cockpit", label: "Performance cockpit", icon: BarChart3 },
    ],
  },
  {
    label: "Money in",
    app: "finance",
    roles: ["ACCOUNTANT", "ORG_ADMIN"],
    items: [
      { to: "/finance/receivables", label: "Customer invoices", icon: Receipt },
      { to: "/finance/statement", label: "Customer statements", icon: FileBarChart },
      { to: "/finance/dunning", label: "Collections & dunning", icon: Gavel },
      { to: "/finance/credit", label: "Credit control", icon: Wallet },
      { to: "/finance/aging", label: "Aging", icon: CreditCard },
    ],
  },
  {
    label: "Money out",
    app: "finance",
    roles: ["ACCOUNTANT", "ORG_ADMIN"],
    items: [
      { to: "/finance/payables", label: "Supplier bills", icon: CreditCard },
      { to: "/finance/payment-runs", label: "Payment runs", icon: Banknote },
    ],
  },
  {
    label: "Cash & bank",
    app: "finance",
    roles: ["ACCOUNTANT", "ORG_ADMIN"],
    items: [
      { to: "/finance/banking", label: "Accounts & cash book", icon: Landmark },
      { to: "/finance/reconciliation", label: "Bank reconciliation", icon: CheckCircle2 },
    ],
  },
  {
    label: "Ledger & close",
    app: "finance",
    roles: ["ACCOUNTANT", "ORG_ADMIN"],
    items: [
      { to: "/finance/accounts", label: "Chart of accounts", icon: BookOpen },
      { to: "/finance/cost-centres", label: "Cost centres", icon: Building2 },
      { to: "/finance/journal", label: "Journal", icon: ScrollText },
      { to: "/finance/statements", label: "Periods & close", icon: FileBarChart },
      { to: "/finance/schedules", label: "Accruals & prepayments", icon: Clock },
      { to: "/finance/assets", label: "Fixed assets", icon: BookOpen },
    ],
  },
  {
    label: "Tax & compliance",
    app: "finance",
    roles: ["ACCOUNTANT", "ORG_ADMIN"],
    items: [
      { to: "/finance/tax", label: "VAT return", icon: ScrollText },
      { to: "/finance/tax-ebm", label: "EBM audit", icon: ScrollText },
      { to: "/finance/tax/payments", label: "RRA payments", icon: Landmark },
      { to: "/finance/tax-codes", label: "Tax codes", icon: Receipt },
    ],
  },
  {
    label: "Performance",
    app: "finance",
    roles: ["ACCOUNTANT", "ORG_ADMIN"],
    items: [
      { to: "/finance/budgets", label: "Budgets & variance", icon: FileBarChart },
      { to: "/finance/tenant-settings", label: "Finance settings", icon: Sliders },
    ],
  },
  {
    label: "People",
    roles: ["HR_MANAGER", "ORG_ADMIN"],
    match: ["/people"],
    items: [
      { to: "/people", label: "Overview", icon: Users, end: true },
      { to: "/people/employees", label: "Employees", icon: UserCog },
      { to: "/people/attendance", label: "Time & Attendance", icon: Clock },
      { to: "/people/roster", label: "Shift Rosters", icon: Calendar },
      { to: "/people/leave", label: "Leave & Accrual", icon: UserCheck },
      { to: "/people/timesheets", label: "Timesheets", icon: ClipboardList },
      { to: "/people/payroll", label: "Payroll", icon: Wallet },
      { to: "/people/loans", label: "Loans & Advances", icon: CreditCard },
      { to: "/people/recruitment", label: "Recruitment", icon: UserCheck },
      { to: "/people/offboarding", label: "Offboarding", icon: LogOut },
      { to: "/people/filings", label: "Statutory Filings", icon: FileText },
      { to: "/people/statutory-rates", label: "Statutory rates", icon: ScrollText },
    ],
  },
  {
    label: "",
    roles: "all",
    items: [{ to: "/approvals", label: "Approvals", icon: ShieldCheck }],
  },
  {
    label: "Insights",
    roles: ["ORG_ADMIN"],
    match: ["/documents"],
    items: [{ to: "/documents", label: "Documents", icon: FileText }],
  },
  {
    label: "Admin",
    roles: ["ORG_ADMIN"],
    match: ["/admin", "/companies", "/organizations", "/departments", "/users", "/permissions", "/activity"],
    items: [
      { to: "/admin", label: "Admin Overview", icon: ShieldCheck, end: true },
      { to: "/companies", label: "Organizations & branches", icon: Building2 },
      { to: "/organizations", label: "Organizations", icon: Network },
      { to: "/departments", label: "Departments", icon: Boxes },
      { to: "/users", label: "Users & roles", icon: Users },
      { to: "/permissions", label: "Permissions", icon: ShieldCheck },
      { to: "/activity", label: "Audit log", icon: Activity },
    ],
  },
];

function ViewAsBanner() {
  const { user, stopImpersonating } = useAuth();
  if (!user?.impersonator) return null;
  return (
    <div className="sticky top-0 z-50 flex items-center justify-center gap-3 bg-amber-500 px-4 py-1.5 text-sm font-medium text-amber-950">
      <Eye className="h-4 w-4" />
      <span>
        Viewing as <strong>{user.username}</strong>
        {user.roles.length > 0 && <> ({user.roles.join(", ")})</>} — you are{" "}
        <strong>{user.impersonator.username}</strong>. Everything you do is audited.
      </span>
      <button
        onClick={() => void stopImpersonating()}
        className="rounded-md bg-amber-950/90 px-2.5 py-1 text-xs font-semibold text-amber-50 hover:bg-amber-950"
      >
        Exit view-as
      </button>
    </div>
  );
}

export function AppShell() {
  const { user, logout } = useAuth();
  const [paletteOpen, setPaletteOpen] = useState(false);

  // Tailor the nav to the signed-in role — a cashier sees the till, not the
  // whole admin console. Admins see everything.
  const admin = isAdmin(user);
  const userRoles = user?.roles ?? [];
  const canSee = (roles: "all" | string[] | undefined) =>
    roles === undefined || roles === "all" || admin || roles.some((r) => userRoles.includes(r));
  const visible = NAV.filter((g) => canSee(g.roles)).map((g) => ({
    ...g,
    items: g.items.filter((i) => canSee(i.roles ?? g.roles)),
  }));

  // App-scoped side nav (Oracle Fusion / Workspace behaviour): once you're inside an
  // app, show ONLY that app's contents — not every subsystem at once. Outside any app
  // (e.g. the dashboard) show the full menu so users can still get anywhere.
  const path = useLocation().pathname;
  const activeApp = visible.find((g) =>
    (g.match ?? []).some((p) => path === p || path.startsWith(p + "/")),
  );
  const nav = activeApp
    ? visible.filter(
        (g) =>
          g === activeApp ||
          // Sibling sections of the same app (see NavGroup.app).
          (activeApp.app !== undefined && g.app === activeApp.app) ||
          (g.match ?? []).length === 0,
      )
    : visible;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen(true);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="min-h-screen bg-surface-100 text-ink-900">
      <ViewAsBanner />
      <header className="sticky top-0 z-40 flex h-14 items-center gap-3 border-b border-line bg-surface-0 px-4">
        <AppSwitcher />
        <BrandMark />
        <span className="text-[15px] font-semibold tracking-tight">
          Pharma<span className="text-brand-600">Core</span>
        </span>
        <OrgSwitcher />
        <button
          onClick={() => setPaletteOpen(true)}
          className="ml-2 hidden items-center gap-2 rounded-md border border-line bg-surface-100 px-3 py-1.5 text-xs text-ink-500 hover:bg-surface-0 sm:flex"
        >
          <Search className="h-3.5 w-3.5" /> Search or run a command
          <kbd className="rounded border border-line px-1 font-mono text-[10px]">⌘K</kbd>
        </button>
        <div className="ml-auto flex items-center gap-3">
          <NotificationsBell />
          <div className="flex items-center gap-2 text-sm">
            <Users className="h-4 w-4 text-ink-500" />
            <span className="font-medium">{user?.username}</span>
            {user?.roles.map((r) => (
              <span key={r} className="rounded bg-surface-100 px-1.5 py-0.5 text-[11px] text-ink-500">
                {r}
              </span>
            ))}
          </div>
          <button
            onClick={logout}
            className="flex items-center gap-1.5 rounded-md px-2 py-1.5 text-sm text-ink-700 hover:bg-surface-100"
          >
            <LogOut className="h-4 w-4" /> Sign out
          </button>
        </div>
      </header>

      <div className="flex">
        <nav className="min-h-[calc(100vh-3.5rem)] w-56 border-r border-line bg-surface-0 p-2">
          {activeApp && (
            <div className="mb-2 border-b border-line pb-2">
              <NavLink
                to="/"
                className="flex items-center gap-2 rounded-md px-3 py-2 text-xs font-medium text-ink-500 hover:bg-surface-100 hover:text-ink-700"
              >
                <ChevronLeft className="h-3.5 w-3.5" /> All apps
              </NavLink>
              <div className="mt-1 flex items-center gap-2 px-3">
                <span className="text-sm font-semibold text-ink-900">{activeApp.label}</span>
              </div>
            </div>
          )}
          {nav.map((group, gi) =>
            group.items.length === 0 ? null : (
              <div key={group.label || `g${gi}`} className={group.label ? "mb-1 mt-3 first:mt-0" : ""}>
                {group.label && group !== activeApp && (
                  <div className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wide text-ink-500">
                    {group.label}
                  </div>
                )}
                {group.items.map(({ to, label, icon: Icon, end }) => (
                  <NavLink
                    key={to}
                    to={to}
                    end={end}
                    className={({ isActive }) =>
                      `mb-0.5 flex items-center gap-2.5 rounded-md px-3 py-2 text-sm ${
                        isActive
                          ? "bg-brand-50 font-semibold text-brand-700"
                          : "text-ink-700 hover:bg-surface-100"
                      }`
                    }
                  >
                    <Icon className="h-4 w-4" />
                    {label}
                  </NavLink>
                ))}
              </div>
            ),
          )}
          {admin && (
            <>
              <div className="mt-4 px-3 text-[11px] uppercase tracking-wide text-ink-500">
                More modules
              </div>
              {["Insurance", "Online store"].map((m) => (
                <div key={m} className="px-3 py-1.5 text-sm text-ink-500/60">
                  {m} <span className="text-[10px]">soon</span>
                </div>
              ))}
            </>
          )}
        </nav>

        <main className="min-w-0 flex-1 p-6">
          <Outlet />
        </main>
      </div>

      {paletteOpen && <CommandPalette onClose={() => setPaletteOpen(false)} />}
    </div>
  );
}
