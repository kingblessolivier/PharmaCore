import { useQuery } from "@tanstack/react-query";
import {
  Building2,
  ChevronDown,
  LayoutDashboard,
  LogOut,
  Network,
  Pill,
  Search,
  Truck,
  Users,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { Organization, Paginated } from "../lib/types";
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

const nav = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/organizations", label: "Organizations", icon: Building2, end: false },
  { to: "/departments", label: "Departments", icon: Network, end: false },
  { to: "/products", label: "Catalog", icon: Pill, end: false },
  { to: "/suppliers", label: "Suppliers", icon: Truck, end: false },
];

export function AppShell() {
  const { user, logout } = useAuth();
  const [paletteOpen, setPaletteOpen] = useState(false);

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
      <header className="sticky top-0 z-40 flex h-14 items-center gap-3 border-b border-line bg-surface-0 px-4">
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
          <div className="mt-3 px-3 text-[11px] uppercase tracking-wide text-ink-500">More modules</div>
          {["Inventory", "Distribution", "Retail", "Finance"].map((m) => (
            <div key={m} className="px-3 py-1.5 text-sm text-ink-500/60">
              {m} <span className="text-[10px]">soon</span>
            </div>
          ))}
        </nav>

        <main className="min-w-0 flex-1 p-6">
          <Outlet />
        </main>
      </div>

      {paletteOpen && <CommandPalette onClose={() => setPaletteOpen(false)} />}
    </div>
  );
}
