/* -------------------------------------------------------------------------- */
/* Physical counts — reconciling the books against the shelf.                  */
/*                                                                             */
/* Approving a count is irreversible and does two things at once: it moves      */
/* stock and it posts to the ledger. So the variance has to be visible *before* */
/* anyone commits it, not summarised afterwards. Two rules the API enforces and */
/* this screen explains: a count posts exactly once, and the person who counted  */
/* cannot approve their own work.                                               */
/* -------------------------------------------------------------------------- */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ClipboardCheck } from "lucide-react";
import { useState } from "react";
import { DataGrid, type Column } from "../components/DataGrid";
import { Drawer, Empty, ErrorNote, Facts, Section } from "../components/RecordKit";
import { Badge, Button, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { money, shortDate } from "../lib/format";
import { approveCount, varianceReport } from "../lib/inventory";
import type { Paginated, StockCount } from "../lib/types";
import { StatusChip } from "../components/Status";

export function StockCountsPage() {
  const qc = useQueryClient();
  const [open, setOpen] = useState<StockCount | null>(null);

  const counts = useQuery({
    queryKey: ["stock-counts"],
    queryFn: () => api<Paginated<StockCount>>("/api/inventory/stock-counts/?page_size=200"),
  });

  const variance = useQuery({
    queryKey: ["count-variance", open?.id],
    enabled: open != null,
    queryFn: () => varianceReport(open!.id),
  });

  const approve = useMutation({
    mutationFn: (id: number) => approveCount(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["stock-counts"] });
      void qc.invalidateQueries({ queryKey: ["count-variance"] });
    },
  });

  const rows = counts.data?.results ?? [];
  const awaiting = rows.filter((c) => c.status === "SUBMITTED");

  const columns: Column<StockCount>[] = [
    {
      key: "reference_no",
      header: "Reference",
      value: (c) => c.reference_no,
      render: (c) => <span className="font-medium text-ink-900">{c.reference_no}</span>,
    },
    {
      key: "count_type",
      header: "Type",
      value: (c) => c.count_type,
      render: (c) => (
        <span className="text-ink-600">
          {c.count_type === "CYCLE_COUNT"
            ? "Cycle count"
            : c.count_type === "FULL_PHYSICAL"
              ? "Full physical"
              : "Spot check"}
        </span>
      ),
    },
    {
      key: "lines",
      header: "Lines",
      align: "right",
      numeric: true,
      value: (c) => (c.items ?? []).length,
    },
    {
      key: "variance_lines",
      header: "With variance",
      align: "right",
      numeric: true,
      value: (c) => (c.items ?? []).filter((i) => i.variance_qty !== 0).length,
      render: (c) => {
        const n = (c.items ?? []).filter((i) => i.variance_qty !== 0).length;
        return n > 0 ? (
          <span className="font-medium tabular-nums text-warning-700">{n}</span>
        ) : (
          <span className="text-ink-400">—</span>
        );
      },
    },
    { key: "counter_username", header: "Counted by", value: (c) => c.counter_username },
    {
      key: "approver_username",
      header: "Approved by",
      value: (c) => c.approver_username ?? "",
      render: (c) => c.approver_username ?? <span className="text-ink-400">—</span>,
    },
    {
      key: "status",
      header: "Status",
      value: (c) => c.status,
      render: (c) => <StatusChip status={c.status} size="sm" />,
    },
    {
      key: "started_at",
      header: "Started",
      value: (c) => c.started_at,
      render: (c) => shortDate(c.started_at),
    },
  ];

  return (
    <div className="space-y-4">
      <PageHeader title="Physical counts" />

      {awaiting.length > 0 && (
        <div className="flex items-start gap-2 rounded-lg border border-warning-200 bg-warning-50 p-3">
          <ClipboardCheck className="mt-0.5 h-4 w-4 shrink-0 text-warning-600" />
          <div className="text-sm text-warning-900">
            <span className="font-semibold">
              {awaiting.length} count{awaiting.length === 1 ? "" : "s"} awaiting approval.
            </span>{" "}
            Until they are approved, the books still show the old figures.
          </div>
        </div>
      )}

      <DataGrid
        rows={rows}
        columns={columns}
        getRowId={(c) => c.id}
        loading={counts.isLoading}
        storageKey="stock-counts"
        exportName="stock-counts"
        searchPlaceholder="Search by reference or counter…"
        emptyMessage="No stock counts recorded."
        onRowClick={(c) => setOpen(c)}
      />

      {open && (
        <Drawer
          title={open.reference_no}
          subtitle={`Counted by ${open.counter_username}`}
          badge={
            open.status === "APPROVED" ? (
              <Badge tone="success">Approved</Badge>
            ) : (
              <Badge tone="warning">{open.status}</Badge>
            )
          }
          onClose={() => setOpen(null)}
          footer={
            open.status !== "APPROVED" && (
              <div className="flex justify-end gap-2">
                <Button onClick={() => approve.mutate(open.id)} disabled={approve.isPending}>
                  {approve.isPending ? "Posting…" : "Approve and post variance"}
                </Button>
              </div>
            )
          }
        >
          <Section title="The count">
            <Facts
              rows={[
                ["Reference", open.reference_no],
                ["Type", open.count_type],
                ["Counted by", open.counter_username],
                ["Approved by", open.approver_username ?? "—"],
                ["Started", shortDate(open.started_at)],
                ["Completed", open.completed_at ? shortDate(open.completed_at) : "—"],
              ]}
            />
          </Section>

          {variance.data && (
            <>
              <Section
                title={open.status === "APPROVED" ? "What was posted" : "What approving would post"}
              >
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <Mini label="Lines" value={String(variance.data.lines)} />
                  <Mini
                    label="With variance"
                    value={String(variance.data.lines_with_variance)}
                    tone={variance.data.lines_with_variance ? "warning" : undefined}
                  />
                  <Mini
                    label="Accuracy"
                    value={`${variance.data.accuracy_pct}%`}
                    tone={variance.data.accuracy_pct < 95 ? "warning" : undefined}
                  />
                  <Mini
                    label="Net value"
                    value={money(variance.data.net_value)}
                    tone={Number(variance.data.net_value) < 0 ? "danger" : undefined}
                  />
                </div>
                {Number(variance.data.net_value) < 0 && (
                  <p className="mt-2 flex items-start gap-1.5 text-sm text-danger-700">
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                    <span>
                      A net loss of {money(Math.abs(Number(variance.data.net_value)))} will be
                      written off to the P&amp;L as shrinkage.
                    </span>
                  </p>
                )}
              </Section>

              <Section title="Line by line" hint="Largest variance first.">
                {variance.data.rows.length === 0 ? (
                  <Empty message="This count has no lines." />
                ) : (
                  <div className="overflow-x-auto rounded-lg border border-line">
                    <table className="w-full text-sm">
                      <thead className="border-b border-line bg-surface-100 text-left text-xs uppercase tracking-wide text-ink-500">
                        <tr>
                          <th className="px-3 py-2">Medicine</th>
                          <th className="px-3 py-2">Batch</th>
                          <th className="px-3 py-2 text-right">System</th>
                          <th className="px-3 py-2 text-right">Counted</th>
                          <th className="px-3 py-2 text-right">Variance</th>
                          <th className="px-3 py-2 text-right">Value</th>
                        </tr>
                      </thead>
                      <tbody>
                        {variance.data.rows.map((r) => (
                          <tr key={r.item} className="border-b border-line last:border-0">
                            <td className="px-3 py-2 text-ink-900">{r.product_name}</td>
                            <td className="px-3 py-2 font-mono text-xs text-ink-700">
                              {r.batch_number}
                            </td>
                            <td className="px-3 py-2 text-right tabular-nums">{r.system_qty}</td>
                            <td className="px-3 py-2 text-right tabular-nums">{r.counted_qty}</td>
                            <td className="px-3 py-2 text-right tabular-nums">
                              {r.variance_qty === 0 ? (
                                <span className="text-ink-400">—</span>
                              ) : (
                                <span
                                  className={
                                    r.variance_qty < 0 ? "text-danger-700" : "text-success-700"
                                  }
                                >
                                  {r.variance_qty > 0 ? `+${r.variance_qty}` : r.variance_qty}
                                </span>
                              )}
                            </td>
                            <td className="px-3 py-2 text-right tabular-nums text-ink-600">
                              {money(r.variance_value)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Section>
            </>
          )}

          {open.status !== "APPROVED" && (
            <Section title="Before you approve">
              <p className="text-sm text-ink-600">
                This posts once and cannot be repeated — a second attempt is refused rather than
                doubling the adjustment. You also cannot approve a count you performed yourself.
              </p>
            </Section>
          )}

          {approve.isError && <ErrorNote error={approve.error} />}
        </Drawer>
      )}
    </div>
  );
}

function Mini({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
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
      <div className={`mt-0.5 text-lg font-semibold tabular-nums ${colour}`}>{value}</div>
    </div>
  );
}
