import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Layers, Plus, ShieldCheck } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { DataGrid } from "../components/DataGrid";
import {
  Drawer,
  ErrorNote,
  Field,
  Grid,
  Input,
  LineEditor,
  ProductPicker,
  Section,
  Select,
  StatusBadge,
  SupplierSelect,
  Textarea,
  TotalsRow,
} from "../components/RecordKit";
import { useDefaultOrg } from "../lib/recordData";
import { Badge, Button, Modal, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { money, num, type PurchaseRequisition, type RequisitionLine } from "../lib/procurement";
import type { Paginated } from "../lib/types";

const PRIORITIES = [
  ["LOW", "Low"],
  ["NORMAL", "Normal"],
  ["HIGH", "High"],
  ["URGENT", "Urgent (stock-out)"],
] as const;

const emptyLine = (): RequisitionLine => ({
  product: 0,
  quantity: 1,
  estimated_unit_cost: "0.00",
});

/* -------------------------------------------------------------------------- */

function RequisitionDrawer({
  requisition,
  onClose,
}: {
  requisition: PurchaseRequisition | null;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const { orgId } = useDefaultOrg();
  const editable = requisition === null || requisition.is_editable;
  const [form, setForm] = useState({
    priority: requisition?.priority ?? "NORMAL",
    needed_by: requisition?.needed_by ?? "",
    justification: requisition?.justification ?? "",
    preferred_supplier: requisition?.preferred_supplier ?? null,
    lines: requisition?.lines?.length
      ? requisition.lines.map((l) => ({ ...l }))
      : [emptyLine()],
  });

  const total = useMemo(
    () => form.lines.reduce((s, l) => s + num(l.estimated_unit_cost) * Number(l.quantity || 0), 0),
    [form.lines],
  );

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["requisitions"] });
    void qc.invalidateQueries({ queryKey: ["procurement-overview"] });
  };

  const save = useMutation({
    mutationFn: () =>
      api<PurchaseRequisition>(
        requisition
          ? `/api/procurement/requisitions/${requisition.id}/`
          : "/api/procurement/requisitions/",
        {
          method: requisition ? "PATCH" : "POST",
          body: JSON.stringify({
            organization: orgId,
            priority: form.priority,
            needed_by: form.needed_by || null,
            justification: form.justification,
            preferred_supplier: form.preferred_supplier,
            lines: form.lines
              .filter((l) => l.product && Number(l.quantity) > 0)
              .map((l) => ({
                product: l.product,
                quantity: Number(l.quantity),
                quantity_approved: Number(l.quantity_approved ?? 0),
                estimated_unit_cost: l.estimated_unit_cost || "0",
                notes: l.notes ?? "",
              })),
          }),
        },
      ),
    onSuccess: () => {
      invalidate();
      onClose();
    },
  });

  const submit = useMutation({
    mutationFn: () =>
      api(`/api/procurement/requisitions/${requisition!.id}/submit/`, {
        method: "POST",
        body: "{}",
      }),
    onSuccess: () => {
      invalidate();
      onClose();
    },
  });

  return (
    <Drawer
      title={requisition ? requisition.requisition_number : "New requisition"}
      badge={
        requisition && (
          <StatusBadge status={requisition.status} label={requisition.status_display} />
        )
      }
      subtitle={
        requisition
          ? `${requisition.organization_name} · raised by ${requisition.requested_by_name ?? "—"}`
          : "Tell HQ what this branch needs. Approved requisitions get consolidated into supplier orders."
      }
      onClose={onClose}
      width="max-w-4xl"
      footer={
        <>
          {requisition?.status === "DRAFT" && (
            <Button disabled={submit.isPending} onClick={() => submit.mutate()}>
              <ShieldCheck className="h-3.5 w-3.5" /> Submit for approval
            </Button>
          )}
          {editable && (
            <Button disabled={save.isPending} onClick={() => save.mutate()}>
              {save.isPending ? "Saving…" : requisition ? "Save changes" : "Create requisition"}
            </Button>
          )}
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
        </>
      }
    >
      <ErrorNote error={save.error ?? submit.error} />

      {requisition?.decision_note && (
        <div className="mb-4 rounded-md border border-line bg-surface-50 px-3 py-2 text-sm text-ink-700">
          <span className="font-semibold">Approver note:</span> {requisition.decision_note}
        </div>
      )}

      <Section title="Request">
        <Grid cols={3}>
          <Field label="Priority">
            <Select
              disabled={!editable}
              value={form.priority}
              onChange={(e) => setForm({ ...form, priority: e.target.value as never })}
            >
              {PRIORITIES.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Needed by">
            <Input
              type="date"
              disabled={!editable}
              value={form.needed_by}
              onChange={(e) => setForm({ ...form, needed_by: e.target.value })}
            />
          </Field>
          <Field label="Preferred supplier" hint="A hint for the buyer — not binding.">
            <SupplierSelect
              value={form.preferred_supplier}
              allowBlank
              disabled={!editable}
              onChange={(id) => setForm({ ...form, preferred_supplier: id })}
            />
          </Field>
        </Grid>
        <div className="mt-3">
          <Field label="Justification">
            <Textarea
              disabled={!editable}
              value={form.justification}
              onChange={(e) => setForm({ ...form, justification: e.target.value })}
              placeholder="Why this is needed — e.g. below reorder level, stock-out risk before month end"
            />
          </Field>
        </div>
      </Section>

      <Section title="What we need">
        <LineEditor<RequisitionLine>
          rows={form.lines}
          readOnly={!editable}
          onChange={(lines) => setForm({ ...form, lines })}
          makeRow={emptyLine}
          addLabel="Add product"
          emptyMessage="Nothing requested yet."
          columns={[
            {
              header: "Product",
              width: "42%",
              cell: (row, set) => (
                <ProductPicker
                  value={row.product || null}
                  disabled={!editable}
                  onChange={(id) => set({ product: id })}
                />
              ),
            },
            {
              header: "Qty",
              width: "12%",
              align: "right",
              cell: (row, set) =>
                editable ? (
                  <Input
                    type="number"
                    min={1}
                    value={row.quantity}
                    onChange={(e) => set({ quantity: Number(e.target.value) })}
                    className="text-right"
                  />
                ) : (
                  <>{row.quantity}</>
                ),
            },
            {
              header: "Approved",
              width: "12%",
              align: "right",
              cell: (row, set) =>
                editable ? (
                  <Input
                    type="number"
                    min={0}
                    value={row.quantity_approved ?? 0}
                    onChange={(e) => set({ quantity_approved: Number(e.target.value) })}
                    className="text-right"
                  />
                ) : (
                  <>{row.quantity_approved || row.quantity}</>
                ),
            },
            {
              header: "Est. unit cost",
              width: "16%",
              align: "right",
              cell: (row, set) =>
                editable ? (
                  <Input
                    type="number"
                    step="0.01"
                    value={row.estimated_unit_cost}
                    onChange={(e) => set({ estimated_unit_cost: e.target.value })}
                    className="text-right"
                  />
                ) : (
                  <>{row.estimated_unit_cost}</>
                ),
            },
            {
              header: "Est. total",
              width: "18%",
              align: "right",
              cell: (row) => (
                <span className="font-medium">
                  {(num(row.estimated_unit_cost) * Number(row.quantity || 0)).toLocaleString(
                    undefined,
                    { maximumFractionDigits: 2 },
                  )}
                </span>
              ),
            },
          ]}
          footer={<TotalsRow span={4} label="Estimated total" value={money(total)} strong />}
        />
      </Section>
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

function ConsolidateModal({
  requisitions,
  onClose,
}: {
  requisitions: PurchaseRequisition[];
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { orgId } = useDefaultOrg();
  const [supplier, setSupplier] = useState<number | null>(null);
  const [expected, setExpected] = useState("");
  const [currency, setCurrency] = useState("RWF");
  const [rate, setRate] = useState("1.000000");
  const [isImport, setIsImport] = useState(false);

  const consolidate = useMutation({
    mutationFn: () =>
      api<{ id: number; po_number: string }>("/api/procurement/requisitions/consolidate/", {
        method: "POST",
        body: JSON.stringify({
          organization: orgId,
          supplier,
          requisitions: requisitions.map((r) => r.id),
          expected_delivery: expected || null,
          currency,
          exchange_rate: rate,
          is_import: isImport,
        }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["requisitions"] });
      void qc.invalidateQueries({ queryKey: ["purchase-orders"] });
      onClose();
      navigate("/procurement/orders");
    },
  });

  return (
    <Modal title="Consolidate into a purchase order" onClose={onClose}>
      <div className="flex flex-col gap-4">
        <p className="text-sm text-ink-500">
          Demand for the same product across {requisitions.length} requisition
          {requisitions.length === 1 ? "" : "s"} is merged onto one line each.
        </p>
        <ErrorNote error={consolidate.error} />
        <Field label="Supplier">
          <SupplierSelect value={supplier} onChange={setSupplier} />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Expected delivery">
            <Input type="date" value={expected} onChange={(e) => setExpected(e.target.value)} />
          </Field>
          <Field label="Currency">
            <Input
              maxLength={3}
              value={currency}
              onChange={(e) => setCurrency(e.target.value.toUpperCase())}
            />
          </Field>
        </div>
        {currency !== "RWF" && (
          <Field label="Exchange rate to RWF">
            <Input
              type="number"
              step="0.000001"
              value={rate}
              onChange={(e) => setRate(e.target.value)}
            />
          </Field>
        )}
        <label className="flex items-center gap-2 text-sm text-ink-700">
          <input
            type="checkbox"
            checked={isImport}
            onChange={(e) => setIsImport(e.target.checked)}
            className="h-3.5 w-3.5 accent-brand-600"
          />
          This is an import (landed cost will be allocated)
        </label>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={!supplier || consolidate.isPending} onClick={() => consolidate.mutate()}>
            {consolidate.isPending ? "Creating…" : "Create purchase order"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

/* -------------------------------------------------------------------------- */

export function RequisitionsPage() {
  const [open, setOpen] = useState<PurchaseRequisition | null>(null);
  const [creating, setCreating] = useState(false);
  const [consolidating, setConsolidating] = useState<PurchaseRequisition[] | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["requisitions"],
    queryFn: () =>
      api<Paginated<PurchaseRequisition>>("/api/procurement/requisitions/?page_size=200"),
  });

  const rows = data?.results ?? [];
  const current = open ? rows.find((r) => r.id === open.id) ?? open : null;

  return (
    <div>
      <PageHeader
        title="Purchase requisitions"
        action={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" /> New requisition
          </Button>
        }
      />
      <p className="mb-4 max-w-3xl text-sm text-ink-500">
        Branches raise what they need; an approver (never the requester) signs it off; HQ selects the
        approved ones and consolidates them into one purchase order per supplier.
      </p>

      <DataGrid<PurchaseRequisition>
        rows={rows}
        loading={isLoading}
        getRowId={(r) => r.id}
        storageKey="procurement-requisitions"
        exportName="requisitions"
        searchPlaceholder="Search by number, branch, requester…"
        emptyMessage="No requisitions yet."
        onRowClick={(r) => setOpen(r)}
        bulkActions={(selected, clear) => {
          const approved = selected.filter((r) => r.status === "APPROVED");
          return (
            <>
              <Button
                disabled={approved.length === 0}
                onClick={() => {
                  setConsolidating(approved);
                  clear();
                }}
              >
                <Layers className="h-3.5 w-3.5" /> Consolidate {approved.length} into a PO
              </Button>
              {approved.length !== selected.length && (
                <span className="text-xs text-ink-500">
                  Only approved requisitions can be consolidated.
                </span>
              )}
            </>
          );
        }}
        columns={[
          {
            key: "requisition_number",
            header: "Requisition",
            render: (r) => (
              <div>
                <div className="font-mono font-medium text-ink-900">
                  {r.requisition_number || "—"}
                </div>
                <div className="text-xs text-ink-500">{r.organization_name}</div>
              </div>
            ),
          },
          {
            key: "status",
            header: "Status",
            value: (r) => r.status,
            render: (r) => <StatusBadge status={r.status} label={r.status_display} />,
          },
          {
            key: "priority",
            header: "Priority",
            value: (r) => r.priority,
            render: (r) => (
              <Badge tone={r.priority === "URGENT" ? "danger" : r.priority === "HIGH" ? "warning" : "neutral"}>
                {r.priority}
              </Badge>
            ),
          },
          { key: "needed_by", header: "Needed by", value: (r) => r.needed_by ?? "—" },
          {
            key: "lines",
            header: "Lines",
            align: "right",
            numeric: true,
            value: (r) => r.lines.length,
          },
          {
            key: "estimated_total",
            header: "Estimated",
            align: "right",
            numeric: true,
            value: (r) => Number(r.estimated_total),
            render: (r) => money(r.estimated_total),
          },
          { key: "requested_by_name", header: "Requested by", value: (r) => r.requested_by_name ?? "—" },
        ]}
      />

      {creating && <RequisitionDrawer requisition={null} onClose={() => setCreating(false)} />}
      {current && <RequisitionDrawer requisition={current} onClose={() => setOpen(null)} />}
      {consolidating && (
        <ConsolidateModal requisitions={consolidating} onClose={() => setConsolidating(null)} />
      )}
    </div>
  );
}
