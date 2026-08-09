/* -------------------------------------------------------------------------- */
/* Batch recalls — freezing the shelf is the easy half.                        */
/*                                                                             */
/* This screen used to report "N batches frozen" and stop. That number counts   */
/* the units that never left, which are the ones that reached nobody. The       */
/* question a recall actually has to answer is where the rest went: which       */
/* pharmacies hold it, what is still on a truck, and — the one that decides     */
/* whether this is a stock problem or a public-safety one — whether any of it   */
/* was dispensed to a named patient.                                            */
/* -------------------------------------------------------------------------- */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertOctagon, Plus, Siren } from "lucide-react";
import { useState } from "react";
import { DataGrid, type Column } from "../components/DataGrid";
import {
  Drawer,
  Empty,
  ErrorNote,
  Facts,
  Field,
  Grid,
  Input,
  ProductPicker,
  Section,
  Textarea,
} from "../components/RecordKit";
import { Badge, Button, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { dateTime, shortDate } from "../lib/format";
import { closeRecall, freezeRecall, traceRecall, type RecallTrace } from "../lib/inventory";
import type { BatchRecall, Paginated } from "../lib/types";

interface Draft {
  recall_reference: string;
  product: number | null;
  batch_number: string;
  manufacturer_name: string;
  reason: string;
}

const BLANK: Draft = {
  recall_reference: "",
  product: null,
  batch_number: "",
  manufacturer_name: "",
  reason: "",
};

export function BatchRecallsPage() {
  const qc = useQueryClient();
  const [draft, setDraft] = useState<Draft | null>(null);
  const [open, setOpen] = useState<BatchRecall | null>(null);

  const recalls = useQuery({
    queryKey: ["batch-recalls"],
    queryFn: () => api<Paginated<BatchRecall>>("/api/inventory/recalls/?page_size=200"),
  });

  const trace = useQuery({
    queryKey: ["recall-trace", open?.id],
    enabled: open != null,
    queryFn: () => traceRecall(open!.id),
  });

  const create = useMutation({
    mutationFn: (d: Draft) =>
      api<BatchRecall>("/api/inventory/recalls/", {
        method: "POST",
        body: JSON.stringify({
          recall_reference: d.recall_reference,
          product: d.product,
          batch_number: d.batch_number,
          manufacturer_name: d.manufacturer_name,
          reason: d.reason,
        }),
      }),
    onSuccess: () => {
      setDraft(null);
      void qc.invalidateQueries({ queryKey: ["batch-recalls"] });
    },
  });

  const freeze = useMutation({
    mutationFn: (id: number) => freezeRecall(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["batch-recalls"] });
      void qc.invalidateQueries({ queryKey: ["recall-trace"] });
    },
  });

  const close = useMutation({
    mutationFn: (id: number) => closeRecall(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["batch-recalls"] });
      void qc.invalidateQueries({ queryKey: ["recall-trace"] });
    },
  });

  const rows = recalls.data?.results ?? [];
  const live = rows.filter((r) => r.status !== "COMPLETED");

  const columns: Column<BatchRecall>[] = [
    {
      key: "recall_reference",
      header: "Reference",
      value: (r) => r.recall_reference,
      render: (r) => <span className="font-medium text-ink-900">{r.recall_reference}</span>,
    },
    { key: "product_name", header: "Medicine", value: (r) => r.product_name ?? "" },
    {
      key: "batch_number",
      header: "Batch",
      value: (r) => r.batch_number,
      render: (r) => <span className="font-mono text-xs text-ink-700">{r.batch_number}</span>,
    },
    { key: "manufacturer_name", header: "Manufacturer", value: (r) => r.manufacturer_name ?? "" },
    {
      key: "status",
      header: "Status",
      value: (r) => r.status,
      render: (r) => (
        <Badge
          tone={
            r.status === "COMPLETED" ? "success" : r.status === "IN_PROGRESS" ? "warning" : "danger"
          }
        >
          {r.status === "COMPLETED"
            ? "Closed"
            : r.status === "IN_PROGRESS"
              ? "Frozen"
              : "Initiated"}
        </Badge>
      ),
    },
    {
      key: "recalled_at",
      header: "Raised",
      value: (r) => r.recalled_at,
      render: (r) => shortDate(r.recalled_at),
    },
  ];

  return (
    <div className="space-y-4">
      <PageHeader
        title="Batch recalls"
        action={
          <Button onClick={() => setDraft({ ...BLANK })}>
            <Plus className="h-4 w-4" /> Raise a recall
          </Button>
        }
      />

      {live.length > 0 && (
        <div className="flex items-start gap-2 rounded-lg border border-danger-200 bg-danger-50 p-3">
          <Siren className="mt-0.5 h-4 w-4 shrink-0 text-danger-600" />
          <div className="text-sm text-danger-900">
            <span className="font-semibold">
              {live.length} recall{live.length === 1 ? "" : "s"} still open.
            </span>{" "}
            Open each one to see whether any of the batch reached a patient.
          </div>
        </div>
      )}

      <DataGrid
        rows={rows}
        columns={columns}
        getRowId={(r) => r.id}
        loading={recalls.isLoading}
        storageKey="batch-recalls"
        exportName="batch-recalls"
        searchPlaceholder="Search by reference, medicine or batch…"
        emptyMessage="No recalls have been raised."
        onRowClick={(r) => setOpen(r)}
      />

      {open && (
        <Drawer
          title={open.recall_reference}
          subtitle={`${open.product_name ?? ""} · batch ${open.batch_number}`}
          badge={
            open.status === "COMPLETED" ? (
              <Badge tone="success">Closed</Badge>
            ) : open.status === "IN_PROGRESS" ? (
              <Badge tone="warning">Frozen</Badge>
            ) : (
              <Badge tone="danger">Initiated</Badge>
            )
          }
          onClose={() => setOpen(null)}
          footer={
            <div className="flex justify-end gap-2">
              {open.status === "INITIATED" && (
                <Button onClick={() => freeze.mutate(open.id)} disabled={freeze.isPending}>
                  {freeze.isPending ? "Freezing…" : "Freeze all stock"}
                </Button>
              )}
              {open.status === "IN_PROGRESS" && (
                <Button
                  variant="secondary"
                  onClick={() => close.mutate(open.id)}
                  disabled={close.isPending}
                >
                  {close.isPending ? "Closing…" : "Close recall"}
                </Button>
              )}
            </div>
          }
        >
          <Section title="The recall">
            <Facts
              rows={[
                ["Reference", open.recall_reference],
                ["Medicine", open.product_name ?? "—"],
                ["Batch", open.batch_number],
                ["Manufacturer", open.manufacturer_name || "—"],
                ["Raised", dateTime(open.recalled_at)],
                ["Status", open.status],
              ]}
            />
            {open.reason && <p className="mt-2 text-sm text-ink-600">{open.reason}</p>}
          </Section>

          {trace.isLoading ? (
            <Section title="Tracing…">
              <p className="text-sm text-ink-500">Following the batch through the supply chain.</p>
            </Section>
          ) : trace.data ? (
            <TraceView trace={trace.data} />
          ) : null}

          {(freeze.isError || close.isError) && <ErrorNote error={freeze.error ?? close.error} />}
        </Drawer>
      )}

      {draft && (
        <Drawer
          title="Raise a recall"
          onClose={() => setDraft(null)}
          footer={
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setDraft(null)}>
                Cancel
              </Button>
              <Button
                onClick={() => create.mutate(draft)}
                disabled={
                  create.isPending ||
                  !draft.recall_reference.trim() ||
                  !draft.product ||
                  !draft.batch_number.trim() ||
                  !draft.reason.trim()
                }
              >
                {create.isPending ? "Saving…" : "Raise recall"}
              </Button>
            </div>
          }
        >
          <Section title="What is being recalled">
            <Grid>
              <Field label="Recall reference">
                <Input
                  autoFocus
                  value={draft.recall_reference}
                  onChange={(e) => setDraft({ ...draft, recall_reference: e.target.value })}
                  placeholder="RFDA-2026-014"
                />
              </Field>
              <Field label="Medicine">
                <ProductPicker
                  value={draft.product}
                  onChange={(id) => setDraft({ ...draft, product: id })}
                />
              </Field>
              <Field label="Batch number">
                <Input
                  value={draft.batch_number}
                  onChange={(e) => setDraft({ ...draft, batch_number: e.target.value })}
                />
              </Field>
              <Field label="Manufacturer">
                <Input
                  value={draft.manufacturer_name}
                  onChange={(e) => setDraft({ ...draft, manufacturer_name: e.target.value })}
                />
              </Field>
            </Grid>
            <p className="mt-2 text-xs text-ink-500">
              Only this medicine's batch is affected. Another product sharing the same batch string
              is deliberately left alone.
            </p>
          </Section>

          <Section title="Reason" hint="Goes on the recall notice and the audit record.">
            <Field label="Why is this batch being recalled?">
              <Textarea
                rows={3}
                value={draft.reason}
                onChange={(e) => setDraft({ ...draft, reason: e.target.value })}
                placeholder="Manufacturer notification: dissolution failure at 12-month stability"
              />
            </Field>
          </Section>

          {create.isError && <ErrorNote error={create.error} />}
        </Drawer>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */

function TraceView({ trace }: { trace: RecallTrace }) {
  return (
    <>
      {trace.reached_patients && (
        <div className="mb-4 flex items-start gap-2 rounded-lg border border-danger-300 bg-danger-50 p-3">
          <AlertOctagon className="mt-0.5 h-5 w-5 shrink-0 text-danger-600" />
          <div className="text-sm text-danger-900">
            <div className="font-semibold">
              This batch reached patients — {trace.units_dispensed.toLocaleString()} unit(s)
              dispensed across {trace.patients.length} sale(s).
            </div>
            Freezing the shelf does not reach them. The people below were handed this medicine and
            have to be contacted.
          </div>
        </div>
      )}

      <Section title="Where the batch went">
        <div className="grid grid-cols-3 gap-3">
          <Mini label="Still held" value={trace.units_still_held} hint="frozen on shelves" />
          <Mini label="In transit" value={trace.units_in_transit} hint="on a truck now" />
          <Mini
            label="Dispensed"
            value={trace.units_dispensed}
            hint="already with patients"
            tone={trace.units_dispensed > 0 ? "danger" : undefined}
          />
        </div>
      </Section>

      <Section title="Who holds it">
        {trace.holders.length === 0 ? (
          <Empty message="No organization holds or received this batch." />
        ) : (
          <div className="overflow-x-auto rounded-lg border border-line">
            <table className="w-full text-sm">
              <thead className="border-b border-line bg-surface-100 text-left text-xs uppercase tracking-wide text-ink-500">
                <tr>
                  <th className="px-3 py-2">Organization</th>
                  <th className="px-3 py-2 text-right">On hand</th>
                  <th className="px-3 py-2 text-right">In transit</th>
                  <th className="px-3 py-2 text-right">Received</th>
                  <th className="px-3 py-2 text-right">Dispensed</th>
                </tr>
              </thead>
              <tbody>
                {trace.holders.map((h) => (
                  <tr key={h.organization} className="border-b border-line last:border-0">
                    <td className="px-3 py-2 text-ink-900">{h.organization_name}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{h.on_hand_units}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{h.in_transit_units}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{h.received_units}</td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {h.dispensed_units > 0 ? (
                        <span className="font-medium text-danger-700">{h.dispensed_units}</span>
                      ) : (
                        <span className="text-ink-400">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      {trace.patients.length > 0 && (
        <Section
          title="Patients to contact"
          hint="A sale without a dispensing record cannot be attributed to a named person — it still counts as dispensed."
        >
          <ul className="divide-y divide-line rounded-lg border border-line">
            {trace.patients.map((p) => (
              <li key={p.sale} className="flex items-start justify-between gap-3 px-3 py-2">
                <div className="min-w-0">
                  <div className="text-sm text-ink-900">
                    {p.patient_name || "Unnamed walk-in sale"}
                    {p.patient_id_number && (
                      <span className="ml-1.5 font-mono text-xs text-ink-500">
                        {p.patient_id_number}
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-ink-500">
                    {p.quantity} unit(s) · {p.organization_name} · {shortDate(p.sold_at)}
                    {p.prescriber_name && ` · prescribed by ${p.prescriber_name}`}
                  </div>
                </div>
                <Badge tone={p.contactable ? "warning" : "danger"}>
                  {p.contactable ? "Contactable" : "No record"}
                </Badge>
              </li>
            ))}
          </ul>
        </Section>
      )}
    </>
  );
}

function Mini({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: number;
  hint: string;
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
        {value.toLocaleString()}
      </div>
      <div className="mt-0.5 text-xs text-ink-500">{hint}</div>
    </div>
  );
}
