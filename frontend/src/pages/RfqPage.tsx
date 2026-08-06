import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Award, Plus, Send, Star } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { DataGrid } from "../components/DataGrid";
import {
  Drawer,
  Empty,
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
} from "../components/ProcurementKit";
import { useDefaultOrg } from "../lib/procurementData";
import { Badge, Button, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import {
  INCOTERMS,
  money,
  num,
  type QuoteComparisonRow,
  type RequestForQuotation,
  type RFQLine,
  type SupplierQuote,
  type SupplierQuoteLine,
} from "../lib/procurement";
import type { Paginated } from "../lib/types";

const emptyRfqLine = (): RFQLine => ({ product: 0, quantity: 1, specification: "" });
const emptyQuoteLine = (): SupplierQuoteLine => ({
  product: 0,
  quantity_offered: 1,
  unit_price: "0.00",
});

/* -------------------------------------------------------------------------- */

function QuoteForm({ rfq, onDone }: { rfq: RequestForQuotation; onDone: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    supplier: null as number | null,
    quote_reference: "",
    quote_date: new Date().toISOString().slice(0, 10),
    valid_until: "",
    currency: "RWF",
    exchange_rate: "1.000000",
    incoterm: "",
    lead_time_days: 0,
    payment_terms_days: 30,
    freight_amount: "0.00",
    other_charges: "0.00",
    discount_amount: "0.00",
    warranty_terms: "",
    notes: "",
    lines: rfq.lines.map((l) => ({
      rfq_line: l.id ?? null,
      product: l.product,
      quantity_offered: l.quantity,
      unit_price: "0.00",
      lead_time_days: 0,
    })) as SupplierQuoteLine[],
  });

  const total = useMemo(() => {
    const goods = form.lines.reduce(
      (s, l) => s + num(l.unit_price) * Number(l.quantity_offered || 0),
      0,
    );
    return (
      goods + num(form.freight_amount) + num(form.other_charges) - num(form.discount_amount)
    );
  }, [form]);

  const create = useMutation({
    mutationFn: () =>
      api<SupplierQuote>("/api/procurement/quotes/", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          rfq: rfq.id,
          quote_date: form.quote_date || null,
          valid_until: form.valid_until || null,
          lines: form.lines
            .filter((l) => l.product && Number(l.quantity_offered) > 0)
            .map((l) => ({
              rfq_line: l.rfq_line ?? null,
              product: l.product,
              quantity_offered: Number(l.quantity_offered),
              unit_price: l.unit_price || "0",
              lead_time_days: Number(l.lead_time_days ?? 0),
              notes: l.notes ?? "",
            })),
        }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["rfqs"] });
      onDone();
    },
  });

  return (
    <div className="rounded-lg border border-line bg-surface-50 p-3">
      <ErrorNote error={create.error} />
      <Grid cols={4}>
        <Field label="Supplier" className="sm:col-span-2">
          <SupplierSelect value={form.supplier} onChange={(id) => setForm({ ...form, supplier: id })} />
        </Field>
        <Field label="Their reference">
          <Input
            value={form.quote_reference}
            onChange={(e) => setForm({ ...form, quote_reference: e.target.value })}
          />
        </Field>
        <Field label="Quote date">
          <Input
            type="date"
            value={form.quote_date}
            onChange={(e) => setForm({ ...form, quote_date: e.target.value })}
          />
        </Field>
        <Field label="Valid until">
          <Input
            type="date"
            value={form.valid_until}
            onChange={(e) => setForm({ ...form, valid_until: e.target.value })}
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
        <Field label="Incoterm">
          <Select
            value={form.incoterm}
            onChange={(e) => setForm({ ...form, incoterm: e.target.value })}
          >
            <option value="">—</option>
            {INCOTERMS.map((i) => (
              <option key={i} value={i}>
                {i}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Lead time (days)">
          <Input
            type="number"
            value={form.lead_time_days}
            onChange={(e) => setForm({ ...form, lead_time_days: Number(e.target.value) })}
          />
        </Field>
        <Field label="Payment terms (days)">
          <Input
            type="number"
            value={form.payment_terms_days}
            onChange={(e) => setForm({ ...form, payment_terms_days: Number(e.target.value) })}
          />
        </Field>
        <Field label="Freight">
          <Input
            type="number"
            step="0.01"
            value={form.freight_amount}
            onChange={(e) => setForm({ ...form, freight_amount: e.target.value })}
          />
        </Field>
        <Field label="Other charges">
          <Input
            type="number"
            step="0.01"
            value={form.other_charges}
            onChange={(e) => setForm({ ...form, other_charges: e.target.value })}
          />
        </Field>
        <Field label="Discount">
          <Input
            type="number"
            step="0.01"
            value={form.discount_amount}
            onChange={(e) => setForm({ ...form, discount_amount: e.target.value })}
          />
        </Field>
      </Grid>

      <div className="mt-3">
        <LineEditor<SupplierQuoteLine>
          rows={form.lines}
          onChange={(lines) => setForm({ ...form, lines })}
          makeRow={emptyQuoteLine}
          addLabel="Add a line they quoted"
          columns={[
            {
              header: "Product",
              width: "44%",
              cell: (row, set) => (
                <ProductPicker value={row.product || null} onChange={(id) => set({ product: id })} />
              ),
            },
            {
              header: "Qty offered",
              width: "16%",
              align: "right",
              cell: (row, set) => (
                <Input
                  type="number"
                  min={1}
                  value={row.quantity_offered}
                  onChange={(e) => set({ quantity_offered: Number(e.target.value) })}
                  className="text-right"
                />
              ),
            },
            {
              header: "Unit price",
              width: "18%",
              align: "right",
              cell: (row, set) => (
                <Input
                  type="number"
                  step="0.01"
                  value={row.unit_price}
                  onChange={(e) => set({ unit_price: e.target.value })}
                  className="text-right"
                />
              ),
            },
            {
              header: "Line total",
              width: "22%",
              align: "right",
              cell: (row) => (
                <span className="font-medium">
                  {(num(row.unit_price) * Number(row.quantity_offered || 0)).toLocaleString(
                    undefined,
                    { maximumFractionDigits: 2 },
                  )}
                </span>
              ),
            },
          ]}
          footer={
            <TotalsRow span={3} label={`Quote total (${form.currency})`} value={total.toFixed(2)} strong />
          }
        />
      </div>

      <div className="mt-3">
        <Field label="Notes">
          <Textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
        </Field>
      </div>

      <div className="mt-3 flex justify-end gap-2">
        <Button variant="secondary" onClick={onDone}>
          Cancel
        </Button>
        <Button disabled={!form.supplier || create.isPending} onClick={() => create.mutate()}>
          {create.isPending ? "Saving…" : "Record quote"}
        </Button>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */

function Comparison({ rfq, onAwarded }: { rfq: RequestForQuotation; onAwarded: () => void }) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { data: rows = [], isLoading } = useQuery({
    queryKey: ["rfq-comparison", rfq.id],
    queryFn: () => api<QuoteComparisonRow[]>(`/api/procurement/rfqs/${rfq.id}/comparison/`),
  });

  const award = useMutation({
    mutationFn: (quoteId: number) =>
      api<{ po_number: string }>(`/api/procurement/quotes/${quoteId}/award/`, {
        method: "POST",
        body: "{}",
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["rfqs"] });
      void qc.invalidateQueries({ queryKey: ["purchase-orders"] });
      onAwarded();
      navigate("/procurement/orders");
    },
  });

  const shortlist = useMutation({
    mutationFn: (quoteId: number) =>
      api(`/api/procurement/quotes/${quoteId}/shortlist/`, { method: "POST", body: "{}" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["rfqs"] });
      void qc.invalidateQueries({ queryKey: ["rfq-comparison", rfq.id] });
    },
  });

  if (isLoading) return <Empty message="Loading comparison…" />;
  if (rows.length === 0)
    return <Empty message="No quotes recorded yet — add one to compare suppliers." />;

  return (
    <>
      <ErrorNote error={award.error} />
      <div className="overflow-x-auto rounded-lg border border-line">
        <table className="w-full min-w-[860px] text-sm">
          <thead className="border-b border-line bg-surface-50 text-left text-[11px] uppercase tracking-wide text-ink-500">
            <tr>
              <th className="px-2.5 py-2">Supplier</th>
              <th className="px-2.5 py-2 text-right">Goods</th>
              <th className="px-2.5 py-2 text-right">Total (their currency)</th>
              <th className="px-2.5 py-2 text-right">Total (RWF)</th>
              <th className="px-2.5 py-2 text-right">vs best</th>
              <th className="px-2.5 py-2 text-right">Lead</th>
              <th className="px-2.5 py-2 text-right">Terms</th>
              <th className="px-2.5 py-2 text-right">Score</th>
              <th className="px-2.5 py-2" />
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr
                key={r.quote_id}
                className={`border-b border-line last:border-0 ${r.is_cheapest ? "bg-green-50/50" : ""}`}
              >
                <td className="px-2.5 py-2">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-ink-900">{r.supplier_name}</span>
                    {r.is_cheapest && <Badge tone="success">Best price</Badge>}
                    {r.status === "SHORTLISTED" && <Badge tone="info">Shortlisted</Badge>}
                    {r.status === "AWARDED" && <Badge tone="success">Awarded</Badge>}
                    {r.supplier_standing &&
                      ["BLACKLISTED", "SUSPENDED"].includes(r.supplier_standing) && (
                        <Badge tone="danger">{r.supplier_standing}</Badge>
                      )}
                  </div>
                  <div className="text-xs text-ink-500">
                    {r.incoterm || "—"} · valid to {r.valid_until ?? "—"}
                  </div>
                </td>
                <td className="px-2.5 py-2 text-right tabular-nums">{r.goods_total}</td>
                <td className="px-2.5 py-2 text-right tabular-nums">
                  {money(r.total_amount, r.currency)}
                </td>
                <td className="px-2.5 py-2 text-right font-semibold tabular-nums">
                  {money(r.total_amount_base)}
                </td>
                <td className="px-2.5 py-2 text-right tabular-nums">
                  {Number(r.delta_vs_best) === 0 ? (
                    <span className="text-green-700">—</span>
                  ) : (
                    <span className="text-red-700">+{money(r.delta_vs_best)}</span>
                  )}
                </td>
                <td className="px-2.5 py-2 text-right tabular-nums">{r.lead_time_days}d</td>
                <td className="px-2.5 py-2 text-right tabular-nums">net {r.payment_terms_days}d</td>
                <td className="px-2.5 py-2 text-right tabular-nums">
                  {r.supplier_score ? Number(r.supplier_score).toFixed(0) : "—"}
                </td>
                <td className="px-2.5 py-2">
                  <div className="flex justify-end gap-1">
                    {r.status !== "AWARDED" && (
                      <button
                        onClick={() => shortlist.mutate(r.quote_id)}
                        className="rounded-md border border-line px-2 py-1 text-xs font-medium text-ink-700 hover:bg-surface-100"
                      >
                        <Star className="mr-1 inline h-3 w-3" />
                        Shortlist
                      </button>
                    )}
                    {rfq.status !== "AWARDED" && (
                      <Button disabled={award.isPending} onClick={() => award.mutate(r.quote_id)}>
                        <Award className="h-3.5 w-3.5" /> Award
                      </Button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-ink-500">
        Totals are converted to RWF so quotes in different currencies are actually comparable.
        Awarding creates a draft purchase order from that quote and declines the rest.
      </p>
    </>
  );
}

/* -------------------------------------------------------------------------- */

function RfqDrawer({ rfq, onClose }: { rfq: RequestForQuotation | null; onClose: () => void }) {
  const qc = useQueryClient();
  const { orgId } = useDefaultOrg();
  const editable = rfq === null || rfq.status === "DRAFT";
  const [addingQuote, setAddingQuote] = useState(false);
  const [form, setForm] = useState({
    title: rfq?.title ?? "",
    response_due: rfq?.response_due ?? "",
    delivery_required_by: rfq?.delivery_required_by ?? "",
    terms: rfq?.terms ?? "",
    notes: rfq?.notes ?? "",
    lines: rfq?.lines?.length ? rfq.lines.map((l) => ({ ...l })) : [emptyRfqLine()],
  });

  const invalidate = () => void qc.invalidateQueries({ queryKey: ["rfqs"] });

  const save = useMutation({
    mutationFn: () =>
      api<RequestForQuotation>(
        rfq ? `/api/procurement/rfqs/${rfq.id}/` : "/api/procurement/rfqs/",
        {
          method: rfq ? "PATCH" : "POST",
          body: JSON.stringify({
            organization: orgId,
            title: form.title,
            response_due: form.response_due || null,
            delivery_required_by: form.delivery_required_by || null,
            terms: form.terms,
            notes: form.notes,
            lines: form.lines
              .filter((l) => l.product && Number(l.quantity) > 0)
              .map((l) => ({
                product: l.product,
                quantity: Number(l.quantity),
                specification: l.specification ?? "",
              })),
          }),
        },
      ),
    onSuccess: () => {
      invalidate();
      onClose();
    },
  });

  const send = useMutation({
    mutationFn: () => api(`/api/procurement/rfqs/${rfq!.id}/send/`, { method: "POST", body: "{}" }),
    onSuccess: () => {
      invalidate();
      onClose();
    },
  });

  return (
    <Drawer
      title={rfq ? `${rfq.rfq_number} · ${rfq.title}` : "New request for quotation"}
      badge={rfq && <StatusBadge status={rfq.status} label={rfq.status_display} />}
      subtitle={
        rfq
          ? `${rfq.organization_name} · ${rfq.quote_count} quote(s) received`
          : "Ask several suppliers to price the same basket, then compare them like for like."
      }
      onClose={onClose}
      width="max-w-5xl"
      footer={
        <>
          {rfq?.status === "DRAFT" && (
            <Button disabled={send.isPending} onClick={() => send.mutate()}>
              <Send className="h-3.5 w-3.5" /> Mark as sent
            </Button>
          )}
          {editable && (
            <Button disabled={save.isPending || !form.title.trim()} onClick={() => save.mutate()}>
              {save.isPending ? "Saving…" : rfq ? "Save changes" : "Create RFQ"}
            </Button>
          )}
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
        </>
      }
    >
      <ErrorNote error={save.error ?? send.error} />

      <Section title="Enquiry">
        <Grid cols={3}>
          <Field label="Title" className="sm:col-span-3">
            <Input
              disabled={!editable}
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              placeholder="e.g. Q3 antibiotics restock"
            />
          </Field>
          <Field label="Responses due">
            <Input
              type="date"
              disabled={!editable}
              value={form.response_due}
              onChange={(e) => setForm({ ...form, response_due: e.target.value })}
            />
          </Field>
          <Field label="Delivery required by">
            <Input
              type="date"
              disabled={!editable}
              value={form.delivery_required_by}
              onChange={(e) => setForm({ ...form, delivery_required_by: e.target.value })}
            />
          </Field>
        </Grid>
        <div className="mt-3">
          <Field label="Terms sent to suppliers">
            <Textarea
              disabled={!editable}
              value={form.terms}
              onChange={(e) => setForm({ ...form, terms: e.target.value })}
            />
          </Field>
        </div>
      </Section>

      <Section title="Requested items">
        <LineEditor<RFQLine>
          rows={form.lines}
          readOnly={!editable}
          onChange={(lines) => setForm({ ...form, lines })}
          makeRow={emptyRfqLine}
          addLabel="Add product"
          columns={[
            {
              header: "Product",
              width: "45%",
              cell: (row, set) => (
                <ProductPicker
                  value={row.product || null}
                  disabled={!editable}
                  onChange={(id) => set({ product: id })}
                />
              ),
            },
            {
              header: "Quantity",
              width: "15%",
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
              header: "Specification",
              width: "40%",
              cell: (row, set) =>
                editable ? (
                  <Input
                    value={row.specification ?? ""}
                    onChange={(e) => set({ specification: e.target.value })}
                    placeholder="Pack size, brand acceptability, shelf life…"
                  />
                ) : (
                  <>{row.specification || "—"}</>
                ),
            },
          ]}
        />
      </Section>

      {rfq && (
        <Section
          title="Quotes received"
          hint="Record what each supplier came back with, then compare."
          action={
            rfq.status !== "AWARDED" && (
              <Button variant="secondary" onClick={() => setAddingQuote((a) => !a)}>
                <Plus className="h-3.5 w-3.5" /> {addingQuote ? "Cancel" : "Record a quote"}
              </Button>
            )
          }
        >
          {addingQuote && (
            <div className="mb-3">
              <QuoteForm rfq={rfq} onDone={() => setAddingQuote(false)} />
            </div>
          )}
          <Comparison rfq={rfq} onAwarded={onClose} />
        </Section>
      )}
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

export function RfqPage() {
  const [open, setOpen] = useState<RequestForQuotation | null>(null);
  const [creating, setCreating] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["rfqs"],
    queryFn: () => api<Paginated<RequestForQuotation>>("/api/procurement/rfqs/?page_size=200"),
  });

  const rows = data?.results ?? [];
  const current = open ? rows.find((r) => r.id === open.id) ?? open : null;

  return (
    <div>
      <PageHeader
        title="RFQ & quote comparison"
        action={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" /> New RFQ
          </Button>
        }
      />
      <p className="mb-4 max-w-3xl text-sm text-ink-500">
        One enquiry, several suppliers, one comparison table in RWF — including lead time, terms and
        the supplier's own performance score. Awarding turns the winning quote into a draft PO.
      </p>

      <DataGrid<RequestForQuotation>
        rows={rows}
        loading={isLoading}
        getRowId={(r) => r.id}
        storageKey="procurement-rfqs"
        exportName="rfqs"
        searchPlaceholder="Search RFQs by number or title…"
        emptyMessage="No RFQs yet."
        onRowClick={(r) => setOpen(r)}
        columns={[
          {
            key: "rfq_number",
            header: "RFQ",
            render: (r) => (
              <div>
                <div className="font-mono font-medium text-ink-900">{r.rfq_number || "—"}</div>
                <div className="text-xs text-ink-500">{r.title}</div>
              </div>
            ),
          },
          {
            key: "status",
            header: "Status",
            value: (r) => r.status,
            render: (r) => <StatusBadge status={r.status} label={r.status_display} />,
          },
          { key: "response_due", header: "Responses due", value: (r) => r.response_due ?? "—" },
          {
            key: "lines",
            header: "Items",
            align: "right",
            numeric: true,
            value: (r) => r.lines.length,
          },
          {
            key: "quote_count",
            header: "Quotes",
            align: "right",
            numeric: true,
            value: (r) => r.quote_count,
            render: (r) =>
              r.quote_count === 0 ? (
                <span className="text-ink-500">—</span>
              ) : (
                <Badge tone={r.quote_count >= 3 ? "success" : "warning"}>{r.quote_count}</Badge>
              ),
          },
          { key: "created_by_name", header: "Raised by", value: (r) => r.created_by_name ?? "—" },
        ]}
      />

      {creating && <RfqDrawer rfq={null} onClose={() => setCreating(false)} />}
      {current && <RfqDrawer rfq={current} onClose={() => setOpen(null)} />}
    </div>
  );
}
