import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Ban, PackageCheck, Plus, Send, ShieldCheck, XCircle } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { DataGrid } from "../components/DataGrid";
import {
  Drawer,
  ErrorNote,
  Facts,
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
} from "../components/ProcurementKit";
import { useDefaultOrg } from "../lib/procurementData";
import { Badge, Button, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import {
  INCOTERMS,
  money,
  num,
  type PurchaseOrder,
  type PurchaseOrderLine,
} from "../lib/procurement";
import type { Organization, Paginated } from "../lib/types";

const STATUS_FILTERS = [
  ["", "All"],
  ["DRAFT", "Draft"],
  ["PENDING_APPROVAL", "Awaiting approval"],
  ["APPROVED", "Approved"],
  ["SENT", "Sent"],
  ["PARTIALLY_RECEIVED", "Partially received"],
  ["RECEIVED", "Received"],
  ["CLOSED", "Closed"],
  ["CANCELLED", "Cancelled"],
] as const;

type Draft = {
  supplier: number | null;
  order_date: string;
  expected_delivery: string;
  currency: string;
  exchange_rate: string;
  incoterm: string;
  payment_terms_days: number;
  payment_terms_note: string;
  freight_amount: string;
  other_charges: string;
  discount_amount: string;
  is_import: boolean;
  is_dropship: boolean;
  deliver_to: number | null;
  delivery_address: string;
  supplier_reference: string;
  terms: string;
  notes: string;
  lines: PurchaseOrderLine[];
};

const emptyLine = (): PurchaseOrderLine => ({
  product: 0,
  quantity_ordered: 1,
  unit_price: "0.00",
  discount_pct: "0.00",
  tax_rate_pct: "0.00",
});

function toDraft(order?: PurchaseOrder): Draft {
  return {
    supplier: order?.supplier ?? null,
    order_date: order?.order_date ?? new Date().toISOString().slice(0, 10),
    expected_delivery: order?.expected_delivery ?? "",
    currency: order?.currency ?? "RWF",
    exchange_rate: order?.exchange_rate ?? "1.000000",
    incoterm: order?.incoterm ?? "",
    payment_terms_days: order?.payment_terms_days ?? 30,
    payment_terms_note: order?.payment_terms_note ?? "",
    freight_amount: order?.freight_amount ?? "0.00",
    other_charges: order?.other_charges ?? "0.00",
    discount_amount: order?.discount_amount ?? "0.00",
    is_import: order?.is_import ?? false,
    is_dropship: order?.is_dropship ?? false,
    deliver_to: order?.deliver_to ?? null,
    delivery_address: order?.delivery_address ?? "",
    supplier_reference: order?.supplier_reference ?? "",
    terms: order?.terms ?? "",
    notes: order?.notes ?? "",
    lines: order?.lines?.length ? order.lines.map((l) => ({ ...l })) : [emptyLine()],
  };
}

/** Client-side mirror of the server's line maths, so totals move as you type. */
function lineMaths(line: PurchaseOrderLine) {
  const net = num(line.unit_price) * (100 - num(line.discount_pct)) / 100;
  const subtotal = net * Number(line.quantity_ordered || 0);
  const tax = (subtotal * num(line.tax_rate_pct)) / 100;
  return { net, subtotal, tax, total: subtotal + tax };
}

/* -------------------------------------------------------------------------- */

function OrderDrawer({
  order,
  onClose,
}: {
  order: PurchaseOrder | null; // null = creating
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { orgId, orgs } = useDefaultOrg();
  const [draft, setDraft] = useState<Draft>(() => toDraft(order ?? undefined));
  const [cancelReason, setCancelReason] = useState("");
  const editable = order === null || order.is_editable;

  const set = (patch: Partial<Draft>) => setDraft((d) => ({ ...d, ...patch }));

  const totals = useMemo(() => {
    const subtotal = draft.lines.reduce((s, l) => s + lineMaths(l).subtotal, 0);
    const tax = draft.lines.reduce((s, l) => s + lineMaths(l).tax, 0);
    const grand =
      subtotal + tax + num(draft.freight_amount) + num(draft.other_charges) - num(draft.discount_amount);
    return { subtotal, tax, grand, base: grand * num(draft.exchange_rate) };
  }, [draft]);

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["purchase-orders"] });
    void qc.invalidateQueries({ queryKey: ["procurement-overview"] });
  };

  const body = () => ({
    organization: orgId,
    supplier: draft.supplier,
    order_date: draft.order_date,
    expected_delivery: draft.expected_delivery || null,
    currency: draft.currency,
    exchange_rate: draft.exchange_rate,
    incoterm: draft.incoterm,
    payment_terms_days: draft.payment_terms_days,
    payment_terms_note: draft.payment_terms_note,
    freight_amount: draft.freight_amount || "0",
    other_charges: draft.other_charges || "0",
    discount_amount: draft.discount_amount || "0",
    is_import: draft.is_import,
    is_dropship: draft.is_dropship,
    deliver_to: draft.is_dropship ? draft.deliver_to : null,
    delivery_address: draft.delivery_address,
    supplier_reference: draft.supplier_reference,
    terms: draft.terms,
    notes: draft.notes,
    lines: draft.lines
      .filter((l) => l.product && Number(l.quantity_ordered) > 0)
      .map((l) => ({
        product: l.product,
        description: l.description ?? "",
        quantity_ordered: Number(l.quantity_ordered),
        unit_price: l.unit_price || "0",
        discount_pct: l.discount_pct || "0",
        tax_rate_pct: l.tax_rate_pct || "0",
        expected_delivery: l.expected_delivery || null,
        notes: l.notes ?? "",
      })),
  });

  const save = useMutation({
    mutationFn: () =>
      api<PurchaseOrder>(
        order ? `/api/procurement/orders/${order.id}/` : "/api/procurement/orders/",
        { method: order ? "PATCH" : "POST", body: JSON.stringify(body()) },
      ),
    onSuccess: () => {
      invalidate();
      onClose();
    },
  });

  const submit = useMutation({
    mutationFn: () =>
      api(`/api/procurement/orders/${order!.id}/submit/`, { method: "POST", body: "{}" }),
    onSuccess: () => {
      invalidate();
      onClose();
    },
  });

  const send = useMutation({
    mutationFn: () =>
      api(`/api/procurement/orders/${order!.id}/send/`, {
        method: "POST",
        body: JSON.stringify({ method: "EMAIL" }),
      }),
    onSuccess: () => {
      invalidate();
      onClose();
    },
  });

  const cancel = useMutation({
    mutationFn: () =>
      api(`/api/procurement/orders/${order!.id}/cancel/`, {
        method: "POST",
        body: JSON.stringify({ reason: cancelReason }),
      }),
    onSuccess: () => {
      invalidate();
      onClose();
    },
  });

  const closeOrder = useMutation({
    mutationFn: () =>
      api(`/api/procurement/orders/${order!.id}/close/`, {
        method: "POST",
        body: JSON.stringify({ reason: "Balance will not be delivered" }),
      }),
    onSuccess: () => {
      invalidate();
      onClose();
    },
  });

  const startReceipt = useMutation({
    mutationFn: () =>
      api<{ id: number }>(`/api/procurement/orders/${order!.id}/start_receipt/`, {
        method: "POST",
        body: "{}",
      }),
    onSuccess: (receipt) => {
      invalidate();
      void qc.invalidateQueries({ queryKey: ["goods-receipts"] });
      navigate(`/procurement/receipts?open=${receipt.id}`);
    },
  });

  const busy =
    save.isPending || submit.isPending || send.isPending || cancel.isPending || startReceipt.isPending;
  const error =
    save.error ?? submit.error ?? send.error ?? cancel.error ?? closeOrder.error ?? startReceipt.error;

  const footer = (
    <>
      {order && order.status === "DRAFT" && (
        <Button variant="secondary" disabled={busy} onClick={() => cancel.mutate()}>
          <Ban className="h-3.5 w-3.5" /> Cancel order
        </Button>
      )}
      {order && ["APPROVED", "SENT", "PARTIALLY_RECEIVED"].includes(order.status) && (
        <Button variant="secondary" disabled={busy} onClick={() => closeOrder.mutate()}>
          <XCircle className="h-3.5 w-3.5" /> Close short
        </Button>
      )}
      {order && order.can_receive && (
        <Button variant="secondary" disabled={busy} onClick={() => startReceipt.mutate()}>
          <PackageCheck className="h-3.5 w-3.5" /> Receive goods
        </Button>
      )}
      {order && order.status === "APPROVED" && (
        <Button disabled={busy} onClick={() => send.mutate()}>
          <Send className="h-3.5 w-3.5" /> Send to supplier
        </Button>
      )}
      {order && order.status === "DRAFT" && (
        <Button disabled={busy} onClick={() => submit.mutate()}>
          <ShieldCheck className="h-3.5 w-3.5" /> Submit for approval
        </Button>
      )}
      {editable && (
        <Button disabled={busy || !draft.supplier} onClick={() => save.mutate()}>
          {save.isPending ? "Saving…" : order ? "Save changes" : "Create order"}
        </Button>
      )}
      <Button variant="secondary" onClick={onClose}>
        Close
      </Button>
    </>
  );

  return (
    <Drawer
      title={order ? order.po_number : "New purchase order"}
      badge={order && <StatusBadge status={order.status} label={order.status_display} />}
      subtitle={
        order ? (
          <>
            {order.supplier_name} · raised by {order.created_by_name ?? "—"}
            {order.approved_by_name && ` · approved by ${order.approved_by_name}`}
          </>
        ) : (
          "Raise an order on an external supplier. It must be approved by someone else before it can be sent."
        )
      }
      onClose={onClose}
      width="max-w-5xl"
      footer={footer}
    >
      <ErrorNote error={error} />

      {order && !editable && (
        <div className="mb-4 rounded-md border border-line bg-surface-50 p-3">
          <Facts
            rows={[
              ["Ordered", order.quantity_ordered],
              ["Received", `${order.quantity_received} (${order.received_pct}%)`],
              ["Receipts", order.receipt_count],
              ["Sent", order.sent_at ? new Date(order.sent_at).toLocaleString() : "—"],
              ["Consignment", order.consignment_reference ?? "—"],
              ["Cancel reason", order.cancel_reason || "—"],
            ]}
          />
        </div>
      )}

      <Section title="Supplier & dates">
        <Grid cols={3}>
          <Field label="Supplier">
            <SupplierSelect
              value={draft.supplier}
              onChange={(id) => set({ supplier: id })}
              disabled={!editable}
            />
          </Field>
          <Field label="Order date">
            <Input
              type="date"
              disabled={!editable}
              value={draft.order_date}
              onChange={(e) => set({ order_date: e.target.value })}
            />
          </Field>
          <Field label="Expected delivery">
            <Input
              type="date"
              disabled={!editable}
              value={draft.expected_delivery}
              onChange={(e) => set({ expected_delivery: e.target.value })}
            />
          </Field>
          <Field label="Supplier reference">
            <Input
              disabled={!editable}
              value={draft.supplier_reference}
              onChange={(e) => set({ supplier_reference: e.target.value })}
              placeholder="Their quote / proforma number"
            />
          </Field>
          <Field label="Currency">
            <Input
              maxLength={3}
              disabled={!editable}
              value={draft.currency}
              onChange={(e) => set({ currency: e.target.value.toUpperCase() })}
            />
          </Field>
          <Field label="Exchange rate to RWF" hint="1 unit of the order currency in RWF.">
            <Input
              type="number"
              step="0.000001"
              disabled={!editable}
              value={draft.exchange_rate}
              onChange={(e) => set({ exchange_rate: e.target.value })}
            />
          </Field>
        </Grid>
      </Section>

      <Section title="Terms & delivery">
        <Grid cols={4}>
          <Field label="Incoterm">
            <Select
              disabled={!editable}
              value={draft.incoterm}
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
          <Field label="Payment terms (days)">
            <Input
              type="number"
              disabled={!editable}
              value={draft.payment_terms_days}
              onChange={(e) => set({ payment_terms_days: Number(e.target.value) })}
            />
          </Field>
          <Field label="Terms note" className="sm:col-span-2">
            <Input
              disabled={!editable}
              value={draft.payment_terms_note}
              onChange={(e) => set({ payment_terms_note: e.target.value })}
              placeholder="e.g. 2/10 net 30, 30% deposit on order"
            />
          </Field>
        </Grid>
        <div className="mt-3 flex flex-wrap gap-4">
          <label className="flex items-center gap-2 text-sm text-ink-700">
            <input
              type="checkbox"
              disabled={!editable}
              checked={draft.is_import}
              onChange={(e) => set({ is_import: e.target.checked })}
              className="h-3.5 w-3.5 accent-brand-600"
            />
            Import (attach to a consignment for landed cost)
          </label>
          <label className="flex items-center gap-2 text-sm text-ink-700">
            <input
              type="checkbox"
              disabled={!editable}
              checked={draft.is_dropship}
              onChange={(e) => set({ is_dropship: e.target.checked })}
              className="h-3.5 w-3.5 accent-brand-600"
            />
            Drop-ship straight to a branch
          </label>
        </div>
        {draft.is_dropship && (
          <div className="mt-3">
            <Grid cols={2}>
              <Field label="Deliver to">
                <Select
                  disabled={!editable}
                  value={draft.deliver_to ?? ""}
                  onChange={(e) =>
                    set({ deliver_to: e.target.value ? Number(e.target.value) : null })
                  }
                >
                  <option value="">— select a branch —</option>
                  {orgs.map((o: Organization) => (
                    <option key={o.id} value={o.id}>
                      {o.name}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Delivery address">
                <Input
                  disabled={!editable}
                  value={draft.delivery_address}
                  onChange={(e) => set({ delivery_address: e.target.value })}
                />
              </Field>
            </Grid>
          </div>
        )}
      </Section>

      <Section title="Lines" hint={`Prices in ${draft.currency}.`}>
        <LineEditor<PurchaseOrderLine>
          rows={draft.lines}
          readOnly={!editable}
          onChange={(lines) => set({ lines })}
          makeRow={emptyLine}
          addLabel="Add product"
          emptyMessage="No products on this order yet."
          columns={[
            {
              header: "Product",
              width: "34%",
              cell: (row, setRow) => (
                <ProductPicker
                  value={row.product || null}
                  disabled={!editable}
                  onChange={(id) => setRow({ product: id })}
                />
              ),
            },
            {
              header: "Qty",
              width: "9%",
              align: "right",
              cell: (row, setRow) =>
                editable ? (
                  <Input
                    type="number"
                    min={1}
                    value={row.quantity_ordered}
                    onChange={(e) => setRow({ quantity_ordered: Number(e.target.value) })}
                    className="text-right"
                  />
                ) : (
                  <>{row.quantity_ordered}</>
                ),
            },
            {
              header: "Unit price",
              width: "13%",
              align: "right",
              cell: (row, setRow) =>
                editable ? (
                  <Input
                    type="number"
                    step="0.01"
                    value={row.unit_price}
                    onChange={(e) => setRow({ unit_price: e.target.value })}
                    className="text-right"
                  />
                ) : (
                  <>{row.unit_price}</>
                ),
            },
            {
              header: "Disc %",
              width: "9%",
              align: "right",
              cell: (row, setRow) =>
                editable ? (
                  <Input
                    type="number"
                    step="0.01"
                    value={row.discount_pct}
                    onChange={(e) => setRow({ discount_pct: e.target.value })}
                    className="text-right"
                  />
                ) : (
                  <>{row.discount_pct}</>
                ),
            },
            {
              header: "VAT %",
              width: "9%",
              align: "right",
              cell: (row, setRow) =>
                editable ? (
                  <Input
                    type="number"
                    step="0.01"
                    value={row.tax_rate_pct}
                    onChange={(e) => setRow({ tax_rate_pct: e.target.value })}
                    className="text-right"
                  />
                ) : (
                  <>{row.tax_rate_pct}</>
                ),
            },
            {
              header: "Received",
              width: "9%",
              align: "right",
              cell: (row) => (
                <span className="text-ink-500">
                  {row.quantity_received ?? 0}/{row.quantity_ordered}
                </span>
              ),
            },
            {
              header: "Line total",
              width: "13%",
              align: "right",
              cell: (row) => (
                <span className="font-medium">
                  {lineMaths(row).total.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                </span>
              ),
            },
          ]}
          footer={
            <>
              <TotalsRow span={6} label="Subtotal" value={totals.subtotal.toFixed(2)} />
              <TotalsRow span={6} label="VAT" value={totals.tax.toFixed(2)} />
              <TotalsRow span={6} label={`Total (${draft.currency})`} value={totals.grand.toFixed(2)} strong />
              {draft.currency !== "RWF" && (
                <TotalsRow span={6} label="Total (RWF)" value={totals.base.toFixed(2)} />
              )}
            </>
          }
        />
        <Grid cols={3}>
          <Field label="Freight">
            <Input
              type="number"
              step="0.01"
              disabled={!editable}
              value={draft.freight_amount}
              onChange={(e) => set({ freight_amount: e.target.value })}
            />
          </Field>
          <Field label="Other charges">
            <Input
              type="number"
              step="0.01"
              disabled={!editable}
              value={draft.other_charges}
              onChange={(e) => set({ other_charges: e.target.value })}
            />
          </Field>
          <Field label="Order discount">
            <Input
              type="number"
              step="0.01"
              disabled={!editable}
              value={draft.discount_amount}
              onChange={(e) => set({ discount_amount: e.target.value })}
            />
          </Field>
        </Grid>
      </Section>

      <Section title="Terms & notes">
        <Grid cols={2}>
          <Field label="Terms & conditions">
            <Textarea
              disabled={!editable}
              value={draft.terms}
              onChange={(e) => set({ terms: e.target.value })}
            />
          </Field>
          <Field label="Internal notes">
            <Textarea
              disabled={!editable}
              value={draft.notes}
              onChange={(e) => set({ notes: e.target.value })}
            />
          </Field>
        </Grid>
      </Section>

      {order && order.status === "DRAFT" && (
        <Section title="Cancellation">
          <Field label="Reason" hint="Required if you cancel this order.">
            <Input value={cancelReason} onChange={(e) => setCancelReason(e.target.value)} />
          </Field>
        </Section>
      )}
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

export function SupplierOrdersPage() {
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState<PurchaseOrder | null>(null);
  const [creating, setCreating] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["purchase-orders", status],
    queryFn: () =>
      api<Paginated<PurchaseOrder>>(
        `/api/procurement/orders/?page_size=200${status ? `&status=${status}` : ""}`,
      ),
  });

  const rows = data?.results ?? [];
  const current = open ? rows.find((o) => o.id === open.id) ?? open : null;

  return (
    <div>
      <PageHeader
        title="Supplier purchase orders"
        action={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" /> New purchase order
          </Button>
        }
      />
      <p className="mb-4 max-w-3xl text-sm text-ink-500">
        Buying from external suppliers: raise → approve (never your own) → send → receive. Multi-currency
        with Incoterms and payment terms; partial receipt and drop-ship to a branch are both supported.
      </p>

      <DataGrid<PurchaseOrder>
        rows={rows}
        loading={isLoading}
        getRowId={(o) => o.id}
        storageKey="procurement-orders"
        exportName="purchase-orders"
        searchPlaceholder="Search by PO number, supplier, reference…"
        emptyMessage="No purchase orders yet."
        onRowClick={(o) => setOpen(o)}
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
            key: "po_number",
            header: "PO",
            render: (o) => (
              <div>
                <div className="font-mono font-medium text-ink-900">{o.po_number}</div>
                <div className="text-xs text-ink-500">{o.order_date}</div>
              </div>
            ),
          },
          { key: "supplier_name", header: "Supplier" },
          {
            key: "status",
            header: "Status",
            value: (o) => o.status,
            render: (o) => <StatusBadge status={o.status} label={o.status_display} />,
          },
          {
            key: "expected_delivery",
            header: "Due",
            value: (o) => o.expected_delivery ?? "",
            render: (o) => {
              if (!o.expected_delivery) return <span className="text-ink-500">—</span>;
              const late =
                o.expected_delivery < new Date().toISOString().slice(0, 10) &&
                ["APPROVED", "SENT", "PARTIALLY_RECEIVED"].includes(o.status);
              return late ? (
                <Badge tone="danger">{o.expected_delivery}</Badge>
              ) : (
                <span>{o.expected_delivery}</span>
              );
            },
          },
          {
            key: "received_pct",
            header: "Received",
            align: "right",
            numeric: true,
            value: (o) => Number(o.received_pct),
            render: (o) => (
              <div className="flex items-center justify-end gap-2">
                <div className="h-1.5 w-14 overflow-hidden rounded-full bg-surface-100">
                  <div
                    className="h-full bg-brand-600"
                    style={{ width: `${Math.min(100, Number(o.received_pct))}%` }}
                  />
                </div>
                <span className="w-9 text-right">{Number(o.received_pct).toFixed(0)}%</span>
              </div>
            ),
          },
          {
            key: "total_amount",
            header: "Total",
            align: "right",
            numeric: true,
            value: (o) => Number(o.total_amount_base),
            render: (o) => (
              <div>
                <div className="font-medium">{money(o.total_amount, o.currency)}</div>
                {o.currency !== "RWF" && (
                  <div className="text-xs text-ink-500">{money(o.total_amount_base)}</div>
                )}
              </div>
            ),
          },
          {
            key: "flags",
            header: "",
            fixed: true,
            sortable: false,
            render: (o) => (
              <div className="flex justify-end gap-1">
                {o.is_import && <Badge tone="info">Import</Badge>}
                {o.is_dropship && <Badge tone="neutral">Drop-ship</Badge>}
              </div>
            ),
          },
        ]}
      />

      {creating && <OrderDrawer order={null} onClose={() => setCreating(false)} />}
      {current && <OrderDrawer order={current} onClose={() => setOpen(null)} />}
    </div>
  );
}
