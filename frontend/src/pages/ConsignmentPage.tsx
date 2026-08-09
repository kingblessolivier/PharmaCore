import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Handshake, Pencil, Plus, Receipt, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import {
  Badge,
  Button,
  Card,
  ConfirmModal,
  PageHeader,
  SelectField,
  TextArea,
  TextField,
} from "../components/ui";
import { DataGrid } from "../components/DataGrid";
import { Drawer } from "../components/RecordKit";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type {
  ConsignmentAgreement,
  ConsignmentConsumption,
  ConsignmentSettlement,
  Paginated,
  Supplier,
} from "../lib/types";
import { StatusChip } from "../components/Status";

const BLANK = {
  agreement_no: "",
  direction: "SUPPLIER_OWNED" as ConsignmentAgreement["direction"],
  owner_supplier: 0,
  holder_name: "",
  status: "DRAFT" as ConsignmentAgreement["status"],
  start_date: new Date().toISOString().slice(0, 10),
  end_date: "",
  settlement_frequency: "MONTHLY" as ConsignmentAgreement["settlement_frequency"],
  title_transfer: "ON_CONSUMPTION" as ConsignmentAgreement["title_transfer"],
  payment_terms_days: 30,
  currency: "RWF",
  liability_holder: "OWNER" as ConsignmentAgreement["liability_holder"],
  credit_limit: "",
  terms: "",
};

function firstOfMonth(): string {
  const d = new Date();
  return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10);
}

export function ConsignmentPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { user } = useAuth();
  const orgId = user?.organization ?? 0;

  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<ConsignmentAgreement | null>(null);
  const [deleting, setDeleting] = useState<ConsignmentAgreement | null>(null);
  const [settling, setSettling] = useState<ConsignmentAgreement | null>(null);
  const [inspecting, setInspecting] = useState<ConsignmentAgreement | null>(null);
  const [form, setForm] = useState({ ...BLANK });
  const [error, setError] = useState("");
  const [period, setPeriod] = useState({
    period_start: firstOfMonth(),
    period_end: new Date().toISOString().slice(0, 10),
    raise_bill: true,
  });

  const agreementsQuery = useQuery({
    queryKey: ["consignments", orgId],
    queryFn: () =>
      api<Paginated<ConsignmentAgreement>>(`/api/inventory/consignments/?organization=${orgId}`),
    enabled: orgId > 0,
  });

  const suppliersQuery = useQuery({
    queryKey: ["suppliers", "for-consignment"],
    queryFn: () => api<Paginated<Supplier>>("/api/catalog/suppliers/?page_size=500"),
    enabled: creating || editing !== null,
  });

  const consumptionsQuery = useQuery({
    queryKey: ["consignment-consumptions", inspecting?.id],
    queryFn: () =>
      api<Paginated<ConsignmentConsumption>>(
        `/api/inventory/consignment-consumptions/?agreement=${inspecting!.id}`,
      ),
    enabled: inspecting !== null,
  });

  const settlementsQuery = useQuery({
    queryKey: ["consignment-settlements", orgId],
    queryFn: () => api<Paginated<ConsignmentSettlement>>("/api/inventory/consignment-settlements/"),
    enabled: orgId > 0,
  });

  const saveMutation = useMutation({
    mutationFn: () =>
      api<ConsignmentAgreement>(
        editing ? `/api/inventory/consignments/${editing.id}/` : "/api/inventory/consignments/",
        {
          method: editing ? "PATCH" : "POST",
          body: JSON.stringify({
            ...form,
            organization: orgId,
            owner_supplier: form.owner_supplier || null,
            end_date: form.end_date || null,
            credit_limit: form.credit_limit || null,
          }),
        },
      ),
    onSuccess: () => {
      close();
      void qc.invalidateQueries({ queryKey: ["consignments"] });
    },
    onError: (e: Error) => setError(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) =>
      api<void>(`/api/inventory/consignments/${id}/`, { method: "DELETE" }),
    onSuccess: () => {
      setDeleting(null);
      void qc.invalidateQueries({ queryKey: ["consignments"] });
    },
  });

  const settleMutation = useMutation({
    mutationFn: () =>
      api<ConsignmentSettlement>(`/api/inventory/consignments/${settling!.id}/settle/`, {
        method: "POST",
        body: JSON.stringify(period),
      }),
    onSuccess: () => {
      setSettling(null);
      void qc.invalidateQueries({ queryKey: ["consignments"] });
      void qc.invalidateQueries({ queryKey: ["consignment-settlements"] });
    },
    onError: (e: Error) => setError(e.message),
  });

  function close() {
    setCreating(false);
    setEditing(null);
    setError("");
    setForm({ ...BLANK });
  }

  function openEdit(a: ConsignmentAgreement) {
    setEditing(a);
    setForm({
      agreement_no: a.agreement_no,
      direction: a.direction,
      owner_supplier: a.owner_supplier ?? 0,
      holder_name: a.holder_name,
      status: a.status,
      start_date: a.start_date,
      end_date: a.end_date ?? "",
      settlement_frequency: a.settlement_frequency,
      title_transfer: a.title_transfer,
      payment_terms_days: a.payment_terms_days,
      currency: a.currency,
      liability_holder: a.liability_holder,
      credit_limit: a.credit_limit ?? "",
      terms: a.terms,
    });
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (form.agreement_no.trim()) saveMutation.mutate();
  }

  return (
    <div>
      <button
        onClick={() => navigate("/inventory")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> Inventory Home
      </button>

      <PageHeader
        title="Consignment & Vendor-Managed Inventory"
        action={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" /> New Agreement
          </Button>
        }
      />

      <DataGrid<ConsignmentAgreement>
        rows={agreementsQuery.data?.results ?? []}
        loading={agreementsQuery.isLoading}
        getRowId={(a) => a.id}
        storageKey="consignments"
        exportName="consignment-agreements"
        searchPlaceholder="Search by agreement number, counterparty or status…"
        emptyMessage="No consignment agreements yet."
        onRowClick={(a) => setInspecting(a)}
        columns={[
          {
            key: "agreement_no",
            header: "Agreement",
            render: (a) => (
              <span className="flex items-center gap-2 font-mono font-semibold text-ink-900">
                <Handshake className="h-4 w-4 text-brand-600" />
                {a.agreement_no}
              </span>
            ),
          },
          {
            key: "direction",
            header: "Direction",
            render: (a) => (
              <Badge tone={a.direction === "SUPPLIER_OWNED" ? "warning" : "neutral"}>
                {a.direction === "SUPPLIER_OWNED" ? "VMI in" : "VMI out"}
              </Badge>
            ),
          },
          { key: "counterparty_name", header: "Counterparty" },
          {
            key: "status",
            header: "Status",
            align: "center",
            render: (a) => <StatusChip status={a.status} />,
          },
          {
            key: "units_held",
            header: "Units Held",
            align: "right",
            numeric: true,
            value: (a) => a.position.units_held,
          },
          {
            key: "value_held",
            header: "Value Held",
            align: "right",
            numeric: true,
            value: (a) => Number(a.position.value_held),
            render: (a) => <span className="font-mono">{a.position.value_held}</span>,
          },
          {
            key: "unsettled_value",
            header: "Unsettled",
            align: "right",
            numeric: true,
            value: (a) => Number(a.position.unsettled_value),
            render: (a) => (
              <span
                className={`font-mono font-semibold ${
                  a.position.over_credit_limit ? "text-red-600" : ""
                }`}
              >
                {a.position.unsettled_value}
              </span>
            ),
          },
          { key: "settlement_frequency", header: "Settles" },
          {
            key: "actions",
            header: "Actions",
            align: "right",
            fixed: true,
            sortable: false,
            render: (a) => (
              <div className="flex justify-end gap-1">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setSettling(a);
                  }}
                  className="rounded-md p-1.5 text-ink-500 hover:bg-surface-100 hover:text-ink-900"
                  aria-label="Settle period"
                >
                  <Receipt className="h-4 w-4" />
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    openEdit(a);
                  }}
                  className="rounded-md p-1.5 text-ink-500 hover:bg-surface-100 hover:text-ink-900"
                  aria-label="Edit agreement"
                >
                  <Pencil className="h-4 w-4" />
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setDeleting(a);
                  }}
                  className="rounded-md p-1.5 text-ink-500 hover:bg-red-50 hover:text-red-600"
                  aria-label="Delete agreement"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ),
          },
        ]}
      />

      <h2 className="mb-2 mt-6 text-sm font-semibold text-ink-900">Settlements</h2>
      <DataGrid<ConsignmentSettlement>
        rows={settlementsQuery.data?.results ?? []}
        loading={settlementsQuery.isLoading}
        getRowId={(s) => s.id}
        storageKey="consignment-settlements"
        exportName="consignment-settlements"
        searchPlaceholder="Search settlements…"
        emptyMessage="No settlements raised yet."
        initialDensity="compact"
        columns={[
          {
            key: "settlement_no",
            header: "Settlement",
            render: (s) => <span className="font-mono">{s.settlement_no}</span>,
          },
          { key: "agreement_no", header: "Agreement" },
          { key: "counterparty_name", header: "Counterparty" },
          { key: "period", header: "Period", value: (s) => `${s.period_start} → ${s.period_end}` },
          {
            key: "lines_count",
            header: "Lines",
            align: "right",
            numeric: true,
            value: (s) => s.lines_count,
          },
          {
            key: "total_quantity",
            header: "Units",
            align: "right",
            numeric: true,
            value: (s) => s.total_quantity,
          },
          {
            key: "total_value",
            header: "Value",
            align: "right",
            numeric: true,
            value: (s) => Number(s.total_value),
            render: (s) => <span className="font-mono font-semibold">{s.total_value}</span>,
          },
          {
            key: "status",
            header: "Status",
            align: "center",
            render: (s) => <StatusChip status={s.status} />,
          },
          { key: "supplier_bill_no", header: "AP Bill", value: (s) => s.supplier_bill_no ?? "—" },
        ]}
      />

      {(creating || editing) && (
        <Drawer
          title={editing ? `Edit ${editing.agreement_no}` : "New Consignment Agreement"}
          onClose={close}
        >
          <form onSubmit={submit} className="flex flex-col gap-4">
            {error && (
              <div className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-700">{error}</div>
            )}
            <TextField
              label="Agreement Number"
              value={form.agreement_no}
              onChange={(e) => setForm({ ...form, agreement_no: e.target.value })}
              placeholder="e.g. VMI-2026-001"
              required
              autoFocus
            />
            <SelectField
              label="Direction"
              value={form.direction}
              onChange={(e) =>
                setForm({ ...form, direction: e.target.value as ConsignmentAgreement["direction"] })
              }
            >
              <option value="SUPPLIER_OWNED">Supplier-owned stock held by us (VMI in)</option>
              <option value="CUSTOMER_HELD">Our stock held at a customer (VMI out)</option>
            </SelectField>
            {form.direction === "SUPPLIER_OWNED" ? (
              <SelectField
                label="Owning Supplier"
                value={form.owner_supplier}
                onChange={(e) => setForm({ ...form, owner_supplier: Number(e.target.value) })}
              >
                <option value={0}>— Select supplier —</option>
                {(suppliersQuery.data?.results ?? []).map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </SelectField>
            ) : (
              <TextField
                label="Holding Site"
                value={form.holder_name}
                onChange={(e) => setForm({ ...form, holder_name: e.target.value })}
                placeholder="Name of the customer site holding our stock"
              />
            )}
            <div className="grid grid-cols-2 gap-3">
              <TextField
                label="Start Date"
                type="date"
                value={form.start_date}
                onChange={(e) => setForm({ ...form, start_date: e.target.value })}
                required
              />
              <TextField
                label="End Date"
                type="date"
                value={form.end_date}
                onChange={(e) => setForm({ ...form, end_date: e.target.value })}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <SelectField
                label="Status"
                value={form.status}
                onChange={(e) =>
                  setForm({ ...form, status: e.target.value as ConsignmentAgreement["status"] })
                }
              >
                <option value="DRAFT">Draft</option>
                <option value="ACTIVE">Active</option>
                <option value="SUSPENDED">Suspended</option>
                <option value="CLOSED">Closed</option>
              </SelectField>
              <SelectField
                label="Settlement Frequency"
                value={form.settlement_frequency}
                onChange={(e) =>
                  setForm({
                    ...form,
                    settlement_frequency: e.target
                      .value as ConsignmentAgreement["settlement_frequency"],
                  })
                }
              >
                <option value="ON_CONSUMPTION">On each consumption</option>
                <option value="WEEKLY">Weekly</option>
                <option value="FORTNIGHTLY">Fortnightly</option>
                <option value="MONTHLY">Monthly</option>
              </SelectField>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <SelectField
                label="Title Transfers"
                value={form.title_transfer}
                onChange={(e) =>
                  setForm({
                    ...form,
                    title_transfer: e.target.value as ConsignmentAgreement["title_transfer"],
                  })
                }
              >
                <option value="ON_CONSUMPTION">On consumption / sale</option>
                <option value="ON_RECEIPT">On receipt into the store</option>
                <option value="ON_PERIOD_END">At period end</option>
              </SelectField>
              <SelectField
                label="Liability Sits With"
                value={form.liability_holder}
                onChange={(e) =>
                  setForm({
                    ...form,
                    liability_holder: e.target.value as ConsignmentAgreement["liability_holder"],
                  })
                }
              >
                <option value="OWNER">Owner of the goods</option>
                <option value="HOLDER">Site holding the goods</option>
              </SelectField>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <TextField
                label="Payment Terms (days)"
                type="number"
                value={String(form.payment_terms_days)}
                onChange={(e) => setForm({ ...form, payment_terms_days: Number(e.target.value) })}
              />
              <TextField
                label="Currency"
                value={form.currency}
                onChange={(e) => setForm({ ...form, currency: e.target.value })}
              />
              <TextField
                label="Credit Limit"
                value={form.credit_limit}
                onChange={(e) => setForm({ ...form, credit_limit: e.target.value })}
                placeholder="optional"
              />
            </div>
            <TextArea
              label="Terms"
              value={form.terms}
              onChange={(e) => setForm({ ...form, terms: e.target.value })}
              rows={3}
            />
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={close}>
                Cancel
              </Button>
              <Button type="submit" disabled={saveMutation.isPending}>
                {saveMutation.isPending ? "Saving…" : editing ? "Save Changes" : "Create Agreement"}
              </Button>
            </div>
          </form>
        </Drawer>
      )}

      {settling && (
        <Drawer title={`Settle ${settling.agreement_no}`} onClose={() => setSettling(null)}>
          <div className="flex flex-col gap-4">
            {error && (
              <div className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-700">{error}</div>
            )}
            <p className="text-sm text-ink-600">
              Rolls every unsettled consumption in the period into one settlement. For
              supplier-owned stock this is where we finally owe the supplier — an AP bill is raised
              and posted to the GL.
            </p>
            <div className="grid grid-cols-2 gap-3">
              <TextField
                label="Period Start"
                type="date"
                value={period.period_start}
                onChange={(e) => setPeriod({ ...period, period_start: e.target.value })}
              />
              <TextField
                label="Period End"
                type="date"
                value={period.period_end}
                onChange={(e) => setPeriod({ ...period, period_end: e.target.value })}
              />
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={period.raise_bill}
                onChange={(e) => setPeriod({ ...period, raise_bill: e.target.checked })}
              />
              Raise the supplier bill and post it to the GL
            </label>
            <div className="rounded-md bg-surface-100 px-3 py-2 text-xs text-ink-600">
              Currently unsettled: {settling.position.unsettled_lines} lines ·{" "}
              {settling.position.unsettled_units} units ·{" "}
              <span className="font-mono">{settling.position.unsettled_value}</span>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setSettling(null)}>
                Cancel
              </Button>
              <Button onClick={() => settleMutation.mutate()} disabled={settleMutation.isPending}>
                {settleMutation.isPending ? "Settling…" : "Settle Period"}
              </Button>
            </div>
          </div>
        </Drawer>
      )}

      {inspecting && (
        <Drawer
          title={`${inspecting.agreement_no} — Consumption Ledger`}
          onClose={() => setInspecting(null)}
        >
          <Card className="mb-4 p-4 text-xs">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="text-ink-500">Held on site</div>
                <div className="font-mono text-sm font-semibold text-ink-900">
                  {inspecting.position.units_held} units · {inspecting.position.value_held}
                </div>
              </div>
              <div>
                <div className="text-ink-500">Unsettled liability</div>
                <div className="font-mono text-sm font-semibold text-ink-900">
                  {inspecting.position.unsettled_value}
                </div>
              </div>
            </div>
            {inspecting.position.over_credit_limit && (
              <div className="mt-3 rounded-md bg-red-50 px-3 py-2 text-red-700">
                Unsettled value has passed the agreed credit limit of{" "}
                {inspecting.position.credit_limit}.
              </div>
            )}
          </Card>
          <div className="max-h-72 overflow-y-auto">
            {(consumptionsQuery.data?.results ?? []).map((c) => (
              <div
                key={c.id}
                className="flex items-center justify-between border-b border-line py-2 text-xs"
              >
                <div>
                  <div className="font-semibold text-ink-900">{c.product_name}</div>
                  <div className="text-ink-500">
                    Batch {c.batch_number || "—"} · {c.consumed_at.slice(0, 10)} · {c.trigger}
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-mono font-semibold">{c.total_value}</div>
                  <div className="text-ink-500">
                    {c.quantity} × {c.unit_cost}
                  </div>
                  {c.settlement_no ? (
                    <Badge tone="success">{c.settlement_no}</Badge>
                  ) : (
                    <Badge tone="warning">unsettled</Badge>
                  )}
                </div>
              </div>
            ))}
            {(consumptionsQuery.data?.results ?? []).length === 0 && (
              <p className="text-sm text-ink-500">Nothing consumed under this agreement yet.</p>
            )}
          </div>
        </Drawer>
      )}

      {deleting && (
        <ConfirmModal
          title="Delete Agreement"
          message={`Delete ${deleting.agreement_no}? Consumptions recorded against it will be removed too.`}
          confirmLabel="Delete"
          busy={deleteMutation.isPending}
          onClose={() => setDeleting(null)}
          onConfirm={() => deleteMutation.mutate(deleting.id)}
        />
      )}
    </div>
  );
}
