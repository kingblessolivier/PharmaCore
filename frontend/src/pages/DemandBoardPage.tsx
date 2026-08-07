/* -------------------------------------------------------------------------- */
/* What your customers asked for and you could not supply.                     */
/*                                                                             */
/* This is the demand signal a wholesaler imports against. Quantity alone       */
/* ranks it badly — one pharmacy wanting 500 is a different problem from twenty */
/* wanting 25 each — so buyer count and age are carried next to it, and the     */
/* selection you make here becomes a purchase requisition in Procurement.      */
/* -------------------------------------------------------------------------- */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Ship, Users } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { DataGrid, type Column } from "../components/DataGrid";
import { Drawer, Empty, ErrorNote, Facts, Field, Grid, Input, Section } from "../components/RecordKit";
import { Badge, Button, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import {
  BACKORDER_STATUS_LABEL,
  demandBoard,
  ORIGIN_LABEL,
  sourceDemand,
  type Backorder,
  type DemandRow,
} from "../lib/distribution";
import { shortDate } from "../lib/format";
import { useDefaultOrg } from "../lib/recordData";
import type { Paginated } from "../lib/types";

export function DemandBoardPage() {
  const { orgId } = useDefaultOrg();
  const qc = useQueryClient();
  const navigate = useNavigate();

  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [sourcing, setSourcing] = useState(false);
  const [neededBy, setNeededBy] = useState("");
  const [justification, setJustification] = useState("");
  const [raised, setRaised] = useState<{ number: string; id: number; lines: number } | null>(null);

  const board = useQuery({
    queryKey: ["demand-board", orgId],
    enabled: orgId != null,
    queryFn: () => demandBoard(orgId as number),
  });

  const lines = useQuery({
    queryKey: ["backorders", orgId],
    enabled: orgId != null,
    queryFn: () =>
      api<Paginated<Backorder>>(`/api/distribution/backorders/?depot=${orgId ?? 0}&page_size=200`),
  });

  const raise = useMutation({
    mutationFn: () =>
      sourceDemand({
        depot: orgId as number,
        products: selected.size > 0 ? [...selected] : undefined,
        needed_by: neededBy || undefined,
        justification,
      }),
    onSuccess: (r) => {
      setRaised({ number: r.requisition_number, id: r.requisition, lines: r.lines.length });
      setSourcing(false);
      setSelected(new Set());
      void qc.invalidateQueries({ queryKey: ["demand-board"] });
      void qc.invalidateQueries({ queryKey: ["backorders"] });
    },
  });

  const summary = board.data?.summary;
  const rows = useMemo(() => board.data?.rows ?? [], [board.data]);

  /* Selecting nothing means "source everything", so the total falls back to the
     whole board rather than showing zero. */
  const selectedUnits = useMemo(
    () =>
      selected.size > 0
        ? rows.filter((r) => selected.has(r.product)).reduce((s, r) => s + r.quantity, 0)
        : rows.reduce((s, r) => s + r.quantity, 0),
    [rows, selected],
  );

  const columns: Column<DemandRow>[] = [
    {
      key: "sel",
      header: "",
      fixed: true,
      width: "2.5rem",
      render: (r) => (
        <input
          type="checkbox"
          checked={selected.has(r.product)}
          onChange={(e) => {
            e.stopPropagation();
            setSelected((prev) => {
              const next = new Set(prev);
              if (next.has(r.product)) next.delete(r.product);
              else next.add(r.product);
              return next;
            });
          }}
          onClick={(e) => e.stopPropagation()}
          aria-label={`Select ${r.product_name}`}
        />
      ),
    },
    { key: "product_name", header: "Product", value: (r) => r.product_name },
    {
      key: "quantity",
      header: "Units wanted",
      numeric: true,
      align: "right",
      value: (r) => r.quantity,
    },
    {
      key: "buyers",
      header: "Pharmacies",
      numeric: true,
      align: "right",
      value: (r) => r.buyers,
      render: (r) => (
        <span className="inline-flex items-center gap-1 tabular-nums">
          <Users className="h-3 w-3 text-ink-400" />
          {r.buyers}
        </span>
      ),
    },
    {
      key: "age_days",
      header: "Waiting",
      numeric: true,
      align: "right",
      value: (r) => r.age_days,
      render: (r) => (
        <span className={r.age_days > 14 ? "text-warning-700" : ""}>
          {r.age_days === 0 ? "today" : `${r.age_days}d`}
        </span>
      ),
    },
    {
      key: "sourcing",
      header: "Status",
      value: (r) => (r.sourcing > 0 ? "Being sourced" : "Awaiting sourcing"),
      render: (r) =>
        r.sourcing > 0 ? (
          <Badge tone="info">{r.sourcing} being sourced</Badge>
        ) : (
          <Badge tone="warning">Not yet sourced</Badge>
        ),
    },
  ];

  const lineColumns: Column<Backorder>[] = [
    { key: "retail_name", header: "Pharmacy", value: (r) => r.retail_name },
    { key: "product_name", header: "Product", value: (r) => r.product_name },
    {
      key: "quantity_outstanding",
      header: "Wanted",
      numeric: true,
      align: "right",
      value: (r) => r.quantity_outstanding,
    },
    {
      key: "origin",
      header: "Why",
      value: (r) => ORIGIN_LABEL[r.origin],
      render: (r) => <span className="text-ink-600">{ORIGIN_LABEL[r.origin]}</span>,
    },
    {
      key: "status",
      header: "Status",
      value: (r) => BACKORDER_STATUS_LABEL[r.status],
      render: (r) => (
        <Badge
          tone={
            r.status === "FULFILLED"
              ? "success"
              : r.status === "SOURCING"
                ? "info"
                : r.status === "CANCELLED"
                  ? "neutral"
                  : "warning"
          }
        >
          {BACKORDER_STATUS_LABEL[r.status]}
        </Badge>
      ),
    },
    { key: "order_number", header: "From order", value: (r) => r.order_number || "—" },
    { key: "created_at", header: "Asked", value: (r) => shortDate(r.created_at) },
  ];

  return (
    <div className="space-y-4">
      <PageHeader
        title="Unmet demand"
        action={
          rows.length > 0 ? (
            <Button onClick={() => setSourcing(true)}>
              <Ship className="h-4 w-4" />
              Source {selected.size > 0 ? `${selected.size} product(s)` : "all of it"}
            </Button>
          ) : undefined
        }
      />
      <p className="-mt-2 max-w-3xl text-sm text-ink-500">
        What retail pharmacies asked for and you could not supply — the basis for your next import.
      </p>

      {raised && (
        <div className="flex items-start gap-2 rounded-lg border border-success-200 bg-success-50 p-3">
          <Ship className="mt-0.5 h-4 w-4 shrink-0 text-success-600" />
          <div className="min-w-0 flex-1 text-sm">
            <div className="font-medium text-success-900">
              Requisition {raised.number} raised with {raised.lines} line(s)
            </div>
            <div className="mt-0.5 text-xs text-success-800">
              It is a draft in Procurement. Submit it there to start the RFQ, quote and import
              flow. The demand it covers is now marked as being sourced.
            </div>
          </div>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => navigate("/procurement/requisitions")}
          >
            Open Procurement
            <ArrowRight className="ml-1 h-3.5 w-3.5" />
          </Button>
        </div>
      )}

      {summary && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Tile label="Products wanted" value={String(summary.products_wanted)} />
          <Tile label="Units wanted" value={summary.units_wanted.toLocaleString()} />
          <Tile label="Pharmacies waiting" value={String(summary.buyers_waiting)} />
          <Tile
            label="Oldest request"
            value={summary.oldest_days === 0 ? "—" : `${summary.oldest_days}d`}
            tone={summary.oldest_days > 14 ? "warn" : undefined}
          />
        </div>
      )}

      {rows.length === 0 && !board.isLoading ? (
        <Empty message="Nothing outstanding Every line your customers have ordered was supplied from stock." />
      ) : (
        <>
          <section className="space-y-2">
            <h2 className="text-sm font-semibold text-ink-900">By product</h2>
            <DataGrid
              rows={rows}
              columns={columns}
              getRowId={(r) => r.product}
              loading={board.isLoading}
              storageKey="demand-board"
              exportName="unmet-demand"
              searchPlaceholder="Search products…"
              emptyMessage="No open demand."
            />
          </section>

          <section className="space-y-2">
            <h2 className="text-sm font-semibold text-ink-900">Every request</h2>
            <DataGrid
              rows={lines.data?.results ?? []}
              columns={lineColumns}
              getRowId={(r) => r.id}
              loading={lines.isLoading}
              storageKey="backorder-lines"
              exportName="backorders"
              searchPlaceholder="Search requests…"
              emptyMessage="No requests on file."
              initialDensity="compact"
            />
          </section>
        </>
      )}

      {sourcing && (
      <Drawer
        onClose={() => setSourcing(false)}
        title="Raise a purchase requisition"
        footer={
          <>
            <Button variant="ghost" onClick={() => setSourcing(false)}>
              Cancel
            </Button>
            <Button onClick={() => raise.mutate()} disabled={raise.isPending}>
              {raise.isPending ? "Raising…" : "Raise requisition"}
            </Button>
          </>
        }
      >
        <Section title="What this will do">
          <Facts
                rows={[
                  ["Products", selected.size > 0 ? `${selected.size} selected` : `all ${rows.length} wanted`],
                  ["Units", selectedUnits.toLocaleString()],
                  ["Raised at", "This depot"],
                ]}
              />
          <p className="mt-2 text-xs text-ink-500">
            A draft requisition is created in Procurement with one line per product, quantities
            consolidated across every pharmacy that asked. The demand is marked as being sourced so
            it cannot be raised twice.
          </p>
        </Section>

        <Section title="Details">
          <Grid>
            <Field label="Needed by" hint="Defaults to 30 days out.">
              <Input type="date" value={neededBy} onChange={(e) => setNeededBy(e.target.value)} />
            </Field>
          </Grid>
          <Field label="Justification">
            <Input
              value={justification}
              onChange={(e) => setJustification(e.target.value)}
              placeholder="Left blank, the requisition explains itself from the demand behind it."
            />
          </Field>
        </Section>

        {raise.isError && (
          <ErrorNote error={raise.error} />
        )}
      </Drawer>
      )}
    </div>
  );
}

function Tile({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "warn";
}) {
  return (
    <div className="rounded-lg border border-line bg-surface-0 p-3">
      <div className="text-xs text-ink-500">{label}</div>
      <div
        className={
          "mt-0.5 text-xl tabular-nums " + (tone === "warn" ? "text-warning-700" : "text-ink-900")
        }
      >
        {value}
      </div>
    </div>
  );
}
