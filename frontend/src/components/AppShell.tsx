import { Building2, LayoutDashboard, LogOut, Network, Users } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../lib/auth";

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

const nav = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/organizations", label: "Organizations", icon: Building2, end: false },
  { to: "/departments", label: "Departments", icon: Network, end: false },
];

export function AppShell() {
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen bg-surface-100 text-ink-900">
      {/* Top bar */}
      <header className="sticky top-0 z-40 flex h-14 items-center gap-3 border-b border-line bg-surface-0 px-4">
        <BrandMark />
        <span className="text-[15px] font-semibold tracking-tight">
          Pharma<span className="text-brand-600">Core</span>
        </span>
        <span className="rounded-full border border-line px-2.5 py-1 text-xs font-medium text-ink-700">
          <Building2 className="mr-1 inline h-3.5 w-3.5" />
          {user?.is_superuser ? "All organizations" : (user?.organization ?? "No organization")}
        </span>
        <div className="ml-auto flex items-center gap-3">
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
        {/* Side nav */}
        <nav className="min-h-[calc(100vh-3.5rem)] w-56 border-r border-line bg-surface-0 p-2">
          {nav.map(({ to, label, icon: Icon, end }) => (
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
          <div className="mt-3 px-3 text-[11px] uppercase tracking-wide text-ink-500">
            More modules
          </div>
          {["Catalog", "Inventory", "Distribution", "Retail", "Finance"].map((m) => (
            <div key={m} className="px-3 py-1.5 text-sm text-ink-500/60">
              {m} <span className="text-[10px]">soon</span>
            </div>
          ))}
        </nav>

        {/* Content */}
        <main className="min-w-0 flex-1 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
