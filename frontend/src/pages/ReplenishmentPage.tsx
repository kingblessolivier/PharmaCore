import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  CalendarClock,
  Grid3x3,
  Pencil,
  Plus,
  RefreshCw,
  ShoppingCart,
  Snowflake,
  Trash2,
} from "lucide-react";
import { Fragment, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import {
  Badge,
  Button,
  Card,
  ConfirmModal,
  PageHeader,
  SelectField,
  TextField,
} from "../components/ui";
import { DataGrid } from "../components/DataGrid";
import { Drawer } from "../components/RecordKit";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type {
  AbcXyzMatrix,
  NearExpiryRow,
  Paginated,
  Product,
  RecomputeResult,
  ReorderRule,
  SlowStockRow,
  SuggestedOrder,
} from "../lib/types";

type Tab = "rules" | "suggestions" | "matrix" | "slow" | "expiry";

const TABS: { key: Tab; label: string; icon: typeof ShoppingCart }[] = [
  { key: "rules", label: "Reorder Policy", icon: RefreshCw },
  { key: "suggestions", label: "Suggested Orders", icon: ShoppingCart },
  { key: "matrix", label: "ABC / XYZ", icon: Grid3x3 },
  { key: "slow", label: "Slow & Dead Stock", icon: Snowflake },
  { key: "expiry", label: "Near Expiry", icon: CalendarClock },
];

const URGENCY_TONE: Record<string, string> = {
  CRITICAL: "danger",
  HIGH: "warning",
  WATCH: "neutral",
  MEDIUM: "warning",
  LOW: "neutral",
};

const BLANK = {
  product: 0,
  min_level: 0,
  max_level: 0,
  reorder_point: 0,
  reorder_quantity: 0,
  par_level: 0,
  safety_stock: 0,
  lead_time_days: 7,
  review_period_days: 30,
  service_level_percent: "95",
  is_auto_calculated: true,
  is_active: true,
  notes: "",
};

export function ReplenishmentPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { user } = useAuth();
  const orgId = user?.organization ?? 0;

  const [tab, setTab] = useState<Tab>("rules");
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<ReorderRule | null>(null);
  const [deleting, setDeleting] = useState<ReorderRule | null>(null);
  const [form, setForm] = useState({ ...BLANK });
  const [error, setError] = useState("");
  const [recomputed, setRecomputed] = useState<RecomputeResult | null>(null);

  const orgQuery = `?organization=${orgId}`;

  const rulesQuery = useQuery({
    queryKey: ["reorder-rules", orgId],
    queryFn: () => api<Paginated<ReorderRule>>(`/api/inventory/reorder-rules/${orgQuery}`),
    enabled: orgId > 0,
  });

  const productsQuery = useQuery({
    queryKey: ["products", "for-reorder"],
    queryFn: () => api<Paginated<Product>>("/api/catalog/products/?page_size=500"),
    enabled: creating || editing !== null,
  });

  const suggestionsQuery = useQuery({
    queryKey: ["reorder-suggestions", orgId],
    queryFn: () =>
      api<SuggestedOrder[]>(`/api/inventory/reorder-rules/suggestions/${orgQuery}`),
    enabled: orgId > 0 && tab === "suggestions",
  });

  const matrixQuery = useQuery({
    queryKey: ["abc-xyz", orgId],
    queryFn: () => api<AbcXyzMatrix>(`/api/inventory/reorder-rules/abc_xyz/${orgQuery}`),
    enabled: orgId > 0 && tab === "matrix",
  });

  const slowQuery = useQuery({
    queryKey: ["slow-dead", orgId],
    queryFn: () => api<SlowStockRow[]>(`/api/inventory/reorder-rules/slow_dead/${orgQuery}`),
    enabled: orgId > 0 && tab === "slow",
  });

  const expiryQuery = useQuery({
    queryKey: ["near-expiry", orgId],
    queryFn: () =>
      api<NearExpiryRow[]>(`/api/inventory/reorder-rules/near_expiry/${orgQuery}`),
    enabled: orgId > 0 && tab === "expiry",
  });

  const recomputeMutation = useMutation({
    mutationFn: () =>
      api<RecomputeResult>("/api/inventory/reorder-rules/recompute/", {
        method: "POST",
        body: JSON.stringify({ organization: orgId, days: 90 }),
      }),
    onSuccess: (result) => {
      setRecomputed(result);
      void qc.invalidateQueries({ queryKey: ["reorder-rules"] });
      void qc.invalidateQueries({ queryKey: ["abc-xyz"] });
      void qc.invalidateQueries({ queryKey: ["reorder-suggestions"] });
    },
  });

  const saveMutation = useMutation({
    mutationFn: () =>
      api<ReorderRule>(
        editing
          ? `/api/inventory/reorder-rules/${editing.id}/`
          : "/api/inventory/reorder-rules/",
        {
          method: editing ? "PATCH" : "POST",
          body: JSON.stringify({ ...form, organization: orgId }),
        },
      ),
    onSuccess: () => {
      close();
      void qc.invalidateQueries({ queryKey: ["reorder-rules"] });
    },
    onError: (e: Error) => setError(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) =>
      api<void>(`/api/inventory/reorder-rules/${id}/`, { method: "DELETE" }),
    onSuccess: () => {
      setDeleting(null);
      void qc.invalidateQueries({ queryKey: ["reorder-rules"] });
    },
  });

  function close() {
    setCreating(false);
    setEditing(null);
    setError("");
    setForm({ ...BLANK });
  }

  function openEdit(r: ReorderRule) {
    setEditing(r);
    setForm({
      product: r.product,
      min_level: r.min_level,
      max_level: r.max_level,
      reorder_point: r.reorder_point,
      reorder_quantity: r.reorder_quantity,
      par_level: r.par_level,
      safety_stock: r.safety_stock,
      lead_time_days: r.lead_time_days,
      review_period_days: r.review_period_days,
      service_level_percent: r.service_level_percent,
      is_auto_calculated: r.is_auto_calculated,
      is_active: r.is_active,
      notes: r.notes,
    });
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (form.product) saveMutation.mutate();
  }

  return (
    <div className="max-w-6xl">
      <button
        onClick={() => navigate("/inventory")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> Inventory Home
      </button>

      <PageHeader
        title="Replenishment & Stock Intelligence"
        action={
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              onClick={() => recomputeMutation.mutate()}
              disabled={recomputeMutation.isPending || !orgId}
            >
              <RefreshCw className="h-4 w-4" />
              {recomputeMutation.isPending ? "Recomputing…" : "Recompute from demand"}
            </Button>
            <Button onClick={() => setCreating(true)}>
              <Plus className="h-4 w-4" /> Add Rule
            </Button>
          </div>
        }
      />
      <p className="mb-4 text-sm text-ink-500">
        Min/max, reorder point and par level are the levers a buyer turns. Recompute sets them
        from observed demand — lead-time cover plus safety stock sized to the service level.
        Rules marked <strong>manual</strong> keep their hand-set numbers.
      </p>

      {recomputed && (
        <Card className="mb-4 border-brand-200 bg-brand-50 p-4 text-sm">
          <div className="font-semibold text-ink-900">
            Recomputed over {recomputed.window_days} days
          </div>
          <p className="mt-1 text-ink-700">
            {recomputed.products_analysed} products analysed · {recomputed.rules_created} rules
            created · {recomputed.rules_updated} updated · annual consumption value{" "}
            <span className="font-mono">{recomputed.annual_consumption_value}</span>
          </p>
        </Card>
      )}

      <div className="mb-4 flex flex-wrap gap-1 border-b border-line">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium ${
              tab === t.key
                ? "border-brand-600 text-brand-700"
                : "border-transparent text-ink-500 hover:text-ink-900"
            }`}
          >
            <t.icon className="h-4 w-4" />
            {t.label}
          </button>
        ))}
      </div>

      {tab === "rules" && (
        <DataGrid<ReorderRule>
          rows={rulesQuery.data?.results ?? []}
          loading={rulesQuery.isLoading}
          getRowId={(r) => r.id}
          storageKey="reorder-rules"
          exportName="reorder-rules"
          searchPlaceholder="Search by product, class or supplier…"
          emptyMessage="No reorder policy yet. Recompute builds one from movement history."
          columns={[
            { key: "product_name", header: "Product" },
            {
              key: "class",
              header: "ABC/XYZ",
              align: "center",
              value: (r) => `${r.abc_class}${r.xyz_class}`,
              render: (r) =>
                r.abc_class ? (
                  <Badge tone={r.abc_class === "A" ? "success" : r.abc_class === "B" ? "warning" : "neutral"}>
                    {r.abc_class}
                    {r.xyz_class}
                  </Badge>
                ) : (
                  <span className="text-ink-400">—</span>
                ),
            },
            { key: "on_hand", header: "On Hand", align: "right", numeric: true, value: (r) => r.on_hand },
            {
              key: "reorder_point",
              header: "Reorder Point",
              align: "right",
              numeric: true,
              value: (r) => r.reorder_point,
              render: (r) => (
                <span className={r.on_hand <= r.reorder_point ? "font-semibold text-red-600" : ""}>
                  {r.reorder_point}
                </span>
              ),
            },
            { key: "max_level", header: "Max", align: "right", numeric: true, value: (r) => r.max_level },
            { key: "safety_stock", header: "Safety", align: "right", numeric: true, value: (r) => r.safety_stock },
            {
              key: "avg_daily_demand",
              header: "Daily Demand",
              align: "right",
              numeric: true,
              value: (r) => Number(r.avg_daily_demand),
              render: (r) => <span className="font-mono">{Number(r.avg_daily_demand).toFixed(2)}</span>,
            },
            { key: "lead_time_days", header: "Lead (d)", align: "right", numeric: true, value: (r) => r.lead_time_days },
            {
              key: "is_auto_calculated",
              header: "Mode",
              align: "center",
              value: (r) => (r.is_auto_calculated ? "Auto" : "Manual"),
              render: (r) => (
                <Badge tone={r.is_auto_calculated ? "neutral" : "warning"}>
                  {r.is_auto_calculated ? "Auto" : "Manual"}
                </Badge>
              ),
            },
            {
              key: "actions",
              header: "Actions",
              align: "right",
              fixed: true,
              sortable: false,
              render: (r) => (
                <div className="flex justify-end gap-1">
                  <button
                    onClick={() => openEdit(r)}
                    className="rounded-md p-1.5 text-ink-500 hover:bg-surface-100 hover:text-ink-900"
                    aria-label="Edit rule"
                  >
                    <Pencil className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => setDeleting(r)}
                    className="rounded-md p-1.5 text-ink-500 hover:bg-red-50 hover:text-red-600"
                    aria-label="Delete rule"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              ),
            },
          ]}
        />
      )}

      {tab === "suggestions" && (
        <DataGrid<SuggestedOrder>
          rows={suggestionsQuery.data ?? []}
          loading={suggestionsQuery.isLoading}
          getRowId={(s) => s.product}
          storageKey="reorder-suggestions"
          exportName="suggested-orders"
          searchPlaceholder="Search suggestions by product or supplier…"
          emptyMessage="Nothing is at or below its reorder point. Stock cover is healthy."
          columns={[
            { key: "product_name", header: "Product" },
            {
              key: "urgency",
              header: "Urgency",
              align: "center",
              render: (s) => <Badge tone={URGENCY_TONE[s.urgency] ?? "neutral"}>{s.urgency}</Badge>,
            },
            { key: "free_stock", header: "Free Stock", align: "right", numeric: true, value: (s) => s.free_stock },
            { key: "reserved", header: "Reserved", align: "right", numeric: true, value: (s) => s.reserved },
            { key: "reorder_point", header: "ROP", align: "right", numeric: true, value: (s) => s.reorder_point },
            {
              key: "days_of_cover",
              header: "Cover (d)",
              align: "right",
              numeric: true,
              value: (s) => s.days_of_cover ?? -1,
              render: (s) => <span className="font-mono">{s.days_of_cover ?? "—"}</span>,
            },
            {
              key: "suggested_quantity",
              header: "Order Qty",
              align: "right",
              numeric: true,
              value: (s) => s.suggested_quantity,
              render: (s) => <span className="font-mono font-semibold">{s.suggested_quantity}</span>,
            },
            {
              key: "estimated_cost",
              header: "Est. Cost",
              align: "right",
              numeric: true,
              value: (s) => Number(s.estimated_cost),
              render: (s) => <span className="font-mono">{s.estimated_cost}</span>,
            },
            {
              key: "preferred_supplier_name",
              header: "Preferred Supplier",
              value: (s) => s.preferred_supplier_name ?? "—",
            },
          ]}
        />
      )}

      {tab === "matrix" && (
        <div>
          {matrixQuery.isLoading && <p className="text-sm text-ink-500">Loading…</p>}
          {matrixQuery.data && (
            <>
              <div className="grid grid-cols-4 gap-2 text-sm">
                <div />
                {["X", "Y", "Z"].map((x) => (
                  <div key={x} className="pb-1 text-center text-xs font-semibold text-ink-500">
                    {x} — {x === "X" ? "steady" : x === "Y" ? "variable" : "erratic"}
                  </div>
                ))}
                {["A", "B", "C"].map((a) => (
                  <Fragment key={a}>
                    <div className="flex items-center text-xs font-semibold text-ink-500">
                      {a} — {a === "A" ? "top 80% value" : a === "B" ? "next 15%" : "bottom 5%"}
                    </div>
                    {["X", "Y", "Z"].map((x) => {
                      const cell = matrixQuery.data.cells[`${a}${x}`];
                      return (
                        <Card key={`${a}${x}`} className="p-3">
                          <div className="text-xs font-semibold text-ink-500">
                            {a}
                            {x}
                          </div>
                          <div className="mt-1 font-mono text-lg font-semibold text-ink-900">
                            {cell?.count ?? 0}
                          </div>
                          <div className="text-xs text-ink-500">
                            {cell?.units ?? 0} units · {cell?.value ?? "0.00"}
                          </div>
                        </Card>
                      );
                    })}
                  </Fragment>
                ))}
              </div>
              <p className="mt-4 text-sm text-ink-500">
                {matrixQuery.data.total_rules} classified rules
                {matrixQuery.data.unclassified > 0 &&
                  ` · ${matrixQuery.data.unclassified} unclassified (recompute to classify)`}
                . AX deserves tight automatic replenishment; CZ deserves a big buffer and no
                attention.
              </p>
            </>
          )}
        </div>
      )}

      {tab === "slow" && (
        <DataGrid<SlowStockRow>
          rows={slowQuery.data ?? []}
          loading={slowQuery.isLoading}
          getRowId={(r) => r.batch}
          storageKey="slow-dead-stock"
          exportName="slow-dead-stock"
          searchPlaceholder="Search by product or batch…"
          emptyMessage="Nothing is sitting idle. Every lot has moved recently."
          columns={[
            { key: "product_name", header: "Product" },
            { key: "batch_number", header: "Batch", render: (r) => <span className="font-mono">{r.batch_number}</span> },
            {
              key: "category",
              header: "Classification",
              align: "center",
              render: (r) => (
                <Badge tone={r.category === "DEAD" ? "danger" : r.category === "NEVER_MOVED" ? "danger" : "warning"}>
                  {r.category.replace("_", " ")}
                </Badge>
              ),
            },
            { key: "days_idle", header: "Days Idle", align: "right", numeric: true, value: (r) => r.days_idle },
            { key: "quantity_available", header: "Qty", align: "right", numeric: true, value: (r) => r.quantity_available },
            {
              key: "capital_tied",
              header: "Capital Tied Up",
              align: "right",
              numeric: true,
              value: (r) => Number(r.capital_tied),
              render: (r) => <span className="font-mono font-semibold">{r.capital_tied}</span>,
            },
            { key: "last_moved_on", header: "Last Moved", value: (r) => r.last_moved_on ?? "never" },
            { key: "expiry_date", header: "Expires" },
          ]}
        />
      )}

      {tab === "expiry" && (
        <DataGrid<NearExpiryRow>
          rows={expiryQuery.data ?? []}
          loading={expiryQuery.isLoading}
          getRowId={(r) => r.batch}
          storageKey="near-expiry"
          exportName="near-expiry"
          searchPlaceholder="Search by product, batch or action…"
          emptyMessage="Nothing is approaching expiry inside the horizon."
          columns={[
            { key: "product_name", header: "Product" },
            { key: "batch_number", header: "Batch", render: (r) => <span className="font-mono">{r.batch_number}</span> },
            {
              key: "days_to_expiry",
              header: "Days Left",
              align: "right",
              numeric: true,
              value: (r) => r.days_to_expiry,
              render: (r) => (
                <span className={r.days_to_expiry <= 30 ? "font-semibold text-red-600" : ""}>
                  {r.days_to_expiry}
                </span>
              ),
            },
            { key: "quantity_available", header: "Qty", align: "right", numeric: true, value: (r) => r.quantity_available },
            {
              key: "sell_through_days",
              header: "Sell-through (d)",
              align: "right",
              numeric: true,
              value: (r) => r.sell_through_days ?? -1,
              render: (r) => <span className="font-mono">{r.sell_through_days ?? "—"}</span>,
            },
            {
              key: "will_clear_before_expiry",
              header: "Clears in Time?",
              align: "center",
              value: (r) => (r.will_clear_before_expiry ? "Yes" : "No"),
              render: (r) => (
                <Badge tone={r.will_clear_before_expiry ? "success" : "danger"}>
                  {r.will_clear_before_expiry ? "Yes" : "No"}
                </Badge>
              ),
            },
            {
              key: "recommended_action",
              header: "Recommended Action",
              render: (r) => (
                <Badge tone={URGENCY_TONE[r.urgency] ?? "neutral"}>
                  {r.recommended_action.replace(/_/g, " ")}
                </Badge>
              ),
            },
            {
              key: "value_at_risk",
              header: "Value at Risk",
              align: "right",
              numeric: true,
              value: (r) => Number(r.value_at_risk),
              render: (r) => <span className="font-mono font-semibold">{r.value_at_risk}</span>,
            },
          ]}
        />
      )}

      {(creating || editing) && (
        <Drawer title={editing ? `Edit ${editing.product_name}` : "Add Reorder Rule"} onClose={close}>
          <form onSubmit={submit} className="flex flex-col gap-4">
            {error && (
              <div className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-700">{error}</div>
            )}
            {!editing && (
              <SelectField
                label="Product"
                value={form.product}
                onChange={(e) => setForm({ ...form, product: Number(e.target.value) })}
              >
                <option value={0}>— Select Product —</option>
                {(productsQuery.data?.results ?? []).map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.generic_name} {p.strength}
                  </option>
                ))}
              </SelectField>
            )}
            <div className="grid grid-cols-2 gap-3">
              <TextField
                label="Reorder Point"
                type="number"
                value={String(form.reorder_point)}
                onChange={(e) => setForm({ ...form, reorder_point: Number(e.target.value) })}
              />
              <TextField
                label="Reorder Quantity"
                type="number"
                value={String(form.reorder_quantity)}
                onChange={(e) => setForm({ ...form, reorder_quantity: Number(e.target.value) })}
              />
              <TextField
                label="Min Level"
                type="number"
                value={String(form.min_level)}
                onChange={(e) => setForm({ ...form, min_level: Number(e.target.value) })}
              />
              <TextField
                label="Max Level"
                type="number"
                value={String(form.max_level)}
                onChange={(e) => setForm({ ...form, max_level: Number(e.target.value) })}
              />
              <TextField
                label="Par Level"
                type="number"
                value={String(form.par_level)}
                onChange={(e) => setForm({ ...form, par_level: Number(e.target.value) })}
              />
              <TextField
                label="Safety Stock"
                type="number"
                value={String(form.safety_stock)}
                onChange={(e) => setForm({ ...form, safety_stock: Number(e.target.value) })}
              />
              <TextField
                label="Lead Time (days)"
                type="number"
                value={String(form.lead_time_days)}
                onChange={(e) => setForm({ ...form, lead_time_days: Number(e.target.value) })}
              />
              <TextField
                label="Review Period (days)"
                type="number"
                value={String(form.review_period_days)}
                onChange={(e) => setForm({ ...form, review_period_days: Number(e.target.value) })}
              />
            </div>
            <TextField
              label="Service Level (%)"
              value={form.service_level_percent}
              onChange={(e) => setForm({ ...form, service_level_percent: e.target.value })}
            />
            <div className="flex flex-col gap-2 text-sm">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={form.is_auto_calculated}
                  onChange={(e) => setForm({ ...form, is_auto_calculated: e.target.checked })}
                />
                Let the engine recompute these levers each run
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                />
                Active
              </label>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={close}>
                Cancel
              </Button>
              <Button type="submit" disabled={saveMutation.isPending}>
                {saveMutation.isPending ? "Saving…" : editing ? "Save Changes" : "Add Rule"}
              </Button>
            </div>
          </form>
        </Drawer>
      )}

      {deleting && (
        <ConfirmModal
          title="Delete Reorder Rule"
          message={`Delete the replenishment policy for ${deleting.product_name}? Recompute will recreate it from demand unless the product is inactive.`}
          confirmLabel="Delete"
          busy={deleteMutation.isPending}
          onClose={() => setDeleting(null)}
          onConfirm={() => deleteMutation.mutate(deleting.id)}
        />
      )}
    </div>
  );
}
