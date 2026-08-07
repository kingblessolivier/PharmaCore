import { useQuery } from "@tanstack/react-query";
import { ArrowDownLeft, ArrowUpRight } from "lucide-react";
import { useState } from "react";
import { BarChart, ChartFrame, VizRoot } from "../components/Charts";
import { DataGrid } from "../components/DataGrid";
import { Button, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { money } from "../lib/format";
import type { AgingPartner, AgingReport, AgingSide } from "../lib/types";

type Which = "receivables" | "payables";

const BUCKETS: [keyof Omit<AgingPartner, "partner" | "total">, string][] = [
  ["current", "Current"],
  ["d30", "1–30 days"],
  ["d60", "31–60"],
  ["d90", "61–90"],
  ["over90", "90+"],
];

/** Everything past `current`. This is the number that matters: an aging report's
 * job is to separate what is merely outstanding from what is actually late. */
function overdueTotal(row: AgingPartner): number {
  return row.d30 + row.d60 + row.d90 + row.over90;
}

function BucketBar({ side }: { side: AgingSide }) {
  const total = side.total || 1;
  const segments: [string, number, string][] = [
    ["Current", side.buckets.current, "bg-success-500"],
    ["1–30", side.buckets.d30, "bg-brand-500"],
    ["31–60", side.buckets.d60, "bg-warning-400"],
    ["61–90", side.buckets.d90, "bg-warning-600"],
    ["90+", side.buckets.over90, "bg-danger-500"],
  ];
  return (
    <div>
      {/* 2px surface gaps rather than strokes, so adjacent segments stay legible
          without a border darkening every boundary. */}
      <div className="flex h-2 gap-[2px] overflow-hidden rounded-full">
        {segments.map(([label, value, colour]) =>
          value > 0 ? (
            <div
              key={label}
              className={colour}
              style={{ width: `${(value / total) * 100}%` }}
              title={`${label}: ${money(value)}`}
            />
          ) : null,
        )}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-600">
        {segments.map(([label, value, colour]) => (
          <span key={label} className="flex items-center gap-1.5">
            <span className={`h-2 w-2 rounded-full ${colour}`} aria-hidden />
            {label} <span className="tabular-nums text-ink-900">{money(value)}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

export function FinancePage() {
  const [which, setWhich] = useState<Which>("receivables");

  const { data, isLoading } = useQuery({
    queryKey: ["aging"],
    queryFn: () => api<AgingReport>("/api/distribution/aging/"),
  });

  const side = data?.[which];
  const rows = side?.by_partner ?? [];

  return (
    <div className="space-y-4">
      <PageHeader
        title="Aging"
        action={
          <div className="flex gap-1 rounded-lg border border-line bg-surface-0 p-0.5">
            {(["receivables", "payables"] as const).map((option) => (
              <Button
                key={option}
                variant={which === option ? "primary" : "ghost"}
                onClick={() => setWhich(option)}
              >
                {option === "receivables" ? (
                  <ArrowDownLeft className="h-4 w-4" />
                ) : (
                  <ArrowUpRight className="h-4 w-4" />
                )}
                {option === "receivables" ? "Owed to us" : "We owe"}
              </Button>
            ))}
          </div>
        }
      />
      <p className="-mt-2 max-w-3xl text-sm text-ink-500">
        How old the debt is, not just how much. Money in the 90+ bucket is materially less
        likely to arrive than money in the current one, and it is the same number on a balance
        sheet.
      </p>

      {side && (
        <div className="rounded-lg border border-line bg-surface-0 px-4 py-3">
          <div className="mb-2 flex items-baseline justify-between">
            <span className="text-sm font-semibold text-ink-900">
              {which === "receivables" ? "Receivables" : "Payables"}
            </span>
            <span className="tabular-nums text-lg font-semibold text-ink-900">
              {money(side.total)}
            </span>
          </div>
          <BucketBar side={side} />
        </div>
      )}

      {rows.length > 0 && (
        <VizRoot>
          <ChartFrame
            title={which === "receivables" ? "Who owes the most" : "Who we owe the most"}
            subtitle="Ranked by overdue, not by total — a large current balance is not a problem."
          >
            <BarChart
              data={[...rows]
                .sort((a, b) => overdueTotal(b) - overdueTotal(a))
                .slice(0, 8)
                .map((r) => ({
                  label: r.partner.slice(0, 28),
                  value: overdueTotal(r),
                  note: `${money(r.total)} outstanding · ${money(r.over90)} past 90 days`,
                  tone: r.over90 > 0 ? ("critical" as const) : ("warning" as const),
                }))}
              valueFormat={money}
            />
          </ChartFrame>
        </VizRoot>
      )}

      <DataGrid
        rows={rows}
        loading={isLoading}
        getRowId={(r) => r.partner}
        storageKey={`finance.aging.${which}`}
        exportName={`aging-${which}`}
        searchPlaceholder="Search partners…"
        emptyMessage={
          which === "receivables" ? "Nobody owes anything." : "Nothing outstanding to suppliers."
        }
        columns={[
          { key: "partner", header: "Partner", value: (r) => r.partner },
          ...BUCKETS.map(([key, header]) => ({
            key,
            header,
            numeric: true,
            align: "right" as const,
            value: (r: AgingPartner) => r[key],
            render: (r: AgingPartner) => money(r[key]),
          })),
          {
            key: "overdue",
            header: "Overdue",
            numeric: true,
            align: "right",
            value: (r) => overdueTotal(r),
            render: (r) => (
              <span className={overdueTotal(r) > 0 ? "text-danger-700" : "text-ink-500"}>
                {money(overdueTotal(r))}
              </span>
            ),
          },
          {
            key: "total",
            header: "Total",
            numeric: true,
            align: "right",
            value: (r) => r.total,
            render: (r) => <span className="font-semibold">{money(r.total)}</span>,
          },
        ]}
      />
    </div>
  );
}
