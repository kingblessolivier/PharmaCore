import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Badge, Card, PageHeader, Spinner } from "../components/ui";
import { api } from "../lib/api";
import type { CustomerReturn, Paginated } from "../lib/types";

export function CustomerReturnsPage() {
  const navigate = useNavigate();

  const returnsQuery = useQuery({
    queryKey: ["customer-returns-list"],
    queryFn: () => api<Paginated<CustomerReturn>>("/api/distribution/returns/"),
  });

  return (
    <div className="max-w-6xl">
      <button
        onClick={() => navigate("/distribution")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> Distribution Home
      </button>

      <PageHeader title="Retailer Return-to-Depot Requests & Credit Notes" />
      <p className="mb-4 text-sm text-ink-500">
        Return-to-depot inspection verification (Rwanda FDA saleable-returns regime) and credit note issuance.
      </p>

      {returnsQuery.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {returnsQuery.data && (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-line bg-surface-100 text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-3">Return #</th>
                <th className="px-4 py-3">Retail Pharmacy</th>
                <th className="px-4 py-3">Reason</th>
                <th className="px-4 py-3 text-right">Credit Note (RWF)</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Requested At</th>
              </tr>
            </thead>
            <tbody>
              {returnsQuery.data.results.map((r) => (
                <tr key={r.id} className="border-b border-line last:border-0 hover:bg-surface-50">
                  <td className="px-4 py-3 font-mono font-semibold text-ink-900">{r.return_number}</td>
                  <td className="px-4 py-3 font-medium text-ink-900">{r.retail_name}</td>
                  <td className="px-4 py-3 text-ink-700">{r.reason}</td>
                  <td className="px-4 py-3 text-right font-mono font-bold text-emerald-700">
                    RWF {Number(r.credit_note_amount).toLocaleString()}
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={r.status === "APPROVED" ? "success" : r.status === "REJECTED" ? "danger" : "warning"}>
                      {r.status}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-ink-700">
                    {new Date(r.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
              {returnsQuery.data.results.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-ink-500">
                    No retailer return requests filed yet.
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
