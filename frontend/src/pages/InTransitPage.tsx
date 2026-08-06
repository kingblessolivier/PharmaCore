import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Card, PageHeader, Spinner } from "../components/ui";
import { api } from "../lib/api";
import type { InTransitStock, Paginated } from "../lib/types";

export function InTransitPage() {
  const navigate = useNavigate();

  const inTransitQuery = useQuery({
    queryKey: ["in-transit-list"],
    queryFn: () => api<Paginated<InTransitStock>>("/api/distribution/in-transit/"),
  });

  return (
    <div className="max-w-6xl">
      <button
        onClick={() => navigate("/distribution")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> Distribution Home
      </button>

      <PageHeader title="Live In-Transit Stock Monitor" />
      <p className="mb-4 text-sm text-ink-500">
        Real-time tracking of medicine batches currently en-route on delivery trucks between wholesale depots and retail pharmacies.
      </p>

      {inTransitQuery.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {inTransitQuery.data && (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-line bg-surface-100 text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-3">Medicine Product</th>
                <th className="px-4 py-3">Batch Number</th>
                <th className="px-4 py-3">Origin Depot</th>
                <th className="px-4 py-3">Destination Branch</th>
                <th className="px-4 py-3 text-right">Quantity</th>
                <th className="px-4 py-3">Dispatch Time</th>
              </tr>
            </thead>
            <tbody>
              {inTransitQuery.data.results.map((t) => (
                <tr key={t.id} className="border-b border-line last:border-0 hover:bg-surface-50">
                  <td className="px-4 py-3 font-semibold text-ink-900">{t.product_name}</td>
                  <td className="px-4 py-3 font-mono text-ink-700">{t.batch_number}</td>
                  <td className="px-4 py-3 text-ink-900">{t.source_name}</td>
                  <td className="px-4 py-3 text-ink-900">{t.destination_name}</td>
                  <td className="px-4 py-3 text-right font-mono font-bold text-ink-900">
                    {t.quantity.toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-ink-700">
                    {new Date(t.dispatched_at).toLocaleString()}
                  </td>
                </tr>
              ))}
              {inTransitQuery.data.results.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-ink-500">
                    No active stock currently in transit.
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
