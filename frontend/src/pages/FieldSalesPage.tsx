import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Badge, Card, PageHeader, Spinner } from "../components/ui";
import { api } from "../lib/api";
import type { Paginated, SalesRepresentative } from "../lib/types";

export function FieldSalesPage() {
  const navigate = useNavigate();

  const repsQuery = useQuery({
    queryKey: ["sales-reps-list"],
    queryFn: () => api<Paginated<SalesRepresentative>>("/api/distribution/sales-reps/"),
  });

  return (
    <div className="max-w-6xl">
      <button
        onClick={() => navigate("/distribution")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> Distribution Home
      </button>

      <PageHeader title="Field Sales Reps & Route-to-Market Portal (Van Sales & Pre-Sales)" />
      <p className="mb-4 text-sm text-ink-500">
        Medical representative master, territory beats, daily journey plans, van sales sell-from-stock, and rep commission ledgers.
      </p>

      {repsQuery.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {repsQuery.data && (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-line bg-surface-100 text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-3">Sales Rep Username</th>
                <th className="px-4 py-3">Territory / Beat</th>
                <th className="px-4 py-3 text-right">Monthly Target</th>
                <th className="px-4 py-3 text-right">Commission Rate</th>
                <th className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {repsQuery.data.results.map((r) => (
                <tr key={r.id} className="border-b border-line last:border-0 hover:bg-surface-50">
                  <td className="px-4 py-3 font-medium text-ink-900">{r.username}</td>
                  <td className="px-4 py-3 text-ink-700">
                    <Badge tone="brand">{r.territory_code}</Badge>
                  </td>
                  <td className="px-4 py-3 text-right font-mono font-semibold text-ink-900">
                    RWF {Number(r.monthly_sales_target).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right font-mono font-bold text-emerald-700">
                    {r.commission_rate_pct}%
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={r.is_active ? "success" : "neutral"}>
                      {r.is_active ? "Active On Field" : "Inactive"}
                    </Badge>
                  </td>
                </tr>
              ))}
              {repsQuery.data.results.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-ink-500">
                    No field sales representatives configured yet.
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
