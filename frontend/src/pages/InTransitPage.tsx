/* -------------------------------------------------------------------------- */
/* In-transit stock — the units that belong to nobody's shelf right now.       */
/*                                                                             */
/* Dispatch takes stock out of the depot's on-hand and parks it here; receiving */
/* clears it into the pharmacy's. The whole point of the ledger is that no unit */
/* is ever counted twice or vanishes in between — so the question this screen   */
/* must answer is not "what is moving" but "what left and never arrived".      */
/* A flat list of batches cannot answer that; it needs age on the road.        */
/* -------------------------------------------------------------------------- */

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Truck } from "lucide-react";
import { useState } from "react";
import { DataGrid, type Column } from "../components/DataGrid";
import { Drawer, Facts, Section } from "../components/RecordKit";
import { Badge, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { dateTime, shortDate } from "../lib/format";
import type { InTransitStock, Paginated } from "../lib/types";

/** Beyond this, a consignment has been on the road long enough to chase. */
const STALE_DAYS = 3;

function daysOnRoad(dispatchedAt: string): number {
  const ms = Date.now() - new Date(dispatchedAt).getTime();
  return Math.max(0, Math.floor(ms / 86_400_000));
}

function daysToExpiry(expiry: string): number {
  const ms = new Date(expiry).getTime() - Date.now();
  return Math.floor(ms / 86_400_000);
}

export function InTransitPage() {
  const [open, setOpen] = useState<InTransitStock | null>(null);

  const inTransit = useQuery({
    queryKey: ["in-transit-list"],
    queryFn: () =>
      api<Paginated<InTransitStock>>("/api/distribution/in-transit/?page_size=500"),
  });

  const rows = inTransit.data?.results ?? [];
  const stale = rows.filter((t) => daysOnRoad(t.dispatched_at) >= STALE_DAYS);
  const units = rows.reduce((s, t) => s + t.quantity, 0);
  const consignments = new Set(rows.map((t) => t.order)).size;
  const expiringOnRoad = rows.filter((t) => daysToExpiry(t.expiry_date) <= 90);

  const columns: Column<InTransitStock>[] = [
    {
      key: "product_name",
      header: "Medicine",
      value: (t) => t.product_name,
      render: (t) => <span className="font-medium text-ink-900">{t.product_name}</span>,
    },
    {
      key: "batch_number",
      header: "Batch",
      value: (t) => t.batch_number,
      render: (t) => <span className="font-mono text-xs text-ink-700">{t.batch_number}</span>,
    },
    { key: "order_number", header: "Order", value: (t) => t.order_number },
    { key: "source_name", header: "From", value: (t) => t.source_name },
    { key: "destination_name", header: "To", value: (t) => t.destination_name },
    {
      key: "quantity",
      header: "Units",
      align: "right",
      numeric: true,
      value: (t) => t.quantity,
      render: (t) => <span className="tabular-nums">{t.quantity.toLocaleString()}</span>,
    },
    {
      key: "age",
      header: "On the road",
      align: "right",
      numeric: true,
      value: (t) => daysOnRoad(t.dispatched_at),
      render: (t) => {
        const d = daysOnRoad(t.dispatched_at);
        if (d >= STALE_DAYS)
          return <Badge tone="danger">{d} day{d === 1 ? "" : "s"}</Badge>;
        return <span className="tabular-nums text-ink-600">{d === 0 ? "today" : `${d}d`}</span>;
      },
    },
    {
      key: "expiry_date",
      header: "Expires",
      value: (t) => t.expiry_date,
      render: (t) => {
        const d = daysToExpiry(t.expiry_date);
        return (
          <span className={d <= 90 ? "text-warning-700" : "text-ink-600"}>
            {shortDate(t.expiry_date)}
          </span>
        );
      },
    },
  ];

  return (
    <div className="space-y-4">
      <PageHeader title="In-transit stock" />
      <p className="-mt-2 max-w-3xl text-sm text-ink-500">
        Units that have left the depot but have not yet been received. They belong to no one's
        on-hand until a GRN lands them, which is what stops a unit being counted twice — or
        disappearing between the two.
      </p>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Tile label="Consignments moving" value={consignments} />
        <Tile label="Units on the road" value={units.toLocaleString()} />
        <Tile
          label={`Older than ${STALE_DAYS} days`}
          value={stale.length}
          tone={stale.length ? "danger" : undefined}
          hint={stale.length ? "not received — chase these" : "nothing overdue"}
        />
        <Tile
          label="Expiring within 90 days"
          value={expiringOnRoad.length}
          tone={expiringOnRoad.length ? "warning" : undefined}
          hint={expiringOnRoad.length ? "short-dated stock in motion" : "none short-dated"}
        />
      </div>

      {stale.length > 0 && (
        <div className="flex items-start gap-2 rounded-lg border border-danger-200 bg-danger-50 p-3">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-danger-600" />
          <div className="text-sm text-danger-900">
            <span className="font-semibold">
              {stale.length} line{stale.length === 1 ? "" : "s"} dispatched more than {STALE_DAYS}{" "}
              days ago and still not received.
            </span>{" "}
            Stock sitting in this ledger is stock nobody can sell — it is off the depot's shelf and
            not yet on the pharmacy's. Either the delivery has not arrived or the GRN was never
            raised.
          </div>
        </div>
      )}

      <DataGrid
        rows={rows}
        columns={columns}
        getRowId={(t) => t.id}
        loading={inTransit.isLoading}
        storageKey="in-transit"
        exportName="in-transit-stock"
        searchPlaceholder="Search by medicine, batch, order, depot or branch…"
        emptyMessage="Nothing is in transit — every dispatched unit has been received."
        onRowClick={(t) => setOpen(t)}
      />

      {open && (
        <Drawer
          title={`${open.product_name} · ${open.batch_number}`}
          subtitle={`${open.source_name} → ${open.destination_name}`}
          onClose={() => setOpen(null)}
        >
          <Section title="This consignment line">
            <Facts
              rows={[
                ["Order", open.order_number],
                ["Units", open.quantity.toLocaleString()],
                ["Batch", open.batch_number],
                ["Expiry", shortDate(open.expiry_date)],
                ["Dispatched", dateTime(open.dispatched_at)],
                ["On the road", `${daysOnRoad(open.dispatched_at)} day(s)`],
              ]}
            />
          </Section>
          <Section
            title="What happens next"
            hint="These units clear from this ledger the moment the receiving pharmacy finalises its goods received note."
          >
            <div className="flex items-start gap-2 text-sm text-ink-600">
              <Truck className="mt-0.5 h-4 w-4 shrink-0 text-ink-400" />
              <span>
                Held against <span className="font-medium text-ink-900">{open.destination_name}</span>
                . Until the GRN is finalised these units are on neither party's on-hand, which is
                deliberate — it is the only way the two counts can never disagree.
              </span>
            </div>
          </Section>
        </Drawer>
      )}
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
    tone === "danger" ? "text-danger-700" : tone === "warning" ? "text-warning-700" : "text-ink-900";
  return (
    <div className="rounded-lg border border-line bg-surface-0 p-3">
      <div className="text-xs text-ink-500">{label}</div>
      <div className={`mt-0.5 text-xl font-semibold tabular-nums ${colour}`}>{value}</div>
      {hint && <div className="mt-0.5 text-xs text-ink-500">{hint}</div>}
    </div>
  );
}
