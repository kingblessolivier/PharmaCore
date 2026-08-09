import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCheck, FileText, Plus, ScrollText, ShieldCheck } from "lucide-react";
import { useMemo, useState } from "react";
import { DataGrid } from "../components/DataGrid";
import {
  Drawer,
  Empty,
  ErrorNote,
  Facts,
  Field,
  Grid,
  Input,
  LineEditor,
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
import {
  NOTE_REASONS,
  money,
  num,
  type GoodsReceipt,
  type PurchaseOrder,
  type SupplierInvoice,
  type SupplierInvoiceLine,
  type SupplierStatement,
} from "../lib/procurement";
import type { Paginated } from "../lib/types";

const STATUS_FILTERS = [
  ["", "All"],
  ["DRAFT", "Draft"],
  ["MATCHED", "Matched"],
  ["VARIANCE", "Variance"],
  ["PENDING_APPROVAL", "Awaiting approval"],
  ["APPROVED", "Approved & posted"],
  ["REJECTED", "Rejected"],
] as const;

const emptyLine = (): SupplierInvoiceLine => ({
  order_line: null,
  product: null,
  description: "",
  quantity: "1",
  unit_price: "0.00",
  tax_rate_pct: "0.00",
});

/* -------------------------------------------------------------------------- */

function MatchPanel({ invoice }: { invoice: SupplierInvoice }) {
  if (invoice.match_result === "NOT_RUN") {
    return (
      <Empty message="Not matched yet — run the 3-way match to compare against the PO and GRN." />
    );
  }
  const clean = invoice.match_result === "MATCHED";
  return (
    <>
      <div
        className={`mb-3 rounded-md border px-3 py-2 text-sm ${
          clean
            ? "border-green-200 bg-green-50 text-green-800"
            : "border-amber-200 bg-amber-50 text-amber-900"
        }`}
      >
        <span className="font-semibold">{invoice.match_result_display}.</span>{" "}
        {clean
          ? "Quantities and prices agree with the purchase order and goods receipt."
          : "This invoice cannot be submitted without an override reason someone will be accountable for."}
      </div>
      <div className="overflow-x-auto rounded-lg border border-line">
        <table className="w-full min-w-[720px] text-sm">
          <thead className="border-b border-line bg-surface-50 text-left text-[11px] text-ink-500">
            <tr>
              <th className="px-2.5 py-2">Product</th>
              <th className="px-2.5 py-2 text-right">Ordered</th>
              <th className="px-2.5 py-2 text-right">Received</th>
              <th className="px-2.5 py-2 text-right">Invoiced</th>
              <th className="px-2.5 py-2 text-right">PO price</th>
              <th className="px-2.5 py-2 text-right">Invoice price</th>
              <th className="px-2.5 py-2">Result</th>
            </tr>
          </thead>
          <tbody>
            {invoice.match_detail.map((row, i) => (
              <tr key={i} className="border-b border-line last:border-0">
                <td className="px-2.5 py-2">{row.product ?? "—"}</td>
                <td className="px-2.5 py-2 text-right tabular-nums">{row.ordered_qty ?? "—"}</td>
                <td className="px-2.5 py-2 text-right tabular-nums">{row.received_qty ?? "—"}</td>
                <td className="px-2.5 py-2 text-right tabular-nums">{row.invoiced_qty ?? "—"}</td>
                <td className="px-2.5 py-2 text-right tabular-nums">{row.order_price ?? "—"}</td>
                <td className="px-2.5 py-2 text-right tabular-nums">{row.invoiced_price ?? "—"}</td>
                <td className="px-2.5 py-2">
                  {row.issue === "OK" ? (
                    <Badge tone="success">Matched</Badge>
                  ) : (
                    <div>
                      <Badge tone="danger">{row.issue.replaceAll("_", " ")}</Badge>
                      <div className="mt-0.5 text-xs text-ink-600">{row.message}</div>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

/* -------------------------------------------------------------------------- */

function NotesPanel({ invoice }: { invoice: SupplierInvoice }) {
  const qc = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({
    kind: "DEBIT",
    reason: "SHORT_SHIPMENT",
    note_date: new Date().toISOString().slice(0, 10),
    amount: "",
    tax_amount: "0.00",
    description: "",
  });

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["supplier-invoices"] });
    void qc.invalidateQueries({ queryKey: ["supplier-notes"] });
  };

  const create = useMutation({
    mutationFn: () =>
      api<{ id: number }>("/api/procurement/supplier-notes/", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          organization: invoice.organization,
          supplier: invoice.supplier,
          invoice: invoice.id,
          currency: invoice.currency,
        }),
      }),
    onSuccess: () => {
      setAdding(false);
      setForm({ ...form, amount: "", description: "" });
      refresh();
    },
  });

  const issue = useMutation({
    mutationFn: (id: number) =>
      api(`/api/procurement/supplier-notes/${id}/issue/`, { method: "POST", body: "{}" }),
    onSuccess: refresh,
  });

  return (
    <Section
      title="Debit & credit notes"
      hint="A debit note charges the supplier (short-ship, damage); a credit note is what they allow us. Both reduce the payable."
      action={
        <Button variant="secondary" onClick={() => setAdding((a) => !a)}>
          <Plus className="h-3.5 w-3.5" /> {adding ? "Cancel" : "Raise a note"}
        </Button>
      }
    >
      {adding && (
        <div className="mb-3 rounded-lg border border-line bg-surface-50 p-3">
          <ErrorNote error={create.error} />
          <Grid cols={4}>
            <Field label="Type">
              <Select
                value={form.kind}
                onChange={(e) => setForm({ ...form, kind: e.target.value })}
              >
                <option value="DEBIT">Debit note (we charge them)</option>
                <option value="CREDIT">Credit note (they credit us)</option>
              </Select>
            </Field>
            <Field label="Reason">
              <Select
                value={form.reason}
                onChange={(e) => setForm({ ...form, reason: e.target.value })}
              >
                {NOTE_REASONS.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
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
            <Field label="Tax">
              <Input
                type="number"
                step="0.01"
                value={form.tax_amount}
                onChange={(e) => setForm({ ...form, tax_amount: e.target.value })}
              />
            </Field>
            <Field label="Date">
              <Input
                type="date"
                value={form.note_date}
                onChange={(e) => setForm({ ...form, note_date: e.target.value })}
              />
            </Field>
            <Field label="Description" className="sm:col-span-3">
              <Input
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="e.g. 5 packs crushed in transit"
              />
            </Field>
          </Grid>
          <div className="mt-3 flex justify-end">
            <Button disabled={!form.amount || create.isPending} onClick={() => create.mutate()}>
              {create.isPending ? "Saving…" : "Save draft note"}
            </Button>
          </div>
        </div>
      )}

      {invoice.notes_issued.length === 0 ? (
        <Empty message="No notes raised against this invoice." />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-line">
          <table className="w-full min-w-[620px] text-sm">
            <thead className="border-b border-line bg-surface-50 text-left text-[11px] text-ink-500">
              <tr>
                <th className="px-2.5 py-2">Note</th>
                <th className="px-2.5 py-2">Reason</th>
                <th className="px-2.5 py-2">Status</th>
                <th className="px-2.5 py-2 text-right">Amount</th>
                <th className="px-2.5 py-2" />
              </tr>
            </thead>
            <tbody>
              {invoice.notes_issued.map((n) => (
                <tr key={n.id} className="border-b border-line last:border-0">
                  <td className="px-2.5 py-2">
                    <div className="font-mono">{n.note_number}</div>
                    <div className="text-xs text-ink-500">{n.kind_display}</div>
                  </td>
                  <td className="px-2.5 py-2">
                    {n.reason_display}
                    {n.description && <div className="text-xs text-ink-500">{n.description}</div>}
                  </td>
                  <td className="px-2.5 py-2">
                    <StatusBadge status={n.status} />
                  </td>
                  <td className="px-2.5 py-2 text-right tabular-nums">
                    {money(n.total_amount, n.currency)}
                  </td>
                  <td className="px-2.5 py-2 text-right">
                    {n.status === "DRAFT" && (
                      <Button disabled={issue.isPending} onClick={() => issue.mutate(n.id)}>
                        Issue
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot className="border-t border-line bg-surface-50">
              <tr>
                <td colSpan={3} className="px-2.5 py-1.5 text-right font-semibold">
                  Net payable after notes
                </td>
                <td className="px-2.5 py-1.5 text-right font-semibold tabular-nums">
                  {money(invoice.payable_amount, invoice.currency)}
                </td>
                <td />
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </Section>
  );
}

/* -------------------------------------------------------------------------- */

function InvoiceDrawer({
  invoice,
  onClose,
}: {
  invoice: SupplierInvoice | null;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const { orgId } = useDefaultOrg();
  const editable = invoice === null || invoice.is_editable;
  const [tab, setTab] = useState<"invoice" | "match" | "notes">("invoice");
  const [override, setOverride] = useState(invoice?.override_reason ?? "");
  const [form, setForm] = useState({
    supplier: invoice?.supplier ?? null,
    order: invoice?.order ?? null,
    receipt: invoice?.receipt ?? null,
    invoice_number: invoice?.invoice_number ?? "",
    invoice_date: invoice?.invoice_date ?? new Date().toISOString().slice(0, 10),
    due_date: invoice?.due_date ?? "",
    currency: invoice?.currency ?? "RWF",
    exchange_rate: invoice?.exchange_rate ?? "1.000000",
    freight_amount: invoice?.freight_amount ?? "0.00",
    other_charges: invoice?.other_charges ?? "0.00",
    discount_amount: invoice?.discount_amount ?? "0.00",
    tax_class: invoice?.tax_class ?? "",
    qty_tolerance_pct: invoice?.qty_tolerance_pct ?? "0.00",
    price_tolerance_pct: invoice?.price_tolerance_pct ?? "1.00",
    notes: invoice?.notes ?? "",
    lines: invoice?.lines?.length ? invoice.lines.map((l) => ({ ...l })) : [emptyLine()],
  });

  const { data: orders = [] } = useQuery({
    queryKey: ["purchase-orders", "invoiceable"],
    queryFn: () => api<Paginated<PurchaseOrder>>("/api/procurement/orders/?page_size=200"),
    select: (r) => r.results,
  });
  const { data: receipts = [] } = useQuery({
    queryKey: ["goods-receipts", "for-invoice", form.order],
    enabled: Boolean(form.order),
    queryFn: () =>
      api<Paginated<GoodsReceipt>>(`/api/procurement/receipts/?order=${form.order}&page_size=50`),
    select: (r) => r.results.filter((x) => x.status === "POSTED"),
  });

  const selectedOrder = orders.find((o) => o.id === form.order);
  const supplierOrders = orders.filter((o) => !form.supplier || o.supplier === form.supplier);

  const totals = useMemo(() => {
    const goods = form.lines.reduce(
      (s, l) => s + ((num(l.unit_price) * (100 - num(l.discount_pct))) / 100) * num(l.quantity),
      0,
    );
    const tax = form.lines.reduce((s, l) => {
      const sub = ((num(l.unit_price) * (100 - num(l.discount_pct))) / 100) * num(l.quantity);
      return s + (sub * num(l.tax_rate_pct)) / 100;
    }, 0);
    const net =
      goods + num(form.freight_amount) + num(form.other_charges) - num(form.discount_amount);
    return { goods, tax, net, total: net + tax };
  }, [form]);

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["supplier-invoices"] });
    void qc.invalidateQueries({ queryKey: ["procurement-overview"] });
  };

  const loadFromOrder = () => {
    if (!selectedOrder) return;
    setForm({
      ...form,
      currency: selectedOrder.currency,
      exchange_rate: selectedOrder.exchange_rate,
      lines: selectedOrder.lines.map((l) => ({
        order_line: l.id ?? null,
        product: l.product,
        description: "",
        quantity: String(l.quantity_received || l.quantity_ordered),
        unit_price: l.unit_price,
        discount_pct: l.discount_pct ?? "0.00",
        tax_rate_pct: l.tax_rate_pct ?? "0.00",
      })),
    });
  };

  const save = useMutation({
    mutationFn: () =>
      api<SupplierInvoice>(
        invoice ? `/api/procurement/invoices/${invoice.id}/` : "/api/procurement/invoices/",
        {
          method: invoice ? "PATCH" : "POST",
          body: JSON.stringify({
            organization: orgId,
            supplier: form.supplier,
            order: form.order,
            receipt: form.receipt,
            invoice_number: form.invoice_number,
            invoice_date: form.invoice_date,
            due_date: form.due_date || null,
            currency: form.currency,
            exchange_rate: form.exchange_rate,
            freight_amount: form.freight_amount || "0",
            other_charges: form.other_charges || "0",
            discount_amount: form.discount_amount || "0",
            tax_class: form.tax_class,
            qty_tolerance_pct: form.qty_tolerance_pct || "0",
            price_tolerance_pct: form.price_tolerance_pct || "0",
            notes: form.notes,
            lines: form.lines
              .filter((l) => num(l.quantity) > 0)
              .map((l) => ({
                order_line: l.order_line ?? null,
                product: l.product ?? null,
                description: l.description ?? "",
                quantity: l.quantity,
                unit_price: l.unit_price || "0",
                discount_pct: l.discount_pct ?? "0",
                tax_rate_pct: l.tax_rate_pct ?? "0",
              })),
          }),
        },
      ),
    onSuccess: (saved) => {
      invalidate();
      if (!invoice) onClose();
      else if (saved) setTab("match");
    },
  });

  const match = useMutation({
    mutationFn: () =>
      api<SupplierInvoice>(`/api/procurement/invoices/${invoice!.id}/match/`, {
        method: "POST",
        body: "{}",
      }),
    onSuccess: () => {
      invalidate();
      setTab("match");
    },
  });

  const submit = useMutation({
    mutationFn: () =>
      api(`/api/procurement/invoices/${invoice!.id}/submit/`, {
        method: "POST",
        body: JSON.stringify({ override_reason: override }),
      }),
    onSuccess: () => {
      invalidate();
      onClose();
    },
  });

  const tabs: [typeof tab, string][] = [
    ["invoice", "Invoice"],
    ["match", "3-way match"],
    ["notes", "Notes"],
  ];

  return (
    <Drawer
      title={
        invoice ? `${invoice.invoice_number} · ${invoice.supplier_name}` : "New supplier invoice"
      }
      badge={invoice && <StatusBadge status={invoice.status} label={invoice.status_display} />}
      subtitle={
        invoice
          ? `${invoice.internal_number || "—"} · ${invoice.po_number ?? "no PO"} · ${invoice.grn_number ?? "no GRN"}`
          : "Register what the supplier billed, then match it against the order and the goods receipt."
      }
      onClose={onClose}
      width="max-w-5xl"
      footer={
        <>
          {invoice && ["DRAFT", "MATCHED", "VARIANCE"].includes(invoice.status) && (
            <Button variant="secondary" disabled={match.isPending} onClick={() => match.mutate()}>
              <CheckCheck className="h-3.5 w-3.5" />
              {match.isPending ? "Matching…" : "Run 3-way match"}
            </Button>
          )}
          {invoice && ["DRAFT", "MATCHED", "VARIANCE"].includes(invoice.status) && (
            <Button disabled={submit.isPending} onClick={() => submit.mutate()}>
              <ShieldCheck className="h-3.5 w-3.5" /> Submit for approval
            </Button>
          )}
          {editable && (
            <Button
              disabled={save.isPending || !form.supplier || !form.invoice_number.trim()}
              onClick={() => save.mutate()}
            >
              {save.isPending ? "Saving…" : invoice ? "Save changes" : "Create invoice"}
            </Button>
          )}
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
        </>
      }
    >
      <ErrorNote error={save.error ?? match.error ?? submit.error} />

      {invoice && (
        <div className="mb-4 flex gap-1 border-b border-line">
          {tabs.map(([key, label]) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`-mb-px border-b-2 px-3 py-2 text-sm ${
                tab === key
                  ? "border-brand-600 font-semibold text-brand-700"
                  : "border-transparent text-ink-600 hover:text-ink-900"
              }`}
            >
              {label}
              {key === "notes" && invoice.notes_issued.length > 0 && (
                <span className="ml-1 text-xs text-ink-500">({invoice.notes_issued.length})</span>
              )}
            </button>
          ))}
        </div>
      )}

      {(!invoice || tab === "invoice") && (
        <>
          {invoice?.status === "APPROVED" && (
            <div className="mb-4 rounded-md border border-line bg-surface-50 p-3">
              <Facts
                rows={[
                  ["Approved by", invoice.approved_by_name ?? "—"],
                  [
                    "Approved at",
                    invoice.approved_at ? new Date(invoice.approved_at).toLocaleString() : "—",
                  ],
                  ["Posted as bill", invoice.finance_bill ? `#${invoice.finance_bill}` : "—"],
                  ["Override reason", invoice.override_reason || "none"],
                ]}
              />
            </div>
          )}

          <Section title="Invoice">
            <Grid cols={4}>
              <Field label="Supplier">
                <SupplierSelect
                  value={form.supplier}
                  disabled={!editable}
                  onChange={(id) => setForm({ ...form, supplier: id, order: null, receipt: null })}
                />
              </Field>
              <Field label="Their invoice number">
                <Input
                  disabled={!editable}
                  value={form.invoice_number}
                  onChange={(e) => setForm({ ...form, invoice_number: e.target.value })}
                />
              </Field>
              <Field label="Invoice date">
                <Input
                  type="date"
                  disabled={!editable}
                  value={form.invoice_date}
                  onChange={(e) => setForm({ ...form, invoice_date: e.target.value })}
                />
              </Field>
              <Field label="Due date">
                <Input
                  type="date"
                  disabled={!editable}
                  value={form.due_date}
                  onChange={(e) => setForm({ ...form, due_date: e.target.value })}
                />
              </Field>
              <Field label="Purchase order" className="sm:col-span-2">
                <Select
                  disabled={!editable}
                  value={form.order ?? ""}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      order: e.target.value ? Number(e.target.value) : null,
                      receipt: null,
                    })
                  }
                >
                  <option value="">— none (expense invoice) —</option>
                  {supplierOrders.map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.po_number} · {o.supplier_name} · {money(o.total_amount, o.currency)}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Goods receipt" hint="What the quantity match compares against.">
                <Select
                  disabled={!editable || !form.order}
                  value={form.receipt ?? ""}
                  onChange={(e) =>
                    setForm({ ...form, receipt: e.target.value ? Number(e.target.value) : null })
                  }
                >
                  <option value="">— none —</option>
                  {receipts.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.grn_number} · {r.total_received} units
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Tax class">
                <Select
                  disabled={!editable}
                  value={form.tax_class}
                  onChange={(e) => setForm({ ...form, tax_class: e.target.value })}
                >
                  <option value="">—</option>
                  <option value="A">A — Exempt</option>
                  <option value="B">B — Standard 18%</option>
                  <option value="C">C — Zero-rated</option>
                  <option value="D">D — Special</option>
                </Select>
              </Field>
              <Field label="Currency">
                <Input
                  maxLength={3}
                  disabled={!editable}
                  value={form.currency}
                  onChange={(e) => setForm({ ...form, currency: e.target.value.toUpperCase() })}
                />
              </Field>
              <Field label="Rate to RWF">
                <Input
                  type="number"
                  step="0.000001"
                  disabled={!editable}
                  value={form.exchange_rate}
                  onChange={(e) => setForm({ ...form, exchange_rate: e.target.value })}
                />
              </Field>
              <Field
                label="Qty tolerance %"
                hint="Difference accepted before it counts as a variance."
              >
                <Input
                  type="number"
                  step="0.01"
                  disabled={!editable}
                  value={form.qty_tolerance_pct}
                  onChange={(e) => setForm({ ...form, qty_tolerance_pct: e.target.value })}
                />
              </Field>
              <Field label="Price tolerance %">
                <Input
                  type="number"
                  step="0.01"
                  disabled={!editable}
                  value={form.price_tolerance_pct}
                  onChange={(e) => setForm({ ...form, price_tolerance_pct: e.target.value })}
                />
              </Field>
            </Grid>
          </Section>

          <Section
            title="Lines"
            hint="Link each line to its purchase-order line so the match can compare prices."
            action={
              editable &&
              selectedOrder && (
                <Button variant="secondary" onClick={loadFromOrder}>
                  <FileText className="h-3.5 w-3.5" /> Pull lines from {selectedOrder.po_number}
                </Button>
              )
            }
          >
            <LineEditor<SupplierInvoiceLine>
              rows={form.lines}
              readOnly={!editable}
              onChange={(lines) => setForm({ ...form, lines })}
              makeRow={emptyLine}
              addLabel="Add line"
              columns={[
                {
                  header: "PO line",
                  width: "28%",
                  cell: (row, set) =>
                    editable ? (
                      <Select
                        value={row.order_line ?? ""}
                        onChange={(e) => {
                          const id = e.target.value ? Number(e.target.value) : null;
                          const poLine = selectedOrder?.lines.find((l) => l.id === id);
                          set({
                            order_line: id,
                            product: poLine?.product ?? row.product ?? null,
                            unit_price: poLine?.unit_price ?? row.unit_price,
                          });
                        }}
                      >
                        <option value="">— unlinked —</option>
                        {(selectedOrder?.lines ?? []).map((l) => (
                          <option key={l.id} value={l.id}>
                            {l.product_name} · ordered {l.quantity_ordered}
                          </option>
                        ))}
                      </Select>
                    ) : (
                      <>{row.product_name ?? row.description ?? "—"}</>
                    ),
                },
                {
                  header: "Description",
                  width: "20%",
                  cell: (row, set) =>
                    editable ? (
                      <Input
                        value={row.description ?? ""}
                        onChange={(e) => set({ description: e.target.value })}
                        placeholder="As printed on the invoice"
                      />
                    ) : (
                      <>{row.description || "—"}</>
                    ),
                },
                {
                  header: "Qty",
                  width: "11%",
                  align: "right",
                  cell: (row, set) =>
                    editable ? (
                      <Input
                        type="number"
                        step="0.01"
                        value={row.quantity}
                        onChange={(e) => set({ quantity: e.target.value })}
                        className="text-right"
                      />
                    ) : (
                      <>{row.quantity}</>
                    ),
                },
                {
                  header: "Unit price",
                  width: "13%",
                  align: "right",
                  cell: (row, set) =>
                    editable ? (
                      <Input
                        type="number"
                        step="0.01"
                        value={row.unit_price}
                        onChange={(e) => set({ unit_price: e.target.value })}
                        className="text-right"
                      />
                    ) : (
                      <>{row.unit_price}</>
                    ),
                },
                {
                  header: "VAT %",
                  width: "10%",
                  align: "right",
                  cell: (row, set) =>
                    editable ? (
                      <Input
                        type="number"
                        step="0.01"
                        value={row.tax_rate_pct ?? "0"}
                        onChange={(e) => set({ tax_rate_pct: e.target.value })}
                        className="text-right"
                      />
                    ) : (
                      <>{row.tax_rate_pct}</>
                    ),
                },
                {
                  header: "Line total",
                  width: "18%",
                  align: "right",
                  cell: (row) => {
                    const sub =
                      ((num(row.unit_price) * (100 - num(row.discount_pct))) / 100) *
                      num(row.quantity);
                    const total = sub + (sub * num(row.tax_rate_pct)) / 100;
                    return (
                      <span className="font-medium">
                        {total.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                      </span>
                    );
                  },
                },
              ]}
              footer={
                <>
                  <TotalsRow span={5} label="Goods" value={totals.goods.toFixed(2)} />
                  <TotalsRow span={5} label="VAT" value={totals.tax.toFixed(2)} />
                  <TotalsRow
                    span={5}
                    label={`Total (${form.currency})`}
                    value={totals.total.toFixed(2)}
                    strong
                  />
                </>
              }
            />
            <Grid cols={3}>
              <Field label="Freight">
                <Input
                  type="number"
                  step="0.01"
                  disabled={!editable}
                  value={form.freight_amount}
                  onChange={(e) => setForm({ ...form, freight_amount: e.target.value })}
                />
              </Field>
              <Field label="Other charges">
                <Input
                  type="number"
                  step="0.01"
                  disabled={!editable}
                  value={form.other_charges}
                  onChange={(e) => setForm({ ...form, other_charges: e.target.value })}
                />
              </Field>
              <Field label="Discount">
                <Input
                  type="number"
                  step="0.01"
                  disabled={!editable}
                  value={form.discount_amount}
                  onChange={(e) => setForm({ ...form, discount_amount: e.target.value })}
                />
              </Field>
            </Grid>
          </Section>

          <Section title="Notes">
            <Textarea
              disabled={!editable}
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
            />
          </Section>
        </>
      )}

      {invoice && tab === "match" && (
        <>
          <Section title="3-way match — purchase order ↔ goods receipt ↔ invoice">
            <MatchPanel invoice={invoice} />
          </Section>
          {invoice.has_variance && ["DRAFT", "MATCHED", "VARIANCE"].includes(invoice.status) && (
            <Section
              title="Override"
              hint="The match failed. Approval needs a reason on the record — it is audited and shown to the approver."
            >
              <Textarea
                value={override}
                onChange={(e) => setOverride(e.target.value)}
                placeholder="e.g. Supplier confirmed the balance ships next week; the price rise was agreed by email on 12 June."
              />
            </Section>
          )}
        </>
      )}

      {invoice && tab === "notes" && <NotesPanel invoice={invoice} />}
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

function StatementModal({ onClose }: { onClose: () => void }) {
  const { orgId } = useDefaultOrg();
  const [supplier, setSupplier] = useState<number | null>(null);
  const [from, setFrom] = useState(new Date(Date.now() - 180 * 864e5).toISOString().slice(0, 10));
  const [to, setTo] = useState(new Date().toISOString().slice(0, 10));

  const { data, isFetching, refetch, error } = useQuery({
    queryKey: ["supplier-statement", supplier, from, to],
    enabled: false,
    queryFn: () =>
      api<SupplierStatement>(
        `/api/procurement/statement/?organization=${orgId}&supplier=${supplier}&from=${from}&to=${to}`,
      ),
  });

  return (
    <Modal title="Supplier statement of account" onClose={onClose}>
      <div className="flex flex-col gap-4">
        <ErrorNote error={error} />
        <Field label="Supplier">
          <SupplierSelect value={supplier} onChange={setSupplier} />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="From">
            <Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
          </Field>
          <Field label="To">
            <Input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
          </Field>
        </div>
        <div className="flex justify-end">
          <Button disabled={!supplier || isFetching} onClick={() => void refetch()}>
            {isFetching ? "Loading…" : "Show statement"}
          </Button>
        </div>

        {data && (
          <div>
            <div className="mb-2 flex items-center justify-between text-sm">
              <span className="font-semibold text-ink-900">{data.supplier_name}</span>
              <span className="text-ink-500">
                {data.date_from} → {data.date_to}
              </span>
            </div>
            <div className="max-h-72 overflow-y-auto rounded-lg border border-line">
              <table className="w-full text-sm">
                <thead className="sticky top-0 border-b border-line bg-surface-50 text-left text-[11px] text-ink-500">
                  <tr>
                    <th className="px-2.5 py-2">Date</th>
                    <th className="px-2.5 py-2">Document</th>
                    <th className="px-2.5 py-2 text-right">Debit</th>
                    <th className="px-2.5 py-2 text-right">Credit</th>
                    <th className="px-2.5 py-2 text-right">Balance</th>
                  </tr>
                </thead>
                <tbody>
                  {data.entries.map((e, i) => (
                    <tr key={i} className="border-b border-line last:border-0">
                      <td className="px-2.5 py-1.5">{e.date}</td>
                      <td className="px-2.5 py-1.5">
                        <div className="font-mono text-xs">{e.reference}</div>
                        <div className="text-xs text-ink-500">{e.description}</div>
                      </td>
                      <td className="px-2.5 py-1.5 text-right tabular-nums">{e.debit}</td>
                      <td className="px-2.5 py-1.5 text-right tabular-nums">{e.credit}</td>
                      <td className="px-2.5 py-1.5 text-right font-medium tabular-nums">
                        {e.balance}
                      </td>
                    </tr>
                  ))}
                  {data.entries.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-3 py-6 text-center text-ink-500">
                        Nothing in this period.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            <div className="mt-2 flex justify-between text-sm">
              <span className="text-ink-600">Closing balance</span>
              <span className="font-semibold tabular-nums">{money(data.closing_balance)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-ink-600">Still outstanding on bills</span>
              <span className="font-semibold tabular-nums">{money(data.total_outstanding)}</span>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}

/* -------------------------------------------------------------------------- */

export function SupplierInvoicesPage() {
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState<SupplierInvoice | null>(null);
  const [creating, setCreating] = useState(false);
  const [statement, setStatement] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["supplier-invoices", status],
    queryFn: () =>
      api<Paginated<SupplierInvoice>>(
        `/api/procurement/invoices/?page_size=200${status ? `&status=${status}` : ""}`,
      ),
  });

  const rows = data?.results ?? [];
  const current = open ? (rows.find((i) => i.id === open.id) ?? open) : null;

  return (
    <div>
      <PageHeader
        title="Supplier invoices & 3-way match"
        action={
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setStatement(true)}>
              <ScrollText className="h-4 w-4" /> Statement
            </Button>
            <Button onClick={() => setCreating(true)}>
              <Plus className="h-4 w-4" /> New invoice
            </Button>
          </div>
        }
      />

      <DataGrid<SupplierInvoice>
        rows={rows}
        loading={isLoading}
        getRowId={(i) => i.id}
        storageKey="procurement-invoices"
        exportName="supplier-invoices"
        searchPlaceholder="Search by invoice number, supplier, PO…"
        emptyMessage="No supplier invoices yet."
        onRowClick={(i) => setOpen(i)}
        toolbar={
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="rounded-md border border-line bg-surface-0 px-2.5 py-1.5 text-xs font-medium text-ink-700"
            aria-label="Filter by status"
          >
            {STATUS_FILTERS.map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        }
        columns={[
          {
            key: "invoice_number",
            header: "Invoice",
            render: (i) => (
              <div>
                <div className="font-mono font-medium text-ink-900">{i.invoice_number}</div>
                <div className="text-xs text-ink-500">{i.invoice_date}</div>
              </div>
            ),
          },
          { key: "supplier_name", header: "Supplier" },
          { key: "po_number", header: "PO", value: (i) => i.po_number ?? "—" },
          { key: "grn_number", header: "GRN", value: (i) => i.grn_number ?? "—" },
          {
            key: "status",
            header: "Status",
            value: (i) => i.status,
            render: (i) => <StatusBadge status={i.status} label={i.status_display} />,
          },
          {
            key: "match_result",
            header: "Match",
            value: (i) => i.match_result,
            render: (i) =>
              i.match_result === "NOT_RUN" ? (
                <span className="text-ink-500">not run</span>
              ) : (
                <Badge tone={i.match_result === "MATCHED" ? "success" : "danger"}>
                  {i.match_result_display}
                </Badge>
              ),
          },
          {
            key: "total_amount",
            header: "Total",
            align: "right",
            numeric: true,
            value: (i) => Number(i.total_amount_base),
            render: (i) => (
              <div>
                <div className="font-medium">{money(i.total_amount, i.currency)}</div>
                {Number(i.notes_total) !== 0 && (
                  <div className="text-xs text-ink-500">
                    net {money(i.payable_amount, i.currency)}
                  </div>
                )}
              </div>
            ),
          },
          { key: "due_date", header: "Due", value: (i) => i.due_date ?? "—" },
        ]}
      />

      {creating && <InvoiceDrawer invoice={null} onClose={() => setCreating(false)} />}
      {current && <InvoiceDrawer invoice={current} onClose={() => setOpen(null)} />}
      {statement && <StatementModal onClose={() => setStatement(false)} />}
    </div>
  );
}
