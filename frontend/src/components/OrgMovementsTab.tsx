import { useQuery } from "@tanstack/react-query";
import { Spinner } from "./ui";
import { api } from "../lib/api";
import type { Paginated, StockMovement } from "../lib/types";

const TYPE_LABEL: Record<string, string> = {
  INTAKE: "Supplier intake",
  TRANSFER_IN: "Transfer in",
  TRANSFER_OUT: "Transfer out",
  SALE: "Sale",
  RETURN: "Return / void",
  WASTAGE: "Wastage",
  ADJUSTMENT: "Adjustment",
  RECALL: "Recall",
};

const TONE: Record<string, string> = {
  INTAKE: "text-green-700",
  TRANSFER_IN: "text-green-700",
  RETURN: "text-green-700",
  TRANSFER_OUT: "text-red-600",
  SALE: "text-red-600",
  WASTAGE: "text-red-600",
};

export function OrgMovementsTab({ organizationId }: { organizationId: number }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["movements", organizationId],
    queryFn: () =>
      api<Paginated<StockMovement>>(`/api/inventory/movements/?organization=${organizationId}`),
  });

  return (
    <div>
      <h2 className="mb-1 text-sm font-semibold text-ink-900">Stock movement ledger</h2>
      <p className="mb-3 text-xs text-ink-500">
        Every quantity change, append-only — the full audit trail of stock in and out.
      </p>

      {isLoading && (
        <div className="flex justify-center py-8">
          <Spinner />
        </div>
      )}
      {isError && <p className="text-sm text-red-600">Failed to load movements.</p>}

      {data && (
        <div className="overflow-hidden rounded-lg border border-line bg-surface-0">
          <table className="w-full text-sm">
            <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-2.5">When</th>
                <th className="px-4 py-2.5">Type</th>
                <th className="px-4 py-2.5">Medicine · batch</th>
                <th className="px-4 py-2.5 text-right">Change</th>
                <th className="px-4 py-2.5">By</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((m) => (
                <tr key={m.id} className="border-b border-line last:border-0 hover:bg-surface-100">
                  <td className="px-4 py-2.5 text-ink-600">
                    {new Date(m.occurred_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-2.5">{TYPE_LABEL[m.movement_type] ?? m.movement_type}</td>
                  <td className="px-4 py-2.5">
                    <span className="font-medium">{m.product_name}</span>
                    {m.batch_number && (
                      <span className="ml-1 font-mono text-xs text-ink-500">
                        · {m.batch_number}
                      </span>
                    )}
                  </td>
                  <td
                    className={`px-4 py-2.5 text-right font-mono ${TONE[m.movement_type] ?? "text-ink-700"}`}
                  >
                    {m.quantity_delta > 0 ? "+" : ""}
                    {m.quantity_delta}
                  </td>
                  <td className="px-4 py-2.5 text-ink-600">{m.created_by ?? "—"}</td>
                </tr>
              ))}
              {data.results.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-ink-500">
                    No stock movements yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
