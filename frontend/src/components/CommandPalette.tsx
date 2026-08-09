import { useQuery } from "@tanstack/react-query";
import { Building2, LayoutDashboard, Pill, Plus, Search, Truck } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ComponentType } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import type { Organization, Paginated, Product } from "../lib/types";

interface Command {
  id: string;
  label: string;
  hint?: string;
  icon: ComponentType<{ className?: string }>;
  run: () => void;
}

export function CommandPalette({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => inputRef.current?.focus(), []);

  const go = (path: string) => {
    navigate(path);
    onClose();
  };

  const products = useQuery({
    queryKey: ["palette-products", query],
    queryFn: () =>
      api<Paginated<Product>>(`/api/catalog/products/?search=${encodeURIComponent(query)}`),
    enabled: query.length >= 2,
  });
  const orgs = useQuery({
    queryKey: ["organizations"],
    queryFn: () => api<Paginated<Organization>>("/api/organizations/"),
  });

  const commands = useMemo<Command[]>(() => {
    const q = query.toLowerCase();
    const nav: Command[] = [
      { id: "n-dash", label: "Dashboard", icon: LayoutDashboard, run: () => go("/") },
      { id: "n-orgs", label: "Organizations", icon: Building2, run: () => go("/organizations") },
      { id: "n-cat", label: "Catalog", icon: Pill, run: () => go("/products") },
      { id: "n-sup", label: "Suppliers", icon: Truck, run: () => go("/suppliers") },
    ];
    const actions: Command[] = [
      {
        id: "a-org",
        label: "Register organization",
        hint: "action",
        icon: Plus,
        run: () => go("/organizations"),
      },
      {
        id: "a-med",
        label: "New medicine",
        hint: "action",
        icon: Plus,
        run: () => go("/products"),
      },
    ];
    const base = [...nav, ...actions].filter((c) => !q || c.label.toLowerCase().includes(q));

    const orgMatches: Command[] = q
      ? (orgs.data?.results ?? [])
          .filter((o) => o.name.toLowerCase().includes(q))
          .slice(0, 5)
          .map((o) => ({
            id: `o-${o.id}`,
            label: o.name,
            hint: "organization",
            icon: Building2,
            run: () => go(`/organizations/${o.id}`),
          }))
      : [];
    const productMatches: Command[] = (products.data?.results ?? []).slice(0, 6).map((p) => ({
      id: `p-${p.id}`,
      label: `${p.generic_name} ${p.strength}`.trim(),
      hint: "medicine",
      icon: Pill,
      run: () => go(`/products/${p.id}`),
    }));

    return [...base, ...orgMatches, ...productMatches];
  }, [query, orgs.data, products.data]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => setActive(0), [query]);

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, commands.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      commands[active]?.run();
    } else if (e.key === "Escape") {
      onClose();
    }
  }

  return (
    <div
      className="fixed inset-0 z-[1400] flex items-start justify-center bg-black/30 p-4 pt-[12vh]"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg overflow-hidden rounded-xl border border-line bg-surface-0 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 border-b border-line px-4">
          <Search className="h-4 w-4 text-ink-500" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Search or run a command…"
            className="w-full bg-transparent py-3 text-sm outline-none"
          />
          <kbd className="rounded border border-line px-1.5 font-mono text-[10px] text-ink-500">
            esc
          </kbd>
        </div>
        <ul className="max-h-80 overflow-y-auto p-1.5">
          {commands.map((c, i) => (
            <li key={c.id}>
              <button
                onMouseEnter={() => setActive(i)}
                onClick={c.run}
                className={`flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm ${
                  i === active ? "bg-brand-50 text-brand-700" : "text-ink-700 hover:bg-surface-100"
                }`}
              >
                <c.icon className="h-4 w-4" />
                <span className="flex-1">{c.label}</span>
                {c.hint && <span className="text-[11px] text-ink-500">{c.hint}</span>}
              </button>
            </li>
          ))}
          {commands.length === 0 && (
            <li className="px-3 py-6 text-center text-sm text-ink-500">No matches.</li>
          )}
        </ul>
      </div>
    </div>
  );
}
