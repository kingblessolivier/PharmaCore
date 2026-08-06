import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { PageHeader } from "../components/ui";
import { DataGrid } from "../components/DataGrid";
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

      <DataGrid<InTransitStock>
        rows={inTransitQuery.data?.results ?? []}
        loading={inTransitQuery.isLoading}
        getRowId={(t) => t.id}
        storageKey="in-transit"
        exportName="in-transit-stock"
        searchPlaceholder="Search by medicine, batch, depot or branch…"
        emptyMessage="No active stock currently in transit."
        columns={[
          {
            key: "product_name",
            header: "Medicine Product",
            render: (t) => <span className="font-semibold text-ink-900">{t.product_name}</span>,
          },
          {
            key: "batch_number",
            header: "Batch Number",
            render: (t) => <span className="font-mono text-ink-700">{t.batch_number}</span>,
          },
          { key: "source_name", header: "Origin Depot" },
          { key: "destination_name", header: "Destination Branch" },
          {
            key: "quantity",
            header: "Quantity",
            align: "right",
            numeric: true,
            render: (t) => <span className="font-semibold">{t.quantity.toLocaleString()}</span>,
          },
          {
            key: "dispatched_at",
            header: "Dispatch Time",
            value: (t) => t.dispatched_at,
            render: (t) => new Date(t.dispatched_at).toLocaleString(),
          },
        ]}
      />
    </div>
  );
}
