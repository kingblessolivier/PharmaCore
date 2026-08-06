import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Card, PageHeader, Spinner } from "../components/ui";
import { api } from "../lib/api";
import type { Paginated, TenderContract } from "../lib/types";

export function InstitutionalTendersPage() {
  const navigate = useNavigate();

  const tendersQuery = useQuery({
    queryKey: ["tenders-list"],
    queryFn: () => api<Paginated<TenderContract>>("/api/distribution/tenders/"),
  });

  return (
    <div className="max-w-6xl">
      <button
        onClick={() => navigate("/distribution")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> Distribution Home
      </button>

      <PageHeader title="Institutional & B2G Customer Tenders (Hospitals, NGOs & MOH Contracts)" />
      <p className="mb-4 text-sm text-ink-500">
        Awarded tender contract price locks, committed bulk volume balance, and scheduled call-off order tracking.
      </p>

      {tendersQuery.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {tendersQuery.data && (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-line bg-surface-100 text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-3">Tender #</th>
                <th className="px-4 py-3">Institutional Client</th>
                <th className="px-4 py-3">Product Name</th>
                <th className="px-4 py-3 text-right">Contract Price (RWF)</th>
                <th className="px-4 py-3 text-right">Committed Qty</th>
                <th className="px-4 py-3 text-right">Remaining Balance</th>
                <th className="px-4 py-3">Valid Until</th>
              </tr>
            </thead>
            <tbody>
              {tendersQuery.data.results.map((t) => (
                <tr key={t.id} className="border-b border-line last:border-0 hover:bg-surface-50">
                  <td className="px-4 py-3 font-mono font-semibold text-ink-900">{t.tender_number}</td>
                  <td className="px-4 py-3 font-medium text-ink-900">{t.client_name}</td>
                  <td className="px-4 py-3 text-ink-700">{t.product_name}</td>
                  <td className="px-4 py-3 text-right font-mono font-bold text-ink-900">
                    RWF {Number(t.contract_price).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-ink-900">{t.total_committed_qty} units</td>
                  <td className="px-4 py-3 text-right font-mono font-bold text-emerald-700">
                    {t.remaining_qty} units
                  </td>
                  <td className="px-4 py-3 text-ink-700">{t.valid_until}</td>
                </tr>
              ))}
              {tendersQuery.data.results.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-ink-500">
                    No institutional tender contracts registered yet.
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
