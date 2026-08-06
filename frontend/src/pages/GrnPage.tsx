import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowLeft, CheckCircle2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Badge, Card, PageHeader, Spinner } from "../components/ui";
import { api } from "../lib/api";
import type { GoodsReceivedNote, Paginated } from "../lib/types";

export function GrnPage() {
  const navigate = useNavigate();

  const grnQuery = useQuery({
    queryKey: ["grn-list"],
    queryFn: () => api<Paginated<GoodsReceivedNote>>("/api/distribution/grn/"),
  });

  return (
    <div className="max-w-6xl">
      <button
        onClick={() => navigate("/distribution")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> Distribution Home
      </button>

      <PageHeader title="Goods Received Notes (GRN) Registry" />
      <p className="mb-4 text-sm text-ink-500">
        Immutable reception logs, batch line verification, and discrepancy tracking for all retail inventory landings.
      </p>

      {grnQuery.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {grnQuery.data && (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-line bg-surface-100 text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-3">GRN Number</th>
                <th className="px-4 py-3">Retail Branch</th>
                <th className="px-4 py-3">Order Ref</th>
                <th className="px-4 py-3">Discrepancy Status</th>
                <th className="px-4 py-3">Reception Date</th>
                <th className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {grnQuery.data.results.map((g) => (
                <tr key={g.id} className="border-b border-line last:border-0 hover:bg-surface-50">
                  <td className="px-4 py-3 font-mono font-semibold text-ink-900">{g.grn_number}</td>
                  <td className="px-4 py-3 font-medium text-ink-900">{g.retail_name}</td>
                  <td className="px-4 py-3 font-mono text-ink-700">PO-{g.order}</td>
                  <td className="px-4 py-3">
                    {g.has_discrepancy ? (
                      <Badge tone="danger">
                        <AlertTriangle className="h-3 w-3 inline mr-1" /> Discrepancy Found
                      </Badge>
                    ) : (
                      <Badge tone="success">
                        <CheckCircle2 className="h-3 w-3 inline mr-1" /> Fully Matched
                      </Badge>
                    )}
                  </td>
                  <td className="px-4 py-3 text-ink-700">
                    {new Date(g.received_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone="success">{g.status}</Badge>
                  </td>
                </tr>
              ))}
              {grnQuery.data.results.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-ink-500">
                    No Goods Received Notes found.
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
