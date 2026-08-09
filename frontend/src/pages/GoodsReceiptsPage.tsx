import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { PackageCheck, ThermometerSnowflake, XCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { DataGrid } from "../components/DataGrid";
import {
  Drawer,
  ErrorNote,
  Facts,
  Field,
  Grid,
  Input,
  LineEditor,
  Section,
  Select,
  StatusBadge,
  Textarea,
  TotalsRow,
} from "../components/RecordKit";
import { Badge, Button, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { money, num, type GoodsReceipt, type GoodsReceiptLine } from "../lib/procurement";
import type { Paginated } from "../lib/types";

const REJECTION_REASONS = [
  ["", "—"],
  ["DAMAGED", "Damaged"],
  ["SHORT_DATED", "Short-dated"],
  ["WRONG_ITEM", "Wrong item"],
  ["TEMPERATURE_ABUSED", "Temperature abused"],
] as const;

const STATUS_FILTERS = [
  ["", "All"],
  ["DRAFT", "Draft (not yet in stock)"],
  ["POSTED", "Posted"],
  ["CANCELLED", "Cancelled"],
] as const;

/* -------------------------------------------------------------------------- */

function ReceiptDrawer({ receipt, onClose }: { receipt: GoodsReceipt; onClose: () => void }) {
  const qc = useQueryClient();
  const editable = receipt.is_editable;
  const [form, setForm] = useState({
    received_on: receipt.received_on,
    supplier_delivery_note: receipt.supplier_delivery_note,
    waybill_number: receipt.waybill_number,
    vehicle_plate: receipt.vehicle_plate,
    driver_name: receipt.driver_name,
    requires_qc: receipt.requires_qc,
    cold_chain_intact: receipt.cold_chain_intact,
    packaging_intact: receipt.packaging_intact,
    temperature_on_arrival_c: receipt.temperature_on_arrival_c ?? "",
    discrepancy_note: receipt.discrepancy_note,
    notes: receipt.notes,
    lines: receipt.lines.map((l) => ({ ...l })),
  });

  const totals = useMemo(() => {
    const received = form.lines.reduce((s, l) => s + Number(l.quantity_received || 0), 0);
    const rejected = form.lines.reduce((s, l) => s + Number(l.quantity_rejected || 0), 0);
    const value = form.lines.reduce(
      (s, l) => s + num(l.unit_cost) * Number(l.quantity_received || 0),
      0,
    );
    return { received, rejected, value };
  }, [form.lines]);

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["goods-receipts"] });
    void qc.invalidateQueries({ queryKey: ["purchase-orders"] });
    void qc.invalidateQueries({ queryKey: ["procurement-overview"] });
  };

  const save = useMutation({
    mutationFn: () =>
      api<GoodsReceipt>(`/api/procurement/receipts/${receipt.id}/`, {
        method: "PATCH",
        body: JSON.stringify({
          ...form,
          temperature_on_arrival_c: form.temperature_on_arrival_c || null,
          lines: form.lines.map((l) => ({
            order_line: l.order_line,
            product: l.product,
            batch_number: l.batch_number,
            manufacture_date: l.manufacture_date || null,
            expiry_date: l.expiry_date,
            quantity_expected: Number(l.quantity_expected),
            quantity_received: Number(l.quantity_received),
            quantity_rejected: Number(l.quantity_rejected ?? 0),
            rejection_reason: l.rejection_reason ?? "",
            rejection_note: l.rejection_note ?? "",
            unit_cost: l.unit_cost || "0",
            storage_location: l.storage_location ?? "",
          })),
        }),
      }),
    onSuccess: invalidate,
  });

  const post = useMutation({
    mutationFn: async () => {
      await save.mutateAsync();
      return api<GoodsReceipt>(`/api/procurement/receipts/${receipt.id}/post/`, {
        method: "POST",
        body: "{}",
      });
    },
    onSuccess: () => {
      invalidate();
      onClose();
    },
  });

  const cancel = useMutation({
    mutationFn: () =>
      api(`/api/procurement/receipts/${receipt.id}/cancel/`, { method: "POST", body: "{}" }),
    onSuccess: () => {
      invalidate();
      onClose();
    },
  });

  return (
    <Drawer
      title={receipt.grn_number}
      badge={<StatusBadge status={receipt.status} label={receipt.status_display} />}
      subtitle={
        <>
          {receipt.po_number} · {receipt.supplier_name} → {receipt.organization_name}
        </>
      }
      onClose={onClose}
      width="max-w-5xl"
      footer={
        <>
          {editable && (
            <Button variant="secondary" disabled={cancel.isPending} onClick={() => cancel.mutate()}>
              <XCircle className="h-3.5 w-3.5" /> Cancel receipt
            </Button>
          )}
          {editable && (
            <Button variant="secondary" disabled={save.isPending} onClick={() => save.mutate()}>
              {save.isPending ? "Saving…" : "Save draft"}
            </Button>
          )}
          {editable && (
            <Button disabled={post.isPending} onClick={() => post.mutate()}>
              <PackageCheck className="h-3.5 w-3.5" />
              {post.isPending ? "Posting…" : "Post to stock"}
            </Button>
          )}
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
        </>
      }
    >
      <ErrorNote error={save.error ?? post.error ?? cancel.error} />

      {!editable && (
        <div className="mb-4 rounded-md border border-line bg-surface-50 p-3">
          <Facts
            rows={[
              ["Posted by", receipt.posted_by_name ?? "—"],
              ["Posted at", receipt.posted_at ? new Date(receipt.posted_at).toLocaleString() : "—"],
              ["Received", receipt.total_received],
              ["Rejected", receipt.total_rejected],
              ["Value (RWF)", money(receipt.goods_value_base)],
              ["Quarantined", receipt.requires_qc ? "Yes — pending QC" : "No"],
            ]}
          />
        </div>
      )}

      {editable && form.requires_qc && (
        <div className="mb-4 rounded-md border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-900">
          Posting will land these batches in <strong>quarantine</strong> with a pending quality
          check. They are not sellable until QC releases them (Inventory → Quality Control).
        </div>
      )}

      <Section title="Delivery">
        <Grid cols={4}>
          <Field label="Received on">
            <Input
              type="date"
              disabled={!editable}
              value={form.received_on}
              onChange={(e) => setForm({ ...form, received_on: e.target.value })}
            />
          </Field>
          <Field label="Supplier delivery note">
            <Input
              disabled={!editable}
              value={form.supplier_delivery_note}
              onChange={(e) => setForm({ ...form, supplier_delivery_note: e.target.value })}
            />
          </Field>
          <Field label="Waybill">
            <Input
              disabled={!editable}
              value={form.waybill_number}
              onChange={(e) => setForm({ ...form, waybill_number: e.target.value })}
            />
          </Field>
          <Field label="Vehicle plate">
            <Input
              disabled={!editable}
              value={form.vehicle_plate}
              onChange={(e) => setForm({ ...form, vehicle_plate: e.target.value })}
            />
          </Field>
          <Field label="Driver">
            <Input
              disabled={!editable}
              value={form.driver_name}
              onChange={(e) => setForm({ ...form, driver_name: e.target.value })}
            />
          </Field>
          <Field label="Temperature on arrival (°C)">
            <Input
              type="number"
              step="0.01"
              disabled={!editable}
              value={form.temperature_on_arrival_c}
              onChange={(e) => setForm({ ...form, temperature_on_arrival_c: e.target.value })}
            />
          </Field>
        </Grid>
        <div className="mt-3 flex flex-wrap gap-4">
          <label className="flex items-center gap-2 text-sm text-ink-700">
            <input
              type="checkbox"
              disabled={!editable}
              checked={form.requires_qc}
              onChange={(e) => setForm({ ...form, requires_qc: e.target.checked })}
              className="h-3.5 w-3.5 accent-brand-600"
            />
            Quarantine for QC before the stock is sellable
          </label>
          <label className="flex items-center gap-2 text-sm text-ink-700">
            <input
              type="checkbox"
              disabled={!editable}
              checked={form.cold_chain_intact}
              onChange={(e) => setForm({ ...form, cold_chain_intact: e.target.checked })}
              className="h-3.5 w-3.5 accent-brand-600"
            />
            <ThermometerSnowflake className="h-3.5 w-3.5 text-sky-600" /> Cold chain intact
          </label>
          <label className="flex items-center gap-2 text-sm text-ink-700">
            <input
              type="checkbox"
              disabled={!editable}
              checked={form.packaging_intact}
              onChange={(e) => setForm({ ...form, packaging_intact: e.target.checked })}
              className="h-3.5 w-3.5 accent-brand-600"
            />
            Packaging intact
          </label>
        </div>
      </Section>

      <Section
        title="What arrived"
        hint="Batch number and expiry are mandatory — they are what makes a recall possible."
      >
        <LineEditor<GoodsReceiptLine>
          rows={form.lines}
          readOnly={!editable}
          onChange={(lines) => setForm({ ...form, lines })}
          makeRow={() => ({ ...form.lines[0] })}
          addLabel="Add a second batch of the same line"
          emptyMessage="Nothing to receive on this order."
          columns={[
            {
              header: "Product",
              width: "22%",
              cell: (row) => <span className="font-medium">{row.product_name}</span>,
            },
            {
              header: "Batch",
              width: "14%",
              cell: (row, set) =>
                editable ? (
                  <Input
                    value={row.batch_number}
                    onChange={(e) => set({ batch_number: e.target.value })}
                    placeholder="Required"
                  />
                ) : (
                  <span className="font-mono">{row.batch_number}</span>
                ),
            },
            {
              header: "Expiry",
              width: "13%",
              cell: (row, set) =>
                editable ? (
                  <Input
                    type="date"
                    value={row.expiry_date}
                    onChange={(e) => set({ expiry_date: e.target.value })}
                  />
                ) : (
                  <>{row.expiry_date}</>
                ),
            },
            {
              header: "Expected",
              width: "9%",
              align: "right",
              cell: (row) => <span className="text-ink-500">{row.quantity_expected}</span>,
            },
            {
              header: "Received",
              width: "10%",
              align: "right",
              cell: (row, set) =>
                editable ? (
                  <Input
                    type="number"
                    min={0}
                    value={row.quantity_received}
                    onChange={(e) => set({ quantity_received: Number(e.target.value) })}
                    className="text-right"
                  />
                ) : (
                  <>{row.quantity_received}</>
                ),
            },
            {
              header: "Rejected",
              width: "10%",
              align: "right",
              cell: (row, set) =>
                editable ? (
                  <Input
                    type="number"
                    min={0}
                    value={row.quantity_rejected}
                    onChange={(e) => set({ quantity_rejected: Number(e.target.value) })}
                    className="text-right"
                  />
                ) : (
                  <>{row.quantity_rejected}</>
                ),
            },
            {
              header: "Reason",
              width: "12%",
              cell: (row, set) =>
                editable ? (
                  <Select
                    value={row.rejection_reason ?? ""}
                    onChange={(e) => set({ rejection_reason: e.target.value })}
                  >
                    {REJECTION_REASONS.map(([v, l]) => (
                      <option key={v} value={v}>
                        {l}
                      </option>
                    ))}
                  </Select>
                ) : (
                  <>{row.rejection_reason || "—"}</>
                ),
            },
            {
              header: "Unit cost",
              width: "10%",
              align: "right",
              cell: (row, set) =>
                editable ? (
                  <Input
                    type="number"
                    step="0.01"
                    value={row.unit_cost}
                    onChange={(e) => set({ unit_cost: e.target.value })}
                    className="text-right"
                  />
                ) : (
                  <>{row.unit_cost}</>
                ),
            },
            {
              header: "Variance",
              width: "10%",
              align: "right",
              cell: (row) => {
                const v = Number(row.quantity_received || 0) - Number(row.quantity_expected || 0);
                if (v === 0) return <span className="text-ink-500">—</span>;
                return (
                  <Badge tone={v > 0 ? "warning" : "danger"}>
                    {v > 0 ? `+${v} over` : `${v} short`}
                  </Badge>
                );
              },
            },
          ]}
          footer={
            <>
              <TotalsRow span={8} label="Units received" value={totals.received} />
              <TotalsRow span={8} label="Units rejected" value={totals.rejected} />
              <TotalsRow span={8} label="Value landing (RWF)" value={money(totals.value)} strong />
            </>
          }
        />
      </Section>

      <Section title="Notes">
        <Grid cols={2}>
          <Field label="Discrepancy note">
            <Textarea
              disabled={!editable}
              value={form.discrepancy_note}
              onChange={(e) => setForm({ ...form, discrepancy_note: e.target.value })}
              placeholder="What was wrong with the delivery, if anything"
            />
          </Field>
          <Field label="Internal notes">
            <Textarea
              disabled={!editable}
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
            />
          </Field>
        </Grid>
      </Section>
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

export function GoodsReceiptsPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [status, setStatus] = useState("");
  const [openId, setOpenId] = useState<number | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["goods-receipts", status],
    queryFn: () =>
      api<Paginated<GoodsReceipt>>(
        `/api/procurement/receipts/?page_size=200${status ? `&status=${status}` : ""}`,
      ),
  });

  // Deep link from "Receive goods" on a purchase order.
  useEffect(() => {
    const id = params.get("open");
    if (id) {
      setOpenId(Number(id));
      params.delete("open");
      setParams(params, { replace: true });
    }
  }, [params, setParams]);

  const rows = data?.results ?? [];
  const current = rows.find((r) => r.id === openId) ?? null;

  return (
    <div>
      <PageHeader title="Goods receipts (GRN)" />

      <DataGrid<GoodsReceipt>
        rows={rows}
        loading={isLoading}
        getRowId={(r) => r.id}
        storageKey="procurement-receipts"
        exportName="goods-receipts"
        searchPlaceholder="Search by GRN, PO, supplier, delivery note…"
        emptyMessage="No goods receipts yet."
        /* Opens the full receipt. The drawer could not show the cold-chain
           condition, the shelf life arriving and the variance against the order
           at the same time — which are precisely the three things worth seeing
           before the receipt is posted. */
        onRowClick={(r) => navigate(`/procurement/receipts/${r.id}`)}
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
            key: "grn_number",
            header: "GRN",
            render: (r) => (
              <div>
                <div className="font-mono font-medium text-ink-900">{r.grn_number}</div>
                <div className="text-xs text-ink-500">{r.received_on}</div>
              </div>
            ),
          },
          { key: "po_number", header: "Purchase order" },
          { key: "supplier_name", header: "Supplier" },
          { key: "organization_name", header: "Delivered to" },
          {
            key: "status",
            header: "Status",
            value: (r) => r.status,
            render: (r) => <StatusBadge status={r.status} label={r.status_display} />,
          },
          {
            key: "total_received",
            header: "Received",
            align: "right",
            numeric: true,
            value: (r) => r.total_received,
          },
          {
            key: "total_rejected",
            header: "Rejected",
            align: "right",
            numeric: true,
            value: (r) => r.total_rejected,
            render: (r) =>
              r.total_rejected > 0 ? (
                <Badge tone="danger">{r.total_rejected}</Badge>
              ) : (
                <span className="text-ink-500">—</span>
              ),
          },
          {
            key: "goods_value_base",
            header: "Value",
            align: "right",
            numeric: true,
            value: (r) => Number(r.goods_value_base),
            render: (r) => money(r.goods_value_base),
          },
          {
            key: "flags",
            header: "",
            fixed: true,
            sortable: false,
            render: (r) => (
              <div className="flex justify-end gap-1">
                {r.has_discrepancy && <Badge tone="warning">Discrepancy</Badge>}
                {r.requires_qc && r.status === "POSTED" && <Badge tone="info">Quarantined</Badge>}
              </div>
            ),
          },
        ]}
      />

      {current && <ReceiptDrawer receipt={current} onClose={() => setOpenId(null)} />}
    </div>
  );
}
