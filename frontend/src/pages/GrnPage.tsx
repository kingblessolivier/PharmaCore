/* -------------------------------------------------------------------------- */
/* Goods received notes — the stock write-event, and the record of what was    */
/* wrong with it.                                                              */
/*                                                                             */
/* A GRN's whole reason to exist is the discrepancy: what the depot said it     */
/* sent versus what the pharmacy actually counted. The register used to show a  */
/* yes/no flag and no way to reach the lines, which is the one thing a manager  */
/* opens this screen to see. (It also pointed at a route that did not exist,    */
/* so it had never displayed anything at all.)                                  */
/* -------------------------------------------------------------------------- */

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { useState } from "react";
import { DataGrid, type Column } from "../components/DataGrid";
import { Drawer, Empty, Facts, Section } from "../components/RecordKit";
import { Badge, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { dateTime, shortDate } from "../lib/format";
import type { GoodsReceivedNote, Paginated } from "../lib/types";
import { StatusChip } from "../components/Status";

export function GrnPage() {
  const [open, setOpen] = useState<GoodsReceivedNote | null>(null);

  const grns = useQuery({
    queryKey: ["grn-list"],
    queryFn: () => api<Paginated<GoodsReceivedNote>>("/api/distribution/grns/?page_size=300"),
  });

  const rows = grns.data?.results ?? [];
  const withDiscrepancy = rows.filter((g) => g.has_discrepancy);

  /** Units short or damaged across a note — the number worth chasing a depot over. */
  function shortfall(g: GoodsReceivedNote): number {
    return (g.lines ?? []).reduce(
      (s, l) => s + Math.max(0, l.quantity_expected - l.quantity_received) + l.quantity_damaged,
      0,
    );
  }

  const columns: Column<GoodsReceivedNote>[] = [
    {
      key: "grn_number",
      header: "GRN",
      value: (g) => g.grn_number,
      render: (g) => <span className="font-medium text-ink-900">{g.grn_number}</span>,
    },
    { key: "order_number", header: "Against order", value: (g) => g.order_number },
    {
      key: "lines",
      header: "Lines",
      align: "right",
      numeric: true,
      value: (g) => (g.lines ?? []).length,
    },
    {
      key: "received",
      header: "Units received",
      align: "right",
      numeric: true,
      value: (g) => (g.lines ?? []).reduce((s, l) => s + l.quantity_received, 0),
      render: (g) => (
        <span className="tabular-nums">
          {(g.lines ?? []).reduce((s, l) => s + l.quantity_received, 0).toLocaleString()}
        </span>
      ),
    },
    {
      key: "shortfall",
      header: "Short / damaged",
      align: "right",
      numeric: true,
      value: (g) => shortfall(g),
      render: (g) => {
        const n = shortfall(g);
        return n > 0 ? (
          <span className="font-medium tabular-nums text-danger-700">{n.toLocaleString()}</span>
        ) : (
          <span className="text-ink-400">—</span>
        );
      },
    },
    {
      key: "status",
      header: "Status",
      value: (g) => g.status,
      render: (g) => <StatusChip status={g.status} size="sm" />,
    },
    {
      key: "has_discrepancy",
      header: "Matched",
      value: (g) => (g.has_discrepancy ? "Discrepancy" : "Clean"),
      render: (g) =>
        g.has_discrepancy ? (
          <span className="inline-flex items-center gap-1 text-sm text-danger-700">
            <AlertTriangle className="h-3.5 w-3.5" /> Discrepancy
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 text-sm text-success-700">
            <CheckCircle2 className="h-3.5 w-3.5" /> Clean
          </span>
        ),
    },
    {
      key: "received_at",
      header: "Received",
      value: (g) => g.received_at,
      render: (g) => shortDate(g.received_at),
    },
  ];

  return (
    <div className="space-y-4">
      <PageHeader title="Goods received notes" />

      {rows.length > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <Tile label="Notes on file" value={rows.length} />
          <Tile
            label="With a discrepancy"
            value={withDiscrepancy.length}
            tone={withDiscrepancy.length ? "danger" : undefined}
            hint={
              withDiscrepancy.length
                ? "short, over or damaged on arrival"
                : "every delivery matched its manifest"
            }
          />
          <Tile
            label="Units short or damaged"
            value={rows.reduce((s, g) => s + shortfall(g), 0).toLocaleString()}
            tone={rows.some((g) => shortfall(g) > 0) ? "danger" : undefined}
            hint="claimable against the sending depot"
          />
        </div>
      )}

      <DataGrid
        rows={rows}
        columns={columns}
        getRowId={(g) => g.id}
        loading={grns.isLoading}
        storageKey="grn"
        exportName="goods-received-notes"
        searchPlaceholder="Search by GRN number or order…"
        emptyMessage="No goods received notes yet."
        onRowClick={(g) => setOpen(g)}
      />

      {open && (
        <Drawer
          title={open.grn_number}
          subtitle={`Received against ${open.order_number}`}
          badge={
            open.has_discrepancy ? (
              <Badge tone="danger">Discrepancy</Badge>
            ) : (
              <Badge tone="success">Clean</Badge>
            )
          }
          onClose={() => setOpen(null)}
        >
          <Section title="Reception">
            <Facts
              rows={[
                ["GRN", open.grn_number],
                ["Order", open.order_number],
                ["Status", open.status === "FINALIZED" ? "Finalised" : "Draft"],
                ["Received", dateTime(open.received_at)],
                ["Lines", String((open.lines ?? []).length)],
                ["Short / damaged", shortfall(open).toLocaleString()],
              ]}
            />
          </Section>

          <Section
            title="What was counted"
            hint="Expected is what the depot's manifest said it dispatched. Received is what the pharmacy actually counted onto its shelf."
          >
            {(open.lines ?? []).length === 0 ? (
              <Empty message="This note carries no lines." />
            ) : (
              <div className="overflow-x-auto rounded-lg border border-line">
                <table className="w-full text-sm">
                  <thead className="border-b border-line bg-surface-100 text-left text-xs uppercase tracking-wide text-ink-500">
                    <tr>
                      <th className="px-3 py-2">Medicine</th>
                      <th className="px-3 py-2">Batch</th>
                      <th className="px-3 py-2">Expiry</th>
                      <th className="px-3 py-2 text-right">Expected</th>
                      <th className="px-3 py-2 text-right">Received</th>
                      <th className="px-3 py-2 text-right">Damaged</th>
                      <th className="px-3 py-2 text-right">Variance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(open.lines ?? []).map((l) => {
                      const variance = l.quantity_received - l.quantity_expected;
                      return (
                        <tr key={l.id} className="border-b border-line last:border-0">
                          <td className="px-3 py-2 text-ink-900">{l.product_name}</td>
                          <td className="px-3 py-2 font-mono text-xs text-ink-700">
                            {l.batch_number}
                          </td>
                          <td className="px-3 py-2 text-ink-600">{shortDate(l.expiry_date)}</td>
                          <td className="px-3 py-2 text-right tabular-nums">
                            {l.quantity_expected.toLocaleString()}
                          </td>
                          <td className="px-3 py-2 text-right tabular-nums">
                            {l.quantity_received.toLocaleString()}
                          </td>
                          <td className="px-3 py-2 text-right tabular-nums">
                            {l.quantity_damaged > 0 ? (
                              <span className="text-danger-700">{l.quantity_damaged}</span>
                            ) : (
                              <span className="text-ink-400">—</span>
                            )}
                          </td>
                          <td className="px-3 py-2 text-right tabular-nums">
                            {variance === 0 ? (
                              <span className="text-ink-400">—</span>
                            ) : (
                              <span
                                className={variance < 0 ? "text-danger-700" : "text-warning-700"}
                              >
                                {variance > 0 ? `+${variance}` : variance}
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Section>

          {open.has_discrepancy && (
            <Section title="Why this matters">
              <p className="text-sm text-ink-600">
                Only what was <span className="font-medium text-ink-900">received</span> was landed
                into stock — the shortfall was never added, so on-hand is correct. What is
                outstanding is commercial: the sending depot invoiced for the manifest, and this
                note is the evidence for a credit.
              </p>
            </Section>
          )}
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
  tone?: "danger";
}) {
  return (
    <div className="rounded-lg border border-line bg-surface-0 p-3">
      <div className="text-xs text-ink-500">{label}</div>
      <div
        className={`mt-0.5 text-xl font-semibold tabular-nums ${
          tone === "danger" ? "text-danger-700" : "text-ink-900"
        }`}
      >
        {value}
      </div>
      {hint && <div className="mt-0.5 text-xs text-ink-500">{hint}</div>}
    </div>
  );
}
