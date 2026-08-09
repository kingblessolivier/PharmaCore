import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Calculator, Link2, Plus, Trash2, Unlink } from "lucide-react";
import { useState } from "react";
import { DataGrid } from "../components/DataGrid";
import {
  Drawer,
  Empty,
  ErrorNote,
  Field,
  Grid,
  Input,
  Section,
  Select,
  StatusBadge,
  SupplierSelect,
  Textarea,
} from "../components/RecordKit";
import { useDefaultOrg } from "../lib/recordData";
import { Badge, Button, ConfirmModal, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import {
  INCOTERMS,
  LANDED_COST_KINDS,
  money,
  type ImportConsignment,
  type LandedCostAllocationResult,
  type LandedCostComponent,
  type PurchaseOrder,
} from "../lib/procurement";
import type { Paginated } from "../lib/types";

const STATUSES = [
  ["DRAFT", "Draft"],
  ["PROFORMA", "Proforma received"],
  ["SHIPPED", "Shipped / in transit"],
  ["ARRIVED", "Arrived at port"],
  ["AT_CUSTOMS", "At customs / clearing"],
  ["CLEARED", "Customs cleared"],
  ["LANDED", "Landed & costed"],
  ["CANCELLED", "Cancelled"],
] as const;

const MODES = [
  ["SEA", "Sea freight"],
  ["AIR", "Air freight"],
  ["ROAD", "Road freight"],
  ["RAIL", "Rail"],
  ["COURIER", "Courier"],
] as const;

type Draft = Omit<Partial<ImportConsignment>, "supplier"> & { supplier: number | null };

/* -------------------------------------------------------------------------- */

function CostsSection({ consignment }: { consignment: ImportConsignment }) {
  const qc = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [deleting, setDeleting] = useState<LandedCostComponent | null>(null);
  const [form, setForm] = useState({
    kind: "FREIGHT",
    description: "",
    vendor_name: "",
    invoice_reference: "",
    amount: "",
    currency: "RWF",
    exchange_rate: "1.000000",
    is_recoverable_tax: false,
    incurred_on: new Date().toISOString().slice(0, 10),
  });

  const refresh = () => void qc.invalidateQueries({ queryKey: ["consignments"] });

  const create = useMutation({
    mutationFn: () =>
      api("/api/procurement/landed-costs/", {
        method: "POST",
        body: JSON.stringify({ ...form, consignment: consignment.id }),
      }),
    onSuccess: () => {
      setAdding(false);
      setForm({ ...form, amount: "", description: "", invoice_reference: "" });
      refresh();
    },
  });

  const remove = useMutation({
    mutationFn: (id: number) =>
      api<void>(`/api/procurement/landed-costs/${id}/`, { method: "DELETE" }),
    onSuccess: () => {
      setDeleting(null);
      refresh();
    },
  });

  return (
    <>
      <Section
        title="Landed-cost components"
        hint="Recoverable import VAT is excluded from unit cost — it comes back from RRA."
        action={
          <Button variant="secondary" onClick={() => setAdding((a) => !a)}>
            <Plus className="h-3.5 w-3.5" /> {adding ? "Cancel" : "Add cost"}
          </Button>
        }
      >
        {adding && (
          <div className="mb-3 rounded-lg border border-line bg-surface-50 p-3">
            <ErrorNote error={create.error} />
            <Grid cols={4}>
              <Field label="Cost type" className="sm:col-span-2">
                <Select
                  value={form.kind}
                  onChange={(e) => {
                    const kind = LANDED_COST_KINDS.find((k) => k.value === e.target.value);
                    setForm({
                      ...form,
                      kind: e.target.value,
                      is_recoverable_tax: Boolean(kind?.recoverable),
                    });
                  }}
                >
                  {LANDED_COST_KINDS.map((k) => (
                    <option key={k.value} value={k.value}>
                      {k.label}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Amount">
                <Input
                  type="number"
                  step="0.01"
                  value={form.amount}
                  onChange={(e) => setForm({ ...form, amount: e.target.value })}
                />
              </Field>
              <Field label="Currency">
                <Input
                  maxLength={3}
                  value={form.currency}
                  onChange={(e) => setForm({ ...form, currency: e.target.value.toUpperCase() })}
                />
              </Field>
              <Field label="Rate to RWF">
                <Input
                  type="number"
                  step="0.000001"
                  value={form.exchange_rate}
                  onChange={(e) => setForm({ ...form, exchange_rate: e.target.value })}
                />
              </Field>
              <Field label="Vendor">
                <Input
                  value={form.vendor_name}
                  onChange={(e) => setForm({ ...form, vendor_name: e.target.value })}
                  placeholder="Freight forwarder, clearing agent, RRA…"
                />
              </Field>
              <Field label="Invoice reference">
                <Input
                  value={form.invoice_reference}
                  onChange={(e) => setForm({ ...form, invoice_reference: e.target.value })}
                />
              </Field>
              <Field label="Incurred on">
                <Input
                  type="date"
                  value={form.incurred_on}
                  onChange={(e) => setForm({ ...form, incurred_on: e.target.value })}
                />
              </Field>
              <Field label="Description" className="sm:col-span-4">
                <Input
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                />
              </Field>
            </Grid>
            <label className="mt-3 flex items-center gap-2 text-sm text-ink-700">
              <input
                type="checkbox"
                checked={form.is_recoverable_tax}
                onChange={(e) => setForm({ ...form, is_recoverable_tax: e.target.checked })}
                className="h-3.5 w-3.5 accent-brand-600"
              />
              Recoverable tax — reclaimed from RRA, so it must not inflate unit cost
            </label>
            <div className="mt-3 flex justify-end">
              <Button disabled={!form.amount || create.isPending} onClick={() => create.mutate()}>
                {create.isPending ? "Saving…" : "Add cost"}
              </Button>
            </div>
          </div>
        )}

        <div className="overflow-x-auto rounded-lg border border-line">
          <table className="w-full min-w-[680px] text-sm">
            <thead className="border-b border-line bg-surface-50 text-left text-[11px] uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-2.5 py-2">Cost</th>
                <th className="px-2.5 py-2">Vendor / reference</th>
                <th className="px-2.5 py-2 text-right">Amount</th>
                <th className="px-2.5 py-2 text-right">In RWF</th>
                <th className="px-2.5 py-2" />
              </tr>
            </thead>
            <tbody>
              {consignment.costs.map((c) => (
                <tr key={c.id} className="border-b border-line last:border-0">
                  <td className="px-2.5 py-2">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-ink-900">{c.kind_display}</span>
                      {c.is_recoverable_tax && <Badge tone="info">Recoverable</Badge>}
                    </div>
                    {c.description && <div className="text-xs text-ink-500">{c.description}</div>}
                  </td>
                  <td className="px-2.5 py-2 text-ink-700">
                    {c.vendor_name || "—"}
                    {c.invoice_reference && (
                      <span className="text-ink-500"> · {c.invoice_reference}</span>
                    )}
                  </td>
                  <td className="px-2.5 py-2 text-right tabular-nums">
                    {money(c.amount, c.currency)}
                  </td>
                  <td className="px-2.5 py-2 text-right tabular-nums">{money(c.amount_base)}</td>
                  <td className="px-2.5 py-2 text-right">
                    <button
                      onClick={() => setDeleting(c)}
                      className="rounded-md p-1.5 text-ink-500 hover:bg-red-50 hover:text-red-600"
                      aria-label="Delete cost"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
              {consignment.costs.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-3 py-6 text-center text-ink-500">
                    No costs recorded — the goods would land at invoice price only.
                  </td>
                </tr>
              )}
            </tbody>
            <tfoot className="border-t border-line bg-surface-50">
              <tr>
                <td colSpan={3} className="px-2.5 py-1.5 text-right">
                  Allocatable pool (excl. recoverable tax)
                </td>
                <td className="px-2.5 py-1.5 text-right font-semibold tabular-nums">
                  {money(consignment.landed_cost_total)}
                </td>
                <td />
              </tr>
              <tr>
                <td colSpan={3} className="px-2.5 py-1.5 text-right text-ink-500">
                  Recoverable tax (reclaimed, not costed)
                </td>
                <td className="px-2.5 py-1.5 text-right tabular-nums text-ink-500">
                  {money(consignment.recoverable_tax_total)}
                </td>
                <td />
              </tr>
            </tfoot>
          </table>
        </div>
      </Section>

      {deleting && (
        <ConfirmModal
          title="Delete landed cost"
          message={`Remove ${deleting.kind_display} of ${money(deleting.amount, deleting.currency)}?`}
          busy={remove.isPending}
          onConfirm={() => remove.mutate(deleting.id)}
          onClose={() => setDeleting(null)}
        />
      )}
    </>
  );
}

/* -------------------------------------------------------------------------- */

function OrdersSection({ consignment }: { consignment: ImportConsignment }) {
  const qc = useQueryClient();
  const [pick, setPick] = useState<number | "">("");

  const { data: orders } = useQuery({
    queryKey: ["purchase-orders", "import-attachable"],
    queryFn: () => api<Paginated<PurchaseOrder>>("/api/procurement/orders/?page_size=200"),
    select: (r) => r.results,
  });

  const attachable = (orders ?? []).filter(
    (o) => o.consignment === null && !["CANCELLED", "CLOSED"].includes(o.status),
  );
  const attached = (orders ?? []).filter((o) => o.consignment === consignment.id);

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["consignments"] });
    void qc.invalidateQueries({ queryKey: ["purchase-orders"] });
  };

  const attach = useMutation({
    mutationFn: () =>
      api(`/api/procurement/consignments/${consignment.id}/attach_order/`, {
        method: "POST",
        body: JSON.stringify({ order: pick }),
      }),
    onSuccess: () => {
      setPick("");
      refresh();
    },
  });

  const detach = useMutation({
    mutationFn: (orderId: number) =>
      api(`/api/procurement/consignments/${consignment.id}/detach_order/`, {
        method: "POST",
        body: JSON.stringify({ order: orderId }),
      }),
    onSuccess: refresh,
  });

  return (
    <Section
      title="Purchase orders on this shipment"
      hint="Landed cost is spread across the lines of every attached order."
    >
      <ErrorNote error={attach.error ?? detach.error} />
      <div className="mb-3 flex flex-wrap items-end gap-2">
        <Field label="Attach an order" className="min-w-[18rem] flex-1">
          <Select value={pick} onChange={(e) => setPick(Number(e.target.value))}>
            <option value="">— select a purchase order —</option>
            {attachable.map((o) => (
              <option key={o.id} value={o.id}>
                {o.po_number} · {o.supplier_name} · {money(o.total_amount, o.currency)}
              </option>
            ))}
          </Select>
        </Field>
        <Button disabled={!pick || attach.isPending} onClick={() => attach.mutate()}>
          <Link2 className="h-3.5 w-3.5" /> Attach
        </Button>
      </div>

      {attached.length === 0 ? (
        <Empty message="No purchase orders attached yet — attach at least one before allocating costs." />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-line">
          <table className="w-full min-w-[560px] text-sm">
            <thead className="border-b border-line bg-surface-50 text-left text-[11px] uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-2.5 py-2">Order</th>
                <th className="px-2.5 py-2">Supplier</th>
                <th className="px-2.5 py-2">Status</th>
                <th className="px-2.5 py-2 text-right">Goods (RWF)</th>
                <th className="px-2.5 py-2" />
              </tr>
            </thead>
            <tbody>
              {attached.map((o) => (
                <tr key={o.id} className="border-b border-line last:border-0">
                  <td className="px-2.5 py-2 font-mono">{o.po_number}</td>
                  <td className="px-2.5 py-2">{o.supplier_name}</td>
                  <td className="px-2.5 py-2">
                    <StatusBadge status={o.status} label={o.status_display} />
                  </td>
                  <td className="px-2.5 py-2 text-right tabular-nums">
                    {money(o.total_amount_base)}
                  </td>
                  <td className="px-2.5 py-2 text-right">
                    <button
                      onClick={() => detach.mutate(o.id)}
                      className="rounded-md p-1.5 text-ink-500 hover:bg-red-50 hover:text-red-600"
                      aria-label="Detach order"
                    >
                      <Unlink className="h-3.5 w-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  );
}

/* -------------------------------------------------------------------------- */

function ConsignmentDrawer({
  consignment,
  onClose,
}: {
  consignment: ImportConsignment | null;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const { orgId } = useDefaultOrg();
  const [draft, setDraft] = useState<Draft>(
    consignment
      ? { ...consignment }
      : {
          supplier: null,
          status: "DRAFT",
          mode: "SEA",
          incoterm: "CIF",
          currency: "USD",
          exchange_rate: "1.000000",
          allocation_basis: "VALUE",
        },
  );
  const [result, setResult] = useState<LandedCostAllocationResult | null>(null);
  const set = (patch: Partial<Draft>) => setDraft((d) => ({ ...d, ...patch }));

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["consignments"] });
    void qc.invalidateQueries({ queryKey: ["procurement-overview"] });
  };

  const save = useMutation({
    mutationFn: () =>
      api<ImportConsignment>(
        consignment
          ? `/api/procurement/consignments/${consignment.id}/`
          : "/api/procurement/consignments/",
        {
          method: consignment ? "PATCH" : "POST",
          body: JSON.stringify({
            organization: orgId,
            supplier: draft.supplier,
            status: draft.status,
            mode: draft.mode,
            incoterm: draft.incoterm ?? "",
            currency: draft.currency,
            exchange_rate: draft.exchange_rate,
            proforma_number: draft.proforma_number ?? "",
            proforma_date: draft.proforma_date || null,
            proforma_amount: draft.proforma_amount ?? "0",
            proforma_document_url: draft.proforma_document_url ?? "",
            bill_of_lading_number: draft.bill_of_lading_number ?? "",
            bill_of_lading_date: draft.bill_of_lading_date || null,
            airway_bill_number: draft.airway_bill_number ?? "",
            vessel_or_flight: draft.vessel_or_flight ?? "",
            container_numbers: draft.container_numbers ?? "",
            carrier: draft.carrier ?? "",
            port_of_loading: draft.port_of_loading ?? "",
            port_of_discharge: draft.port_of_discharge ?? "",
            country_of_origin: draft.country_of_origin ?? "",
            gross_weight_kg: draft.gross_weight_kg ?? "0",
            packages_count: Number(draft.packages_count ?? 0),
            etd: draft.etd || null,
            eta: draft.eta || null,
            arrived_on: draft.arrived_on || null,
            customs_declaration_number: draft.customs_declaration_number ?? "",
            customs_office: draft.customs_office ?? "",
            customs_cleared_on: draft.customs_cleared_on || null,
            clearing_agent: draft.clearing_agent ?? "",
            clearing_agent_contact: draft.clearing_agent_contact ?? "",
            hs_code_summary: draft.hs_code_summary ?? "",
            insurance_policy_number: draft.insurance_policy_number ?? "",
            insurer_name: draft.insurer_name ?? "",
            insured_value: draft.insured_value ?? "0",
            allocation_basis: draft.allocation_basis,
            notes: draft.notes ?? "",
          }),
        },
      ),
    onSuccess: () => {
      invalidate();
      if (!consignment) onClose();
    },
  });

  const allocate = useMutation({
    mutationFn: () =>
      api<LandedCostAllocationResult>(
        `/api/procurement/consignments/${consignment!.id}/allocate_costs/`,
        {
          method: "POST",
          body: JSON.stringify({ allocation_basis: draft.allocation_basis }),
        },
      ),
    onSuccess: (data) => {
      setResult(data);
      invalidate();
    },
  });

  return (
    <Drawer
      title={consignment ? consignment.reference : "New import consignment"}
      badge={
        consignment && (
          <StatusBadge status={consignment.status} label={consignment.status_display} />
        )
      }
      subtitle={
        consignment
          ? `${consignment.supplier_name} · ${consignment.mode} · ${consignment.order_numbers.join(", ") || "no orders attached"}`
          : "Track the shipment's documents and every cost of bringing it in."
      }
      onClose={onClose}
      width="max-w-5xl"
      footer={
        <>
          {consignment && (
            <Button
              variant="secondary"
              disabled={allocate.isPending}
              onClick={() => allocate.mutate()}
            >
              <Calculator className="h-3.5 w-3.5" />
              {allocate.isPending ? "Allocating…" : "Allocate landed cost"}
            </Button>
          )}
          <Button disabled={save.isPending || !draft.supplier} onClick={() => save.mutate()}>
            {save.isPending ? "Saving…" : consignment ? "Save changes" : "Create consignment"}
          </Button>
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
        </>
      }
    >
      <ErrorNote error={save.error ?? allocate.error} />

      {consignment && (
        <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded-lg border border-line px-3 py-2">
            <div className="text-[11px] uppercase tracking-wide text-ink-500">Goods (RWF)</div>
            <div className="text-lg font-semibold tabular-nums">
              {money(consignment.goods_value_base)}
            </div>
          </div>
          <div className="rounded-lg border border-line px-3 py-2">
            <div className="text-[11px] uppercase tracking-wide text-ink-500">Landed cost</div>
            <div className="text-lg font-semibold tabular-nums">
              {money(consignment.landed_cost_total)}
            </div>
          </div>
          <div className="rounded-lg border border-line px-3 py-2">
            <div className="text-[11px] uppercase tracking-wide text-ink-500">Total landed</div>
            <div className="text-lg font-semibold tabular-nums">
              {money(consignment.total_landed_value)}
            </div>
          </div>
          <div className="rounded-lg border border-line px-3 py-2">
            <div className="text-[11px] uppercase tracking-wide text-ink-500">Cost uplift</div>
            <div className="text-lg font-semibold tabular-nums">
              {Number(consignment.uplift_pct).toFixed(1)}%
            </div>
          </div>
        </div>
      )}

      <Section title="Shipment">
        <Grid cols={4}>
          <Field label="Supplier" className="sm:col-span-2">
            <SupplierSelect value={draft.supplier} onChange={(id) => set({ supplier: id })} />
          </Field>
          <Field label="Status">
            <Select value={draft.status} onChange={(e) => set({ status: e.target.value as never })}>
              {STATUSES.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Mode">
            <Select value={draft.mode} onChange={(e) => set({ mode: e.target.value })}>
              {MODES.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Incoterm">
            <Select
              value={draft.incoterm ?? ""}
              onChange={(e) => set({ incoterm: e.target.value })}
            >
              <option value="">—</option>
              {INCOTERMS.map((i) => (
                <option key={i} value={i}>
                  {i}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Currency">
            <Input
              maxLength={3}
              value={draft.currency ?? ""}
              onChange={(e) => set({ currency: e.target.value.toUpperCase() })}
            />
          </Field>
          <Field label="Rate to RWF">
            <Input
              type="number"
              step="0.000001"
              value={draft.exchange_rate ?? ""}
              onChange={(e) => set({ exchange_rate: e.target.value })}
            />
          </Field>
          <Field label="Country of origin">
            <Input
              value={draft.country_of_origin ?? ""}
              onChange={(e) => set({ country_of_origin: e.target.value })}
            />
          </Field>
        </Grid>
      </Section>

      <Section title="Proforma invoice" hint="The supplier's pre-shipment commitment.">
        <Grid cols={4}>
          <Field label="Proforma number">
            <Input
              value={draft.proforma_number ?? ""}
              onChange={(e) => set({ proforma_number: e.target.value })}
            />
          </Field>
          <Field label="Proforma date">
            <Input
              type="date"
              value={draft.proforma_date ?? ""}
              onChange={(e) => set({ proforma_date: e.target.value })}
            />
          </Field>
          <Field label="Proforma amount">
            <Input
              type="number"
              step="0.01"
              value={draft.proforma_amount ?? ""}
              onChange={(e) => set({ proforma_amount: e.target.value })}
            />
          </Field>
          <Field label="Document URL">
            <Input
              value={draft.proforma_document_url ?? ""}
              onChange={(e) => set({ proforma_document_url: e.target.value })}
            />
          </Field>
        </Grid>
      </Section>

      <Section title="Transport documents">
        <Grid cols={4}>
          <Field label="Bill of lading">
            <Input
              value={draft.bill_of_lading_number ?? ""}
              onChange={(e) => set({ bill_of_lading_number: e.target.value })}
            />
          </Field>
          <Field label="B/L date">
            <Input
              type="date"
              value={draft.bill_of_lading_date ?? ""}
              onChange={(e) => set({ bill_of_lading_date: e.target.value })}
            />
          </Field>
          <Field label="Airway bill">
            <Input
              value={draft.airway_bill_number ?? ""}
              onChange={(e) => set({ airway_bill_number: e.target.value })}
            />
          </Field>
          <Field label="Vessel / flight">
            <Input
              value={draft.vessel_or_flight ?? ""}
              onChange={(e) => set({ vessel_or_flight: e.target.value })}
            />
          </Field>
          <Field label="Carrier">
            <Input value={draft.carrier ?? ""} onChange={(e) => set({ carrier: e.target.value })} />
          </Field>
          <Field label="Containers">
            <Input
              value={draft.container_numbers ?? ""}
              onChange={(e) => set({ container_numbers: e.target.value })}
            />
          </Field>
          <Field label="Port of loading">
            <Input
              value={draft.port_of_loading ?? ""}
              onChange={(e) => set({ port_of_loading: e.target.value })}
            />
          </Field>
          <Field label="Port of discharge">
            <Input
              value={draft.port_of_discharge ?? ""}
              onChange={(e) => set({ port_of_discharge: e.target.value })}
            />
          </Field>
          <Field label="Gross weight (kg)">
            <Input
              type="number"
              step="0.001"
              value={draft.gross_weight_kg ?? ""}
              onChange={(e) => set({ gross_weight_kg: e.target.value })}
            />
          </Field>
          <Field label="Packages">
            <Input
              type="number"
              value={draft.packages_count ?? 0}
              onChange={(e) => set({ packages_count: Number(e.target.value) })}
            />
          </Field>
          <Field label="ETD">
            <Input
              type="date"
              value={draft.etd ?? ""}
              onChange={(e) => set({ etd: e.target.value })}
            />
          </Field>
          <Field label="ETA">
            <Input
              type="date"
              value={draft.eta ?? ""}
              onChange={(e) => set({ eta: e.target.value })}
            />
          </Field>
        </Grid>
      </Section>

      <Section title="Customs & clearing">
        <Grid cols={4}>
          <Field label="Declaration number">
            <Input
              value={draft.customs_declaration_number ?? ""}
              onChange={(e) => set({ customs_declaration_number: e.target.value })}
            />
          </Field>
          <Field label="Customs office">
            <Input
              value={draft.customs_office ?? ""}
              onChange={(e) => set({ customs_office: e.target.value })}
            />
          </Field>
          <Field label="Arrived on">
            <Input
              type="date"
              value={draft.arrived_on ?? ""}
              onChange={(e) => set({ arrived_on: e.target.value })}
            />
          </Field>
          <Field label="Cleared on">
            <Input
              type="date"
              value={draft.customs_cleared_on ?? ""}
              onChange={(e) => set({ customs_cleared_on: e.target.value })}
            />
          </Field>
          <Field label="Clearing agent">
            <Input
              value={draft.clearing_agent ?? ""}
              onChange={(e) => set({ clearing_agent: e.target.value })}
            />
          </Field>
          <Field label="Agent contact">
            <Input
              value={draft.clearing_agent_contact ?? ""}
              onChange={(e) => set({ clearing_agent_contact: e.target.value })}
            />
          </Field>
          <Field label="HS codes" className="sm:col-span-2">
            <Input
              value={draft.hs_code_summary ?? ""}
              onChange={(e) => set({ hs_code_summary: e.target.value })}
            />
          </Field>
        </Grid>
      </Section>

      <Section title="Insurance">
        <Grid cols={3}>
          <Field label="Insurer">
            <Input
              value={draft.insurer_name ?? ""}
              onChange={(e) => set({ insurer_name: e.target.value })}
            />
          </Field>
          <Field label="Policy number">
            <Input
              value={draft.insurance_policy_number ?? ""}
              onChange={(e) => set({ insurance_policy_number: e.target.value })}
            />
          </Field>
          <Field label="Insured value">
            <Input
              type="number"
              step="0.01"
              value={draft.insured_value ?? ""}
              onChange={(e) => set({ insured_value: e.target.value })}
            />
          </Field>
        </Grid>
      </Section>

      {consignment && (
        <>
          <OrdersSection consignment={consignment} />
          <CostsSection consignment={consignment} />

          <Section
            title="Cost allocation"
            hint="How the pool is spread across the goods before it becomes unit cost."
          >
            <div className="flex flex-wrap items-end gap-3">
              <Field label="Basis">
                <Select
                  value={draft.allocation_basis}
                  onChange={(e) => set({ allocation_basis: e.target.value as never })}
                >
                  <option value="VALUE">By line value (default)</option>
                  <option value="QUANTITY">By quantity</option>
                </Select>
              </Field>
              <Button disabled={allocate.isPending} onClick={() => allocate.mutate()}>
                <Calculator className="h-3.5 w-3.5" />
                {allocate.isPending ? "Allocating…" : "Allocate into unit cost"}
              </Button>
              {consignment.costs_allocated_at && (
                <span className="text-xs text-ink-500">
                  Last allocated {new Date(consignment.costs_allocated_at).toLocaleString()}
                </span>
              )}
            </div>

            {result && (
              <div className="mt-3 overflow-x-auto rounded-lg border border-line">
                <table className="w-full min-w-[720px] text-sm">
                  <thead className="border-b border-line bg-surface-50 text-left text-[11px] uppercase tracking-wide text-ink-500">
                    <tr>
                      <th className="px-2.5 py-2">Order</th>
                      <th className="px-2.5 py-2">Product</th>
                      <th className="px-2.5 py-2 text-right">Qty</th>
                      <th className="px-2.5 py-2 text-right">Goods unit cost</th>
                      <th className="px-2.5 py-2 text-right">Allocated</th>
                      <th className="px-2.5 py-2 text-right">Landed unit cost</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.allocations.map((a) => (
                      <tr key={a.line_id} className="border-b border-line last:border-0">
                        <td className="px-2.5 py-2 font-mono text-xs">{a.order}</td>
                        <td className="px-2.5 py-2">{a.product}</td>
                        <td className="px-2.5 py-2 text-right tabular-nums">{a.quantity}</td>
                        <td className="px-2.5 py-2 text-right tabular-nums">
                          {money(a.goods_unit_cost)}
                        </td>
                        <td className="px-2.5 py-2 text-right tabular-nums">
                          {money(a.allocated)}
                        </td>
                        <td className="px-2.5 py-2 text-right font-semibold tabular-nums">
                          {money(a.landed_unit_cost)}
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

      <Section title="Notes">
        <Textarea value={draft.notes ?? ""} onChange={(e) => set({ notes: e.target.value })} />
      </Section>
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

export function ImportsPage() {
  const [open, setOpen] = useState<ImportConsignment | null>(null);
  const [creating, setCreating] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["consignments"],
    queryFn: () =>
      api<Paginated<ImportConsignment>>("/api/procurement/consignments/?page_size=200"),
  });

  const rows = data?.results ?? [];
  const current = open ? (rows.find((c) => c.id === open.id) ?? open) : null;

  return (
    <div>
      <PageHeader
        title="Imports & landed cost"
        action={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" /> New consignment
          </Button>
        }
      />

      <DataGrid<ImportConsignment>
        rows={rows}
        loading={isLoading}
        getRowId={(c) => c.id}
        storageKey="procurement-imports"
        exportName="import-consignments"
        searchPlaceholder="Search by reference, B/L, declaration, supplier…"
        emptyMessage="No import consignments yet."
        onRowClick={(c) => setOpen(c)}
        columns={[
          {
            key: "reference",
            header: "Consignment",
            render: (c) => (
              <div>
                <div className="font-mono font-medium text-ink-900">{c.reference}</div>
                <div className="text-xs text-ink-500">{c.supplier_name}</div>
              </div>
            ),
          },
          {
            key: "status",
            header: "Status",
            value: (c) => c.status,
            render: (c) => <StatusBadge status={c.status} label={c.status_display} />,
          },
          { key: "mode", header: "Mode", value: (c) => c.mode },
          {
            key: "bill_of_lading_number",
            header: "B/L or AWB",
            value: (c) => c.bill_of_lading_number || c.airway_bill_number || "—",
          },
          { key: "eta", header: "ETA", value: (c) => c.eta ?? "—" },
          {
            key: "goods_value_base",
            header: "Goods (RWF)",
            align: "right",
            numeric: true,
            value: (c) => Number(c.goods_value_base),
            render: (c) => money(c.goods_value_base),
          },
          {
            key: "landed_cost_total",
            header: "Landed cost",
            align: "right",
            numeric: true,
            value: (c) => Number(c.landed_cost_total),
            render: (c) => money(c.landed_cost_total),
          },
          {
            key: "uplift_pct",
            header: "Uplift",
            align: "right",
            numeric: true,
            value: (c) => Number(c.uplift_pct),
            render: (c) => {
              const v = Number(c.uplift_pct);
              return (
                <Badge tone={v > 30 ? "danger" : v > 15 ? "warning" : "neutral"}>
                  {v.toFixed(1)}%
                </Badge>
              );
            },
          },
          {
            key: "costs_allocated_at",
            header: "Costed",
            value: (c) => (c.costs_allocated_at ? "Yes" : "No"),
            render: (c) =>
              c.costs_allocated_at ? (
                <Badge tone="success">Allocated</Badge>
              ) : (
                <Badge tone="warning">Not costed</Badge>
              ),
          },
        ]}
      />

      {creating && <ConsignmentDrawer consignment={null} onClose={() => setCreating(false)} />}
      {current && <ConsignmentDrawer consignment={current} onClose={() => setOpen(null)} />}
    </div>
  );
}
