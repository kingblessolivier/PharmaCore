import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  PanelLeft,
  Activity,
  Banknote,
  BarChart3,
  Bell,
  BookOpen,
  Boxes,
  Building2,
  ChevronDown,
  ChevronLeft,
  ClipboardList,
  KeyRound,
  TriangleAlert,
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
  Clock,
  Wallet,
  Thermometer,
  Warehouse,
  PackageCheck,
  ShoppingBag,
  Ship,
  FileSearch,
  Receipt,
  Handshake,
  ScanLine,
  RefreshCw,
  Moon,
  Sun,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { can } from "../lib/roles";
import { applyTheme, storedTheme, type Theme } from "../lib/theme";
import type { AppNotification, Organization, Paginated } from "../lib/types";
import { ChangePasswordModal } from "./ChangePasswordModal";
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
  needs: "all" | string[];
}
const APPS: AppTile[] = [
  { label: "Retail", hue: "#0D9488", icon: ShoppingCart, to: "/retail", needs: ["sale.create"] },
  { label: "Catalog", hue: "#CA8A04", icon: Pill, to: "/catalog", needs: ["catalog.view"] },
  {
    label: "Distribution",
    hue: "#3B5BDB",
    icon: Truck,
    to: "/distribution",
    needs: ["distribution.view"],
  },
  {
    label: "Inventory",
    hue: "#0891B2",
    icon: Warehouse,
    to: "/inventory",
    needs: ["inventory.view"],
  },
  {
    label: "Procurement",
    hue: "#7C3AED",
    icon: ShoppingBag,
    to: "/procurement",
    needs: ["procurement.view"],
  },
  { label: "Finance", hue: "#15803D", icon: Wallet, to: "/finance", needs: ["finance.view"] },
  { label: "Insights", hue: "#DB2777", icon: BarChart3, to: "/", needs: "all" },
  {
    label: "Admin",
    hue: "#475569",
    icon: ShieldCheck,
    to: "/admin",
    needs: ["organization.manage"],
  },
  { label: "Insurance", hue: "#7C3AED", icon: Shield, to: "/insurance", needs: ["insurance.view"] },
  {
    label: "People",
    hue: "#EA580C",
    icon: Users,
    to: "/people",
    needs: ["employee.view", "user.manage"],
  },
  { label: "Online", hue: "#0EA5E9", icon: Globe, to: null, needs: "all" },
  { label: "Connect", hue: "#2563EB", icon: MessageSquare, to: "/connect/chat", needs: "all" },
];

function AppSwitcher() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const canSee = (needs: "all" | string[]) =>
    needs === "all" || needs.some((code) => can(user, code));
  const tiles = APPS.filter((t) => canSee(t.needs));

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
          <div className="px-1 pb-2 text-[11px] font-semibold text-ink-500">
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

/** The branch this session is posting to, named in the status bar.
 *
 * Reads the same query as the switcher above rather than taking a prop, so the
 * bar and the switcher cannot drift into naming different places. */
function StatusOrg() {
  const { user } = useAuth();
  const { data } = useQuery({
    queryKey: ["organizations"],
    queryFn: () => api<Paginated<Organization>>("/api/organizations/"),
  });
  const label = user?.is_superuser
    ? "All organizations"
    : (data?.results[0]?.name ?? "No branch selected");
  return (
    <span className="flex items-center gap-1">
      <Building2 size={12} className="text-ink-500" aria-hidden />
      {label}
    </span>
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

  const label = user?.is_superuser
    ? "All organizations"
    : (data?.results[0]?.name ?? "Organization");

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

function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(() => storedTheme());
  const dark = theme === "dark";
  return (
    <button
      onClick={() => {
        const next: Theme = dark ? "light" : "dark";
        setTheme(next);
        applyTheme(next);
      }}
      className="rounded-md p-1.5 text-ink-600 hover:bg-surface-100"
      aria-label={dark ? "Switch to light" : "Switch to dark"}
      title={dark ? "Switch to light" : "Switch to dark"}
    >
      {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </button>
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
              <button
                onClick={() => markAll.mutate()}
                className="text-xs text-brand-700 hover:underline"
              >
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
                      stock_order: "/distribution/orders",
                      orders: "/distribution/orders",
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
  /** Per-item override; else inherits the group's. */
  needs?: "all" | string[];
}

interface NavGroup {
  label: string; // "" = ungrouped (rendered without a header)
  /**
   * Permission codes that reveal this group — **capability, not job title**.
   *
   * The nav used to gate on role names, and five of the eleven seeded roles
   * appeared in no group at all: a warehouse clerk could not open Inventory, a
   * dispatcher could not open Distribution, an insurance clerk could not open
   * Insurance (audit D7). Every one of those screens was built for exactly the
   * person who could not reach it. Gating on what someone may *do* fixes that
   * class of bug permanently — add a role, grant it permissions, and the nav
   * follows without anyone editing this file.
   *
   * "all" means every signed-in user (Connect, the dashboard).
   */
  needs: "all" | string[];
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
  {
    label: "",
    needs: "all",
    items: [{ to: "/", label: "Dashboard", icon: LayoutDashboard, end: true }],
  },
  {
    label: "Catalog",
    needs: ["catalog.view"],
    match: ["/catalog", "/products"],
    items: [
      { to: "/catalog", label: "Catalog Overview", icon: Pill, end: true },
      { to: "/products", label: "Products", icon: Pill },
      { to: "/catalog/price-lists", label: "Price Lists", icon: CreditCard },
      { to: "/catalog/formularies", label: "Formularies", icon: ShieldCheck },
      { to: "/catalog/manufacturers", label: "Reference data", icon: Boxes },
      { to: "/catalog/low-stock", label: "Low Stock", icon: ClipboardList },
      { to: "/catalog/expiry", label: "Expiry Forecast", icon: Clock },
    ],
  },
  {
    label: "Insurance",
    needs: ["insurance.view"],
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
    needs: "all",
    match: ["/connect"],
    items: [
      { to: "/connect/chat", label: "Chat", icon: MessageSquare },
      { to: "/connect/mail", label: "Mail", icon: Mail },
    ],
  },
  {
    label: "Distribution",
    needs: ["distribution.view"],
    match: ["/distribution"],
    items: [
      { to: "/distribution", label: "Distribution Overview", icon: Truck, end: true },
      { to: "/distribution/orders", label: "Orders to depots", icon: ClipboardList },
      { to: "/distribution/in-transit", label: "In-Transit Stock", icon: Truck },
      { to: "/distribution/grn", label: "Depot deliveries received", icon: PackageCheck },
      { to: "/distribution/listings", label: "Depot Offered Listings", icon: Store },
      { to: "/distribution/portal", label: "B2B Ordering Portal", icon: ShoppingCart },
      { to: "/distribution/demand", label: "Unmet Demand", icon: TrendingUp },
      { to: "/distribution/sales-reps", label: "Field Sales & Reps", icon: Users },
      { to: "/distribution/tenders", label: "Institutional Tenders", icon: FileText },
      { to: "/distribution/returns", label: "Customer Returns", icon: RotateCcw },
    ],
  },
  {
    label: "Inventory",
    needs: ["inventory.view"],
    match: ["/inventory"],
    items: [
      { to: "/inventory", label: "Warehouse Overview", icon: Warehouse, end: true },
      { to: "/inventory/warehouses", label: "Warehouse setup", icon: Building2 },
      { to: "/inventory/picking", label: "Wave Picking", icon: ClipboardList },
      { to: "/inventory/replenishment", label: "Replenishment", icon: RefreshCw },
      { to: "/inventory/serialisation", label: "Track & Trace", icon: ScanLine },
      { to: "/inventory/consignment", label: "Consignment / VMI", icon: Handshake },
      { to: "/inventory/coldchain", label: "Cold chain", icon: Thermometer },
      { to: "/inventory/qc", label: "Quality Control", icon: FileText },
      { to: "/inventory/recalls", label: "Batch Recalls", icon: Shield },
      { to: "/inventory/counts", label: "Physical Counts", icon: ClipboardList },
      { to: "/inventory/disposal", label: "Stock Disposal", icon: ScrollText },
    ],
  },
  {
    label: "Procurement",
    needs: ["procurement.view"],
    match: ["/procurement", "/suppliers"],
    items: [
      { to: "/procurement", label: "Procurement Overview", icon: ShoppingBag, end: true },
      { to: "/procurement/requisitions", label: "Requisitions", icon: ClipboardList },
      { to: "/procurement/rfqs", label: "RFQ & Quotes", icon: FileSearch },
      { to: "/procurement/orders", label: "Supplier purchase orders", icon: ShoppingBag },
      { to: "/procurement/imports", label: "Imports & Landed Cost", icon: Ship },
      { to: "/procurement/receipts", label: "Supplier goods receipts", icon: PackageCheck },
      { to: "/procurement/invoices", label: "Supplier Invoices", icon: Receipt },
      { to: "/suppliers", label: "Supplier directory", icon: Building2 },
      { to: "/procurement/suppliers", label: "Supplier qualification", icon: Handshake },
    ],
  },
  {
    // Not "all" any more: a driver and a warehouse clerk both landed on the
    // point-of-sale till, which is the one screen neither should open.
    label: "Retail",
    needs: ["sale.create"],
    match: ["/retail", "/pos"],
    items: [
      { to: "/retail", label: "Retail Overview", icon: ShoppingCart, end: true },
      { to: "/pos", label: "Point of sale counter", icon: ShoppingCart },
      { to: "/retail/sales", label: "Sales history", icon: Receipt },
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
    // Reading your branch's numbers is `finance.view`; the ledger itself is
    // `finance.manage`. Without the split, giving a branch manager sight of
    // their own margin also handed them the chart of accounts and the VAT
    // return, which is how "just make them an admin" starts.
    label: "Finance",
    app: "finance",
    needs: ["finance.view"],
    match: ["/finance"],
    items: [
      { to: "/finance", label: "Home", icon: Wallet, end: true },
      { to: "/finance/cockpit", label: "Performance cockpit", icon: BarChart3 },
      { to: "/finance/risk", label: "Risk & cash cycle", icon: TriangleAlert },
    ],
  },
  {
    label: "Money in",
    app: "finance",
    needs: ["finance.view"],
    items: [{ to: "/finance/receivables", label: "Customer money", icon: Receipt }],
  },
  {
    label: "Money out",
    app: "finance",
    needs: ["finance.manage"],
    items: [
      { to: "/finance/payables", label: "Supplier bills", icon: CreditCard },
      { to: "/finance/payment-runs", label: "Payment runs", icon: Banknote },
      { to: "/finance/banking", label: "Cash & bank", icon: Landmark },
    ],
  },
  {
    label: "Ledger & close",
    app: "finance",
    needs: ["finance.manage"],
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
    // Tax was four entries — VAT return, EBM audit, RRA payments, tax codes.
    // They are one desk worked in that order, so they are one screen now, and a
    // group heading over a single item is just a heading.
    label: "Performance",
    app: "finance",
    needs: ["finance.view"],
    items: [
      { to: "/finance/tax", label: "Tax & compliance", icon: ScrollText },
      { to: "/finance/budgets", label: "Budgets & variance", icon: FileBarChart },
      {
        to: "/finance/tenant-settings",
        label: "Finance settings",
        icon: Sliders,
        needs: ["finance.manage"],
      },
    ],
  },
  {
    label: "People",
    needs: ["employee.view", "user.manage"],
    match: ["/people"],
    items: [
      { to: "/people", label: "Overview", icon: Users, end: true },
      { to: "/people/employees", label: "Employees", icon: UserCog },
      { to: "/people/records", label: "Employee records", icon: ClipboardList },
      { to: "/people/attendance", label: "Time & attendance", icon: Clock },
      { to: "/people/leave", label: "Leave & Accrual", icon: UserCheck },
      { to: "/people/payroll", label: "Payroll", icon: Wallet },
      { to: "/people/loans", label: "Loans & Advances", icon: CreditCard },
      { to: "/people/recruitment", label: "Recruitment", icon: UserCheck },
      { to: "/people/offboarding", label: "Offboarding", icon: LogOut },
      { to: "/people/filings", label: "Statutory filings", icon: FileText },
    ],
  },
  {
    label: "",
    needs: ["approval.decide"],
    items: [{ to: "/approvals", label: "Approvals", icon: ShieldCheck }],
  },
  {
    label: "Insights",
    needs: ["audit.view", "finance.view"],
    match: ["/documents"],
    items: [{ to: "/documents", label: "Documents", icon: FileText }],
  },
  {
    label: "Admin",
    needs: ["organization.manage", "company.manage"],
    match: [
      "/admin",
      "/companies",
      "/organizations",
      "/departments",
      "/users",
      "/permissions",
      "/activity",
    ],
    items: [
      { to: "/admin", label: "Admin Overview", icon: ShieldCheck, end: true },
      { to: "/companies", label: "Organizations & branches", icon: Building2 },
      { to: "/departments", label: "Departments", icon: Boxes },
      { to: "/users", label: "Users & access", icon: Users },
      { to: "/activity", label: "Audit log", icon: Activity },
    ],
  },
];

function ViewAsBanner() {
  const { user, stopImpersonating } = useAuth();
  if (!user?.impersonator) return null;
  return (
    <div className="z-50 flex shrink-0 items-center justify-center gap-3 bg-amber-500 px-4 py-1.5 text-sm font-medium text-amber-950">
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
  const [passwordOpen, setPasswordOpen] = useState(false);

  /* Collapse the sidebar to its glyphs. Remembered, because this is a working
     preference rather than a per-visit one: somebody who wants the width back
     for a wide table wants it back tomorrow too. Every item keeps a `title`
     when collapsed, so the icon alone is never the only way to identify it. */
  const [railOnly, setRailOnly] = useState(() => localStorage.getItem("nav-rail") === "1");
  const toggleRail = () => {
    setRailOnly((on) => {
      localStorage.setItem("nav-rail", on ? "0" : "1");
      return !on;
    });
  };

  // Tailor the nav to what the signed-in user may actually do. A cashier sees the
  // till, not the admin console; a warehouse clerk sees Inventory, which the old
  // role-name gate denied them. `can()` already grants everything to a superuser
  // and SYS_ADMIN, so no separate admin bypass is needed here.
  const canSee = (needs: "all" | string[] | undefined) =>
    needs === undefined || needs === "all" || needs.some((code) => can(user, code));

  /* A depot is not a shop, so it is not offered a counter.
   *
   * The till refuses a depot at the door (apps/retail/views_counter._org), and
   * a menu entry that leads only to a refusal is worse than no entry — it reads
   * as a bug rather than as a rule. A depot moves stock on B2B orders; the two
   * book revenue differently and neither should be able to post the other's
   * transactions. */
  const sellsOverTheCounter = !["DEPOT", "HQ", "DISTRIBUTOR"].includes(
    user?.organization_type ?? "",
  );
  const visible = NAV.filter(
    (g) => canSee(g.needs) && (sellsOverTheCounter || g.label !== "Retail"),
  ).map((g) => ({
    ...g,
    items: g.items.filter((i) => canSee(i.needs ?? g.needs)),
  }));

  /* App-scoped side nav: inside an app you see that app, and nothing else.
   *
   * This existed and leaked badly. "No `match`" was being read as "always
   * visible" — a rule meant for Dashboard, Approvals and Connect, which really
   * are global. But Finance's six sections carry `app: "finance"` and no `match`
   * of their own, so they fell through it into every app: a cashier standing at
   * the till was shown "Ledger & close" and "Chart of accounts".
   *
   * Global now means what it says — no `match` AND no `app`. A group that
   * belongs to an app is only ever shown inside it.
   *
   * And outside any app the menu no longer lists all 89 entries. Picking a
   * subsystem is what the app switcher is for; a side nav that shows everything
   * at once is a directory, not a navigation.
   */
  const path = useLocation().pathname;
  const isGlobal = (g: NavGroup) => (g.match ?? []).length === 0 && g.app === undefined;
  const activeApp = visible.find((g) =>
    (g.match ?? []).some((p) => path === p || path.startsWith(p + "/")),
  );
  const nav = visible.filter(
    (g) =>
      isGlobal(g) ||
      (activeApp !== undefined &&
        (g === activeApp ||
          // Sibling sections of the same app (see NavGroup.app).
          (activeApp.app !== undefined && g.app === activeApp.app))),
  );

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
    <div className="flex h-screen flex-col overflow-hidden text-ink-900">
      <ViewAsBanner />
      <header className="z-40 flex h-11 shrink-0 items-center gap-2 border-b border-chrome-600 bg-gradient-to-b from-chrome-100 to-chrome-300 px-2 shadow-[inset_0_1px_0_#fff]">
        <button
          onClick={toggleRail}
          title={railOnly ? "Expand the menu" : "Collapse the menu"}
          aria-label={railOnly ? "Expand the menu" : "Collapse the menu"}
          aria-expanded={!railOnly}
          className="rounded-md p-1.5 text-ink-600 hover:bg-surface-100"
        >
          <PanelLeft className="h-[18px] w-[18px]" />
        </button>
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
          <ThemeToggle />
          <NotificationsBell />
          <div className="flex items-center gap-2 text-sm">
            <Users className="h-4 w-4 text-ink-500" />
            <span className="font-medium">{user?.username}</span>
            {user?.roles.map((r) => (
              <span
                key={r}
                className="rounded bg-surface-100 px-1.5 py-0.5 text-[11px] text-ink-500"
              >
                {r}
              </span>
            ))}
          </div>
          {/* Next to Sign out, which is where somebody looks for it. There was
              no way to change your own password at all: the only route out of
              one a colleague had seen was to ask an admin to reset it. */}
          <button
            onClick={() => setPasswordOpen(true)}
            title="Change your password"
            className="flex items-center gap-1.5 rounded-md px-2 py-1.5 text-sm text-ink-700 hover:bg-surface-100"
          >
            <KeyRound className="h-4 w-4" /> Password
          </button>
          <button
            onClick={logout}
            className="flex items-center gap-1.5 rounded-md px-2 py-1.5 text-sm text-ink-700 hover:bg-surface-100"
          >
            <LogOut className="h-4 w-4" /> Sign out
          </button>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <nav
          className={`${railOnly ? "w-12" : "w-52"} shrink-0 overflow-y-auto overflow-x-hidden border-r border-chrome-600 bg-chrome-200 p-1 transition-[width] duration-150`}
        >
          {activeApp && (
            <div className="mb-2 border-b border-line pb-2">
              <NavLink
                to="/"
                title="All apps"
                className="flex items-center gap-2 rounded-md px-3 py-2 text-xs font-medium text-ink-500 hover:bg-surface-100 hover:text-ink-700"
              >
                <ChevronLeft className="h-3.5 w-3.5 shrink-0" />
                {!railOnly && "All apps"}
              </NavLink>
              {!railOnly && (
                <div className="mt-1 flex items-center gap-2 px-3">
                  <span className="text-sm font-semibold text-ink-900">{activeApp.label}</span>
                </div>
              )}
            </div>
          )}
          {nav.map((group, gi) =>
            group.items.length === 0 ? null : (
              <div
                key={group.label || `g${gi}`}
                className={group.label ? "mb-1 mt-3 first:mt-0" : ""}
              >
                {group.label && group !== activeApp && !railOnly && (
                  <div className="px-3 pb-1 text-[11px] font-semibold text-ink-500">
                    {group.label}
                  </div>
                )}
                {/* Collapsed, a heading becomes a rule: the grouping survives
                    even when its name cannot be shown. */}
                {group.label && group !== activeApp && railOnly && (
                  <div className="mx-2 mb-1 border-t border-line" />
                )}
                {group.items.map(({ to, label, icon: Icon, end }) => (
                  <NavLink
                    key={to}
                    to={to}
                    end={end}
                    title={label}
                    className={({ isActive }) =>
                      /* 26px rows, not 38. A module with fourteen screens
                         fits without scrolling the menu, which is the whole
                         reason a dense ERP nav exists. */
                      `mb-px flex items-center gap-2 rounded-[2px] px-2 py-1 text-[12px] ${
                        isActive
                          ? "border border-chrome-500 bg-surface-0 font-semibold text-chrome-900"
                          : "border border-transparent text-ink-700 hover:bg-chrome-200"
                      }`
                    }
                  >
                    <Icon size={14} className="shrink-0" />
                    {!railOnly && label}
                  </NavLink>
                ))}
              </div>
            ),
          )}
          {can(user, "organization.manage") && !railOnly && (
            <>
              <div className="mt-4 px-3 text-[11px] text-ink-500">
                More modules
              </div>
              {/* Insurance used to be listed here as "soon". It has been built since,
                  so advertising it as unbuilt sent people looking for a screen that
                  is already two clicks away. */}
              {["Online store"].map((m) => (
                <div key={m} className="px-3 py-1.5 text-sm text-ink-500/60">
                  {m} <span className="text-[10px]">soon</span>
                </div>
              ))}
            </>
          )}
        </nav>

        <main className="min-w-0 flex-1 overflow-y-auto bg-chrome-50 p-2.5">
          <Outlet />
        </main>
      </div>

      {/* The status bar.

          An ERP tells you where you are and who you are at the bottom of the
          window, permanently — not in a toast that fades. Somebody four hours
          into a shift, working two branches, needs to be able to answer "which
          pharmacy am I posting this to" without leaving the screen. */}
      <footer className="flex h-[22px] shrink-0 items-center gap-3 border-t border-chrome-600 bg-gradient-to-b from-chrome-100 to-chrome-300 px-2 text-[11px] text-ink-700">
        <StatusOrg />
        <span className="flex items-center gap-1">
          <Users size={12} className="text-ink-500" aria-hidden />
          {user?.username}
          {user?.roles?.[0] && <span className="text-ink-500">· {user.roles[0]}</span>}
        </span>
        <span className="ml-auto flex items-center gap-1 text-ink-500">
          PharmaCore
          <span className="font-mono">{import.meta.env.MODE === "production" ? "PRD" : "DEV"}</span>
        </span>
      </footer>

      {paletteOpen && <CommandPalette onClose={() => setPaletteOpen(false)} />}
      {passwordOpen && <ChangePasswordModal onClose={() => setPasswordOpen(false)} />}
    </div>
  );
}
