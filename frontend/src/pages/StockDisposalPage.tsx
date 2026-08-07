/* -------------------------------------------------------------------------- */
/* Witnessed destruction of stock that must never be sold.                     */
/*                                                                             */
/* Confirming used to set a status. The stock stayed on the books as sellable   */
/* and the loss never reached the P&L, so a certificate was issued for goods    */
/* the system still believed it owned. Destruction now removes the units,       */
/* writes a stock movement and posts the write-off — which is why the disposal  */
/* has to say *what* is being destroyed before it can be confirmed.             */
/* -------------------------------------------------------------------------- */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Flame, Plus, Trash2 } from "lucide-react";
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
  Section,
  Select,
} from "../components/RecordKit";
import { Badge, Button, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { money, shortDate } from "../lib/format";
import {
  addDisposalLine,
  confirmDestruction,
  destructionCandidates,
  type DestructionCandidate,
} from "../lib/inventory";
import { useDefaultOrg } from "../lib/recordData";
import type { Paginated, StockDisposal } from "../lib/types";

interface Draft {
  disposal_no: string;
  reason: string;
  destruction_method: string;
  secondary_witness_name: string;
  certificate_no: string;
}

const BLANK: Draft = {
  disposal_no: "",
  reason: "EXPIRED",
  destruction_method: "INCINERATION",
  secondary_witness_name: "",
  certificate_no: "",
};

export function StockDisposalPage() {
  const { orgId } = useDefaultOrg();
  const qc = useQueryClient();
  const [draft, setDraft] = useState<Draft | null>(null);
  const [open, setOpen] = useState<StockDisposal | null>(null);
  const [picking, setPicking] = useState<DestructionCandidate | null>(null);
  const [pickQty, setPickQty] = useState("");

  const disposals = useQuery({
    queryKey: ["disposals"],
    queryFn: () => api<Paginated<StockDisposal>>("/api/inventory/disposals/?page_size=200"),
  });

  const candidates = useQuery({
    queryKey: ["destruction-candidates", orgId],
    enabled: orgId != null,
    queryFn: () => destructionCandidates(orgId as number),
  });

  const create = useMutation({
    mutationFn: (d: Draft) =>
      api<StockDisposal>("/api/inventory/disposals/", {
        method: "POST",
        body: JSON.stringify({ ...d, organization: orgId }),
      }),
    onSuccess: (created) => {
      setDraft(null);
      setOpen(created);
      void qc.invalidateQueries({ queryKey: ["disposals"] });
    },
  });

  const addLine = useMutation({
    mutationFn: (p: { disposal: number; batch: number; quantity: number }) =>
      addDisposalLine(p.disposal, p.batch, p.quantity),
    onSuccess: () => {
      setPicking(null);
      setPickQty("");
      void qc.invalidateQueries({ queryKey: ["disposals"] });
    },
  });

  const destroy = useMutation({
    mutationFn: (id: number) => confirmDestruction(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["disposals"] });
      void qc.invalidateQueries({ queryKey: ["destruction-candidates"] });
    },
  });

  const rows = disposals.data?.results ?? [];
  const waiting = candidates.data ?? [];
  const waitingValue = waiting.reduce((s, c) => s + Number(c.value), 0);

  const columns: Column<StockDisposal>[] = [
    {
      key: "disposal_no",
      header: "Disposal",
      value: (d) => d.disposal_no,
      render: (d) => <span className="font-medium text-ink-900">{d.disposal_no}</span>,
    },
    { key: "reason", header: "Reason", value: (d) => d.reason },
    { key: "destruction_method", header: "Method", value: (d) => d.destruction_method },
    {
      key: "witnesses",
      header: "Witnesses",
      sortable: false,
      value: (d) => `${d.primary_witness_username} ${d.secondary_witness_name}`,
      render: (d) => (
        <span className="text-xs text-ink-600">
          {d.primary_witness_username}
          {d.secondary_witness_name ? ` + ${d.secondary_witness_name}` : ""}
          {!d.secondary_witness_name && (
            <span className="ml-1 text-danger-700">second witness missing</span>
          )}
        </span>
      ),
    },
    { key: "certificate_no", header: "Certificate", value: (d) => d.certificate_no || "—" },
    {
      key: "status",
      header: "Status",
      value: (d) => d.status,
      render: (d) => (
        <Badge tone={d.status === "DESTROYED" ? "success" : "neutral"}>
          {d.status === "DESTROYED" ? "Destroyed" : d.status === "APPROVED" ? "Approved" : "Draft"}
        </Badge>
      ),
    },
    {
      key: "destroyed_at",
      header: "Destroyed",
      value: (d) => d.destroyed_at ?? "",
      render: (d) => (d.destroyed_at ? shortDate(d.destroyed_at) : <span className="text-ink-400">—</span>),
    },
  ];

  return (
    <div className="space-y-4">
      <PageHeader
        title="Stock disposal"
        action={
          <Button onClick={() => setDraft({ ...BLANK })}>
            <Plus className="h-4 w-4" /> New disposal
          </Button>
        }
      />
      <p className="-mt-2 max-w-3xl text-sm text-ink-500">
        Confirming a disposal removes the units from stock, records the movement and writes the
        loss off. Because it is irreversible, a disposal must list what is being destroyed and name
        two witnesses before it can be confirmed.
      </p>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Tile label="Awaiting destruction" value={waiting.length} />
        <Tile
          label="Value to write off"
          value={money(waitingValue)}
          tone={waitingValue > 0 ? "danger" : undefined}
        />
        <Tile
          label="Expired but still active"
          value={waiting.filter((c) => c.is_expired && c.status === "ACTIVE").length}
          hint="unsellable in fact, sellable on the system"
          tone={waiting.some((c) => c.is_expired && c.status === "ACTIVE") ? "danger" : undefined}
        />
      </div>

      <DataGrid
        rows={rows}
        columns={columns}
        getRowId={(d) => d.id}
        loading={disposals.isLoading}
        storageKey="stock-disposals"
        exportName="stock-disposals"
        searchPlaceholder="Search by disposal number or certificate…"
        emptyMessage="No disposals recorded."
        onRowClick={(d) => setOpen(d)}
      />

      {waiting.length > 0 && (
        <div>
          <h2 className="mb-2 text-sm font-semibold text-ink-900">
            Stock that cannot be sold
          </h2>
          <p className="mb-2 text-xs text-ink-500">
            Expired, quarantined or recalled. Add these to a disposal to have them destroyed.
          </p>
          <DataGrid
            rows={waiting}
            columns={[
              { key: "product_name", header: "Medicine", value: (c) => c.product_name },
              {
                key: "batch_number",
                header: "Batch",
                value: (c) => c.batch_number,
                render: (c) => (
                  <span className="font-mono text-xs text-ink-700">{c.batch_number}</span>
                ),
              },
              {
                key: "quantity",
                header: "Units",
                align: "right",
                numeric: true,
                value: (c) => c.quantity,
              },
              {
                key: "expiry_date",
                header: "Expiry",
                value: (c) => c.expiry_date,
                render: (c) => (
                  <span className={c.is_expired ? "text-danger-700" : "text-ink-600"}>
                    {shortDate(c.expiry_date)}
                  </span>
                ),
              },
              { key: "status", header: "Status", value: (c) => c.status },
              {
                key: "value",
                header: "Value",
                align: "right",
                numeric: true,
                value: (c) => Number(c.value),
                render: (c) => money(c.value),
              },
              {
                key: "add",
                header: "",
                align: "right",
                fixed: true,
                sortable: false,
                render: (c) => (
                  <Button
                    variant="ghost"
                    onClick={(e) => {
                      e.stopPropagation();
                      setPicking(c);
                      setPickQty(String(c.quantity));
                    }}
                    disabled={!open || open.status === "DESTROYED"}
                    title={open ? "Add to the open disposal" : "Open a disposal first"}
                  >
                    <Trash2 className="h-3.5 w-3.5" /> Add
                  </Button>
                ),
              },
            ]}
            getRowId={(c) => c.batch}
            loading={candidates.isLoading}
            storageKey="destruction-candidates"
            exportName="destruction-candidates"
            searchPlaceholder="Search unsellable stock…"
            emptyMessage="Nothing is waiting to be destroyed."
          />
        </div>
      )}

      {picking && open && (
        <Drawer
          title={`Add ${picking.product_name} to ${open.disposal_no}`}
          subtitle={`Batch ${picking.batch_number} · ${picking.quantity} unit(s) available`}
          onClose={() => setPicking(null)}
          footer={
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setPicking(null)}>
                Cancel
              </Button>
              <Button
                onClick={() =>
                  addLine.mutate({
                    disposal: open.id,
                    batch: picking.batch,
                    quantity: Number(pickQty),
                  })
                }
                disabled={addLine.isPending || Number(pickQty) <= 0}
              >
                {addLine.isPending ? "Adding…" : "Add to disposal"}
              </Button>
            </div>
          }
        >
          <Section title="How much is being destroyed">
            <Field label="Units">
              <Input
                autoFocus
                type="number"
                min={1}
                max={picking.quantity}
                value={pickQty}
                onChange={(e) => setPickQty(e.target.value)}
              />
            </Field>
            <p className="mt-2 text-xs text-ink-500">
              Worth {money(picking.value)} at cost. This is what will be written off when the
              disposal is confirmed.
            </p>
          </Section>
          {addLine.isError && <ErrorNote error={addLine.error} />}
        </Drawer>
      )}

      {open && !picking && (
        <Drawer
          title={open.disposal_no}
          subtitle={`${open.reason} · ${open.destruction_method}`}
          badge={
            open.status === "DESTROYED" ? (
              <Badge tone="success">Destroyed</Badge>
            ) : (
              <Badge tone="neutral">{open.status}</Badge>
            )
          }
          onClose={() => setOpen(null)}
          footer={
            open.status !== "DESTROYED" && (
              <div className="flex justify-end gap-2">
                <Button onClick={() => destroy.mutate(open.id)} disabled={destroy.isPending}>
                  <Flame className="h-4 w-4" />
                  {destroy.isPending ? "Destroying…" : "Confirm destruction"}
                </Button>
              </div>
            )
          }
        >
          <Section title="The disposal">
            <Facts
              rows={[
                ["Number", open.disposal_no],
                ["Reason", open.reason],
                ["Method", open.destruction_method],
                ["Primary witness", open.primary_witness_username],
                ["Second witness", open.secondary_witness_name || "— required —"],
                ["Certificate", open.certificate_no || "—"],
              ]}
            />
            {!open.secondary_witness_name && (
              <p className="mt-2 text-sm text-danger-700">
                A second witness must be named before this can be confirmed — destruction is
                witnessed by two people, and one of them cannot be a blank field.
              </p>
            )}
          </Section>

          <Section
            title="What will be destroyed"
            hint="Add batches from the unsellable-stock list on this page."
          >
            <Empty message="Lines are added from the list below the disposals grid." />
          </Section>

          {open.status !== "DESTROYED" && (
            <Section title="What confirming does">
              <p className="text-sm text-ink-600">
                The units leave stock, a wastage movement is written so the ledger explains the
                change, and the value is written off to the P&amp;L. It cannot be undone, and
                confirming twice will not remove the units twice.
              </p>
            </Section>
          )}

          {destroy.isError && <ErrorNote error={destroy.error} />}
        </Drawer>
      )}

      {draft && (
        <Drawer
          title="New disposal"
          subtitle="Record the destruction, its method, and who witnessed it."
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
                  !draft.disposal_no.trim() ||
                  !draft.secondary_witness_name.trim()
                }
              >
                {create.isPending ? "Saving…" : "Create disposal"}
              </Button>
            </div>
          }
        >
          <Section title="Destruction record">
            <Grid>
              <Field label="Disposal number">
                <Input
                  autoFocus
                  value={draft.disposal_no}
                  onChange={(e) => setDraft({ ...draft, disposal_no: e.target.value })}
                  placeholder="DSP-2026-014"
                />
              </Field>
              <Field label="Reason">
                <Select
                  value={draft.reason}
                  onChange={(e) => setDraft({ ...draft, reason: e.target.value })}
                >
                  <option value="EXPIRED">Expired stock</option>
                  <option value="DAMAGED">Damaged / compromised</option>
                  <option value="RECALLED">Recalled stock</option>
                </Select>
              </Field>
              <Field label="Method">
                <Input
                  value={draft.destruction_method}
                  onChange={(e) => setDraft({ ...draft, destruction_method: e.target.value })}
                />
              </Field>
              <Field label="Second witness">
                <Input
                  value={draft.secondary_witness_name}
                  onChange={(e) =>
                    setDraft({ ...draft, secondary_witness_name: e.target.value })
                  }
                  placeholder="Full name"
                />
              </Field>
              <Field label="Certificate number">
                <Input
                  value={draft.certificate_no}
                  onChange={(e) => setDraft({ ...draft, certificate_no: e.target.value })}
                />
              </Field>
            </Grid>
            <p className="mt-2 text-xs text-ink-500">
              You are recorded as the primary witness. A second is required — the API refuses a
              destruction without one.
            </p>
          </Section>
          {create.isError && <ErrorNote error={create.error} />}
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
