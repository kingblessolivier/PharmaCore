/* -------------------------------------------------------------------------- */
/* Expiry forecast — the batches, not just the count of them.                 */
/*                                                                             */
/* This screen promised "batch tracking" and showed two aggregate numbers. A   */
/* count tells you there is a problem; it does not tell you which shelf to walk */
/* to. Expiry is only actionable per batch — you sell it through, move it, or   */
/* destroy it — so the batches are the screen.                                  */
/* -------------------------------------------------------------------------- */

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { useState } from "react";
import { DataGrid, type Column } from "../components/DataGrid";
import { Badge, Button, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { money, shortDate } from "../lib/format";
import { useDefaultOrg } from "../lib/recordData";
import type { InventoryBatch, Paginated } from "../lib/types";
import { StatusChip } from "../components/Status";

/** Anything inside this window is close enough to plan around. */
const HORIZON_DAYS = 90;

function daysLeft(expiry: string): number {
  return Math.floor((new Date(expiry).getTime() - Date.now()) / 86_400_000);
}

export function ExpiryPage() {
  const { orgId } = useDefaultOrg();
  const [horizon, setHorizon] = useState(HORIZON_DAYS);

  const batches = useQuery({
    queryKey: ["expiry-batches", orgId],
    enabled: orgId != null,
    queryFn: () =>
      api<Paginated<InventoryBatch>>(
        `/api/inventory/batches/?organization=${orgId}&page_size=1000`,
      ),
  });

  const all = (batches.data?.results ?? []).filter((b) => b.quantity_available > 0);
  const rows = all
    .filter((b) => daysLeft(b.expiry_date) <= horizon)
    .sort((a, b) => (a.expiry_date < b.expiry_date ? -1 : 1));

  const expired = rows.filter((b) => daysLeft(b.expiry_date) < 0);
  const units = rows.reduce((s, b) => s + b.quantity_available, 0);
  const value = rows.reduce((s, b) => s + Number(b.wholesale_cost ?? 0) * b.quantity_available, 0);

  const columns: Column<InventoryBatch>[] = [
    {
      key: "product_name",
      header: "Medicine",
      value: (b) => b.product_name ?? "",
      render: (b) => <span className="font-medium text-ink-900">{b.product_name}</span>,
    },
    {
      key: "batch_number",
      header: "Batch",
      value: (b) => b.batch_number,
      render: (b) => <span className="font-mono text-xs text-ink-700">{b.batch_number}</span>,
    },
    {
      key: "quantity_available",
      header: "Units",
      align: "right",
      numeric: true,
      value: (b) => b.quantity_available,
      render: (b) => <span className="tabular-nums">{b.quantity_available.toLocaleString()}</span>,
    },
    {
      key: "value",
      header: "Value at cost",
      align: "right",
      numeric: true,
      value: (b) => Number(b.wholesale_cost ?? 0) * b.quantity_available,
      render: (b) => money(Number(b.wholesale_cost ?? 0) * b.quantity_available),
    },
    {
      key: "expiry_date",
      header: "Expires",
      value: (b) => b.expiry_date,
      render: (b) => shortDate(b.expiry_date),
    },
    {
      key: "days",
      header: "Days left",
      align: "right",
      numeric: true,
      value: (b) => daysLeft(b.expiry_date),
      render: (b) => {
        const d = daysLeft(b.expiry_date);
        if (d < 0) return <Badge tone="danger">expired</Badge>;
        if (d <= 30) return <Badge tone="danger">{d}d</Badge>;
        if (d <= 60) return <Badge tone="warning">{d}d</Badge>;
        return <span className="tabular-nums text-ink-600">{d}d</span>;
      },
    },
    {
      key: "status",
      header: "Status",
      value: (b) => b.status,
      render: (b) => <StatusChip status={b.status} />,
    },
  ];

  return (
    <div className="space-y-4">
      <PageHeader
        title="Expiry forecast"
        action={
          <div className="flex items-center gap-2">
            <select
              value={horizon}
              onChange={(e) => setHorizon(Number(e.target.value))}
              className="rounded-md border border-line bg-surface-0 px-2 py-1.5 text-sm"
            >
              <option value={30}>Next 30 days</option>
              <option value={60}>Next 60 days</option>
              <option value={90}>Next 90 days</option>
              <option value={180}>Next 180 days</option>
            </select>
            <Button variant="secondary" onClick={() => batches.refetch()}>
              <RefreshCw className="h-4 w-4" /> Refresh
            </Button>
          </div>
        }
      />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Tile label={`Batches within ${horizon} days`} value={rows.length} />
        <Tile label="Units at risk" value={units.toLocaleString()} />
        <Tile label="Value at cost" value={money(value)} tone={value > 0 ? "warning" : undefined} />
        <Tile
          label="Already expired"
          value={expired.length}
          tone={expired.length ? "danger" : undefined}
          hint={expired.length ? "still on the shelf" : "nothing expired"}
        />
      </div>

      {expired.length > 0 && (
        <div className="flex items-start gap-2 rounded-lg border border-danger-200 bg-danger-50 p-3">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-danger-600" />
          <div className="text-sm text-danger-900">
            <span className="font-semibold">
              {expired.length} batch(es) have already expired and still hold stock.
            </span>{" "}
            They are unsellable in fact. Raise a disposal so they leave the books and the loss
            lands, rather than sitting as inventory that cannot be sold.
          </div>
        </div>
      )}

      <DataGrid
        rows={rows}
        columns={columns}
        getRowId={(b) => b.id}
        loading={batches.isLoading}
        storageKey="expiry-forecast"
        exportName="expiry-forecast"
        searchPlaceholder="Search by medicine or batch…"
        emptyMessage={`Nothing expires within ${horizon} days.`}
      />
    </div>
  );
}

function Tile({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string | number;
  hint?: string;
  tone?: "danger" | "warning";
}) {
  const colour =
    tone === "danger"
      ? "text-danger-700"
      : tone === "warning"
        ? "text-warning-700"
        : "text-ink-900";
  return (
    <div className="rounded-lg border border-line bg-surface-0 p-3">
      <div className="text-xs text-ink-500">{label}</div>
      <div className={`mt-0.5 text-xl font-semibold tabular-nums ${colour}`}>{value}</div>
      {hint && <div className="mt-0.5 text-xs text-ink-500">{hint}</div>}
    </div>
  );
}
