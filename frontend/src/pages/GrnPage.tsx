import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowLeft, CheckCircle2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Badge, PageHeader } from "../components/ui";
import { DataGrid } from "../components/DataGrid";
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

      <DataGrid<GoodsReceivedNote>
        rows={grnQuery.data?.results ?? []}
        loading={grnQuery.isLoading}
        getRowId={(g) => g.id}
        storageKey="grn"
        exportName="goods-received-notes"
        searchPlaceholder="Search by GRN number, branch or order…"
        emptyMessage="No Goods Received Notes found."
        columns={[
          {
            key: "grn_number",
            header: "GRN Number",
            render: (g) => <span className="font-mono font-semibold">{g.grn_number}</span>,
          },
          {
            key: "retail_name",
            header: "Retail Branch",
            render: (g) => <span className="font-medium">{g.retail_name}</span>,
          },
          {
            key: "order",
            header: "Order Ref",
            value: (g) => `PO-${g.order}`,
            render: (g) => <span className="font-mono text-ink-700">PO-{g.order}</span>,
          },
          {
            key: "has_discrepancy",
            header: "Discrepancy Status",
            value: (g) => (g.has_discrepancy ? "Discrepancy Found" : "Fully Matched"),
            render: (g) =>
              g.has_discrepancy ? (
                <Badge tone="danger">
                  <AlertTriangle className="mr-1 inline h-3 w-3" /> Discrepancy Found
                </Badge>
              ) : (
                <Badge tone="success">
                  <CheckCircle2 className="mr-1 inline h-3 w-3" /> Fully Matched
                </Badge>
              ),
          },
          {
            key: "received_at",
            header: "Reception Date",
            value: (g) => g.received_at,
            render: (g) => new Date(g.received_at).toLocaleDateString(),
          },
          {
            key: "status",
            header: "Status",
            render: (g) => <Badge tone="success">{g.status}</Badge>,
          },
        ]}
      />
    </div>
  );
}
