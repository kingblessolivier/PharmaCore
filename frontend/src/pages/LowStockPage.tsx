import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowLeft, RefreshCw, Search, ShoppingCart } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button, Card, PageHeader, Spinner } from "../components/ui";
import { api } from "../lib/api";
import type { DashboardSummary } from "../lib/types";

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
    <div className="max-w-5xl">
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
      <p className="mb-4 text-sm text-ink-500">
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

      {isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {data && (
        <Card className="overflow-hidden">
          <div className="flex items-center justify-between border-b border-line bg-surface-100 px-4 py-3">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-600" />
              <span className="text-sm font-semibold text-ink-900">
                {filtered.length} Medicine(s) Below Minimum
              </span>
            </div>
            <Link to="/orders" className="text-xs font-medium text-brand-700 hover:underline flex items-center gap-1">
              <ShoppingCart className="h-3.5 w-3.5" /> Raise Purchase Order
            </Link>
          </div>

          <table className="w-full text-sm">
            <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-3">Medicine</th>
                <th className="px-4 py-3">Pharmacy / Branch</th>
                <th className="px-4 py-3 text-right">On Hand</th>
                <th className="px-4 py-3 text-right">Minimum Level</th>
                <th className="px-4 py-3 text-right">Deficit</th>
                <th className="px-4 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((item, idx) => {
                const deficit = Math.max(0, item.min - item.on_hand);
                return (
                  <tr key={idx} className="border-b border-line last:border-0 hover:bg-surface-50">
                    <td className="px-4 py-3 font-medium text-ink-900">{item.product}</td>
                    <td className="px-4 py-3 text-ink-700">{item.organization}</td>
                    <td className="px-4 py-3 text-right font-mono font-semibold text-red-600">
                      {item.on_hand}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-ink-500">{item.min}</td>
                    <td className="px-4 py-3 text-right font-mono text-amber-700">+{deficit}</td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        to="/orders"
                        className="inline-flex items-center gap-1 rounded bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-700 hover:bg-brand-100"
                      >
                        Reorder
                      </Link>
                    </td>
                  </tr>
                );
              })}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-sm text-ink-500">
                    {search ? "No low-stock items match your filter." : "All medicines are sufficiently stocked!"}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
