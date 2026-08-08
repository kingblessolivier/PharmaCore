import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, RefreshCw, Search } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import type { DashboardSummary } from "../lib/types";
import { DataGrid } from "../components/DataGrid";

export function LowStockPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api<DashboardSummary>("/api/dashboard/"),
  });

  const items = data?.low_stock.items ?? [];
  const filtered = items.filter(
    (i) =>
      i.product.toLowerCase().includes(search.toLowerCase()) ||
      i.organization.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div>
      <button
        onClick={() => navigate("/catalog")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> Catalog Home
      </button>

      <PageHeader
        title="Low-Stock Reorder List"
        action={
          <Button variant="secondary" onClick={() => refetch()}>
            <RefreshCw className="h-4 w-4" /> Refresh
          </Button>
        }
      />
      <p className="mb-4 text-sm text-ink-500 max-w-3xl">
        Medicines across your pharmacies that are below their minimum threshold and require reordering.
      </p>

      <div className="mb-4 flex items-center gap-2 rounded-md border border-line bg-surface-0 px-3 py-2">
        <Search className="h-4 w-4 text-ink-500" />
        <input
          className="w-full bg-transparent text-sm outline-none"
          placeholder="Filter by medicine or pharmacy branch..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <DataGrid
        rows={filtered}
        loading={isLoading}
        getRowId={(r) => `${r.product}-${r.organization}`}
        storageKey="low-stock"
        exportName="low-stock"
        searchPlaceholder="Search by medicine or branch…"
        emptyMessage="Nothing is below its minimum level."
        columns={[
          { key: "product", header: "Medicine", value: (r) => r.product },
          { key: "organization", header: "Pharmacy / branch", value: (r) => r.organization },
          {
            key: "on_hand",
            header: "On hand",
            align: "right",
            numeric: true,
            value: (r) => r.on_hand,
            render: (r) => (
              <span className="font-mono font-semibold text-danger-600">{r.on_hand}</span>
            ),
          },
          {
            key: "min",
            header: "Minimum level",
            align: "right",
            numeric: true,
            value: (r) => r.min,
            render: (r) => <span className="font-mono text-ink-500">{r.min}</span>,
          },
          {
            key: "deficit",
            header: "Deficit",
            align: "right",
            numeric: true,
            value: (r) => Math.max(0, r.min - r.on_hand),
            render: (r) => (
              <span className="font-mono text-warning-700">
                +{Math.max(0, r.min - r.on_hand)}
              </span>
            ),
          },
          {
            key: "action",
            header: "",
            align: "right",
            fixed: true,
            sortable: false,
            render: () => (
              <Link
                to="/orders"
                className="inline-flex items-center gap-1 rounded bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-700 hover:bg-brand-100"
              >
                Reorder
              </Link>
            ),
          },
        ]}
      />

    </div>
  );
}
