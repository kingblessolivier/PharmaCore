import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  CheckCircle2,
  ClipboardList,
  ListPlus,
  Plus,
  Send,
  Trash2,
  XCircle,
} from "lucide-react";
import { useState, type FormEvent } from "react";
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
import type { Paginated, PickTask, PickWave, Product, StorageZone, Warehouse } from "../lib/types";

const STATUS_TONE: Record<string, string> = {
  DRAFT: "neutral",
  RELEASED: "warning",
  PICKING: "warning",
  PICKED: "success",
  CANCELLED: "danger",
};

const TASK_TONE: Record<string, string> = {
  PENDING: "neutral",
  ASSIGNED: "warning",
  PICKED: "success",
  SHORT: "danger",
  CANCELLED: "neutral",
};

type Demand = { product: number; quantity: number; reference_type: string; reference_id: string };

const BLANK_WAVE = {
  wave_no: "",
  strategy: "DISCRETE" as PickWave["strategy"],
  warehouse: 0,
  zone: 0,
  planned_for: "",
  notes: "",
};

export function PickWavesPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { user } = useAuth();
  const orgId = user?.organization ?? 0;

  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<PickWave | null>(null);
  const [openWave, setOpenWave] = useState<PickWave | null>(null);
  const [building, setBuilding] = useState<PickWave | null>(null);
  const [confirming, setConfirming] = useState<PickTask | null>(null);
  const [form, setForm] = useState({ ...BLANK_WAVE });
  const [demands, setDemands] = useState<Demand[]>([
    { product: 0, quantity: 1, reference_type: "", reference_id: "" },
  ]);
  const [pickedQty, setPickedQty] = useState(0);
  const [shortReason, setShortReason] = useState("");
  const [error, setError] = useState("");

  const wavesQuery = useQuery({
    queryKey: ["pick-waves", orgId],
    queryFn: () => api<Paginated<PickWave>>(`/api/inventory/pick-waves/?organization=${orgId}`),
    enabled: orgId > 0,
  });

  const warehousesQuery = useQuery({
    queryKey: ["warehouses"],
    queryFn: () => api<Paginated<Warehouse>>("/api/inventory/warehouses/"),
    enabled: creating,
  });

  const zonesQuery = useQuery({
    queryKey: ["storage-zones"],
    queryFn: () => api<Paginated<StorageZone>>("/api/inventory/storage-zones/"),
    enabled: creating,
  });

  const productsQuery = useQuery({
    queryKey: ["products", "for-picking"],
    queryFn: () => api<Paginated<Product>>("/api/catalog/products/?page_size=500"),
    enabled: building !== null,
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api<PickWave>("/api/inventory/pick-waves/", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          organization: orgId,
          warehouse: form.warehouse || null,
          zone: form.zone || null,
          planned_for: form.planned_for || null,
        }),
      }),
    onSuccess: (wave) => {
      setCreating(false);
      setForm({ ...BLANK_WAVE });
      setBuilding(wave);
      void qc.invalidateQueries({ queryKey: ["pick-waves"] });
    },
    onError: (e: Error) => setError(e.message),
  });

  const buildMutation = useMutation({
    mutationFn: () =>
      api<PickWave>(`/api/inventory/pick-waves/${building!.id}/build_tasks/`, {
        method: "POST",
        body: JSON.stringify({ demands: demands.filter((d) => d.product && d.quantity > 0) }),
      }),
    onSuccess: (wave) => {
      setBuilding(null);
      setDemands([{ product: 0, quantity: 1, reference_type: "", reference_id: "" }]);
      setOpenWave(wave);
      void qc.invalidateQueries({ queryKey: ["pick-waves"] });
    },
    onError: (e: Error) => setError(e.message),
  });

  const releaseMutation = useMutation({
    mutationFn: (id: number) =>
      api<PickWave>(`/api/inventory/pick-waves/${id}/release/`, {
        method: "POST",
        body: JSON.stringify({}),
      }),
    onSuccess: (wave) => {
      setOpenWave(wave);
      void qc.invalidateQueries({ queryKey: ["pick-waves"] });
    },
    onError: (e: Error) => setError(e.message),
  });

  const cancelMutation = useMutation({
    mutationFn: (id: number) =>
      api<PickWave>(`/api/inventory/pick-waves/${id}/cancel/`, {
        method: "POST",
        body: JSON.stringify({}),
      }),
    onSuccess: (wave) => {
      setOpenWave(wave);
      void qc.invalidateQueries({ queryKey: ["pick-waves"] });
    },
    onError: (e: Error) => setError(e.message),
  });

  const confirmPickMutation = useMutation({
    mutationFn: () =>
      api<PickTask>(`/api/inventory/pick-tasks/${confirming!.id}/confirm/`, {
        method: "POST",
        body: JSON.stringify({ quantity_picked: pickedQty, short_reason: shortReason }),
      }),
    onSuccess: async () => {
      setConfirming(null);
      setShortReason("");
      await qc.invalidateQueries({ queryKey: ["pick-waves"] });
      if (openWave) {
        const fresh = await api<PickWave>(`/api/inventory/pick-waves/${openWave.id}/`);
        setOpenWave(fresh);
      }
    },
    onError: (e: Error) => setError(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) =>
      api<void>(`/api/inventory/pick-waves/${id}/`, { method: "DELETE" }),
    onSuccess: () => {
      setDeleting(null);
      void qc.invalidateQueries({ queryKey: ["pick-waves"] });
    },
  });

  function submitWave(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (form.wave_no.trim()) createMutation.mutate();
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
        title="Wave Picking"
        action={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" /> New Wave
          </Button>
        }
      />
      <p className="mb-4 text-sm text-ink-500 max-w-3xl">
        A wave is a batch of orders released to the floor as one pass. Tasks are built FEFO —
        soonest expiry first — then walk-ordered by aisle, shelf and bin. Releasing reserves the
        stock, so two waves can never promise the same units.
      </p>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
      )}

      <DataGrid<PickWave>
        rows={wavesQuery.data?.results ?? []}
        loading={wavesQuery.isLoading}
        getRowId={(w) => w.id}
        storageKey="pick-waves"
        exportName="pick-waves"
        searchPlaceholder="Search waves by number, strategy or status…"
        emptyMessage="No pick waves yet."
        onRowClick={(w) => setOpenWave(w)}
        columns={[
          {
            key: "wave_no",
            header: "Wave",
            render: (w) => (
              <span className="flex items-center gap-2 font-mono font-semibold text-ink-900">
                <ClipboardList className="h-4 w-4 text-brand-600" />
                {w.wave_no}
              </span>
            ),
          },
          { key: "strategy", header: "Strategy" },
          {
            key: "status",
            header: "Status",
            align: "center",
            render: (w) => <Badge tone={STATUS_TONE[w.status] ?? "neutral"}>{w.status}</Badge>,
          },
          { key: "warehouse_name", header: "Warehouse", value: (w) => w.warehouse_name ?? "—" },
          { key: "zone_name", header: "Zone", value: (w) => w.zone_name ?? "—" },
          {
            key: "tasks",
            header: "Tasks",
            align: "right",
            numeric: true,
            value: (w) => w.task_summary.total,
            render: (w) => (
              <span className="font-mono">
                {w.task_summary.picked}/{w.task_summary.total}
              </span>
            ),
          },
          {
            key: "short",
            header: "Short",
            align: "right",
            numeric: true,
            value: (w) => w.task_summary.short,
            render: (w) =>
              w.task_summary.short > 0 ? (
                <span className="font-mono font-semibold text-red-600">{w.task_summary.short}</span>
              ) : (
                <span className="text-ink-400">0</span>
              ),
          },
          {
            key: "units",
            header: "Units",
            align: "right",
            numeric: true,
            value: (w) => w.task_summary.units_requested,
            render: (w) => (
              <span className="font-mono">
                {w.task_summary.units_picked}/{w.task_summary.units_requested}
              </span>
            ),
          },
          { key: "assigned_to_username", header: "Picker", value: (w) => w.assigned_to_username ?? "—" },
          {
            key: "actions",
            header: "Actions",
            align: "right",
            fixed: true,
            sortable: false,
            render: (w) => (
              <div className="flex justify-end gap-1">
                {w.status === "DRAFT" && (
                  <>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setBuilding(w);
                      }}
                      className="rounded-md p-1.5 text-ink-500 hover:bg-surface-100 hover:text-ink-900"
                      aria-label="Build tasks"
                    >
                      <ListPlus className="h-4 w-4" />
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        releaseMutation.mutate(w.id);
                      }}
                      className="rounded-md p-1.5 text-ink-500 hover:bg-surface-100 hover:text-ink-900"
                      aria-label="Release wave"
                    >
                      <Send className="h-4 w-4" />
                    </button>
                  </>
                )}
                {(w.status === "RELEASED" || w.status === "PICKING") && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      cancelMutation.mutate(w.id);
                    }}
                    className="rounded-md p-1.5 text-ink-500 hover:bg-red-50 hover:text-red-600"
                    aria-label="Cancel wave"
                  >
                    <XCircle className="h-4 w-4" />
                  </button>
                )}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setDeleting(w);
                  }}
                  className="rounded-md p-1.5 text-ink-500 hover:bg-red-50 hover:text-red-600"
                  aria-label="Delete wave"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ),
          },
        ]}
      />

      {creating && (
        <Drawer title="New Pick Wave" onClose={() => setCreating(false)}>
          <form onSubmit={submitWave} className="flex flex-col gap-4">
            <TextField
              label="Wave Number"
              value={form.wave_no}
              onChange={(e) => setForm({ ...form, wave_no: e.target.value })}
              placeholder="e.g. W-2026-0042"
              required
              autoFocus
            />
            <SelectField
              label="Strategy"
              value={form.strategy}
              onChange={(e) =>
                setForm({ ...form, strategy: e.target.value as PickWave["strategy"] })
              }
            >
              <option value="DISCRETE">Discrete — one order at a time</option>
              <option value="BATCH">Batch — same product across orders</option>
              <option value="ZONE">Zone — split by storage zone</option>
              <option value="WAVE">Wave — time-boxed release</option>
              <option value="CLUSTER">Cluster — multi-order cart</option>
            </SelectField>
            <div className="grid grid-cols-2 gap-3">
              <SelectField
                label="Warehouse"
                value={form.warehouse}
                onChange={(e) => setForm({ ...form, warehouse: Number(e.target.value) })}
              >
                <option value={0}>— Any —</option>
                {(warehousesQuery.data?.results ?? []).map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name}
                  </option>
                ))}
              </SelectField>
              <SelectField
                label="Zone"
                value={form.zone}
                onChange={(e) => setForm({ ...form, zone: Number(e.target.value) })}
              >
                <option value={0}>— Any —</option>
                {(zonesQuery.data?.results ?? []).map((z) => (
                  <option key={z.id} value={z.id}>
                    {z.name}
                  </option>
                ))}
              </SelectField>
            </div>
            <TextField
              label="Planned For"
              type="date"
              value={form.planned_for}
              onChange={(e) => setForm({ ...form, planned_for: e.target.value })}
            />
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setCreating(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? "Creating…" : "Create & Add Demand"}
              </Button>
            </div>
          </form>
        </Drawer>
      )}

      {building && (
        <Drawer title={`Build Tasks — ${building.wave_no}`} onClose={() => setBuilding(null)}>
          <div className="flex flex-col gap-4">
            <p className="text-sm text-ink-600">
              Each demand line is split across as many batches as it takes, soonest expiry first.
              A demand that cannot be fully covered still produces a short task for the gap.
            </p>
            {demands.map((d, i) => (
              <div key={i} className="grid grid-cols-[1fr_5rem] gap-2">
                <SelectField
                  label={i === 0 ? "Product" : ""}
                  value={d.product}
                  onChange={(e) => {
                    const next = [...demands];
                    next[i] = { ...d, product: Number(e.target.value) };
                    setDemands(next);
                  }}
                >
                  <option value={0}>— Select product —</option>
                  {(productsQuery.data?.results ?? []).map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.generic_name} {p.strength}
                    </option>
                  ))}
                </SelectField>
                <TextField
                  label={i === 0 ? "Qty" : ""}
                  type="number"
                  value={String(d.quantity)}
                  onChange={(e) => {
                    const next = [...demands];
                    next[i] = { ...d, quantity: Number(e.target.value) };
                    setDemands(next);
                  }}
                />
              </div>
            ))}
            <Button
              variant="secondary"
              onClick={() =>
                setDemands([
                  ...demands,
                  { product: 0, quantity: 1, reference_type: "", reference_id: "" },
                ])
              }
            >
              <Plus className="h-4 w-4" /> Add Line
            </Button>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setBuilding(null)}>
                Cancel
              </Button>
              <Button onClick={() => buildMutation.mutate()} disabled={buildMutation.isPending}>
                {buildMutation.isPending ? "Building…" : "Build FEFO Tasks"}
              </Button>
            </div>
          </div>
        </Drawer>
      )}

      {openWave && (
        <Drawer title={`${openWave.wave_no} — Pick List`} onClose={() => setOpenWave(null)}>
          <Card className="mb-4 p-4 text-xs">
            <div className="flex items-center justify-between">
              <Badge tone={STATUS_TONE[openWave.status] ?? "neutral"}>{openWave.status}</Badge>
              <span className="text-ink-600">
                {openWave.task_summary.picked} picked · {openWave.task_summary.short} short ·{" "}
                {openWave.task_summary.total} total
              </span>
            </div>
            {openWave.status === "DRAFT" && openWave.task_summary.total > 0 && (
              <Button
                className="mt-3"
                onClick={() => releaseMutation.mutate(openWave.id)}
                disabled={releaseMutation.isPending}
              >
                <Send className="h-4 w-4" /> Release to Floor
              </Button>
            )}
          </Card>
          <div className="max-h-80 overflow-y-auto">
            {openWave.tasks.map((t) => (
              <div
                key={t.id}
                className="flex items-center justify-between border-b border-line py-2 text-xs"
              >
                <div>
                  <div className="font-semibold text-ink-900">
                    #{t.sequence} {t.product_name}
                  </div>
                  <div className="text-ink-500">
                    Batch {t.batch_number || "—"} · exp {t.expiry_date ?? "—"} · bin{" "}
                    {t.bin_code ?? "unassigned"}
                  </div>
                  {t.short_reason && <div className="text-red-600">{t.short_reason}</div>}
                </div>
                <div className="flex items-center gap-3 text-right">
                  <div>
                    <div className="font-mono font-semibold">
                      {t.quantity_picked}/{t.quantity_requested}
                    </div>
                    <Badge tone={TASK_TONE[t.status] ?? "neutral"}>{t.status}</Badge>
                  </div>
                  {(t.status === "ASSIGNED" || t.status === "PENDING") && (
                    <button
                      onClick={() => {
                        setConfirming(t);
                        setPickedQty(t.quantity_requested);
                      }}
                      className="rounded-md p-1.5 text-ink-500 hover:bg-surface-100 hover:text-emerald-600"
                      aria-label="Confirm pick"
                    >
                      <CheckCircle2 className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </div>
            ))}
            {openWave.tasks.length === 0 && (
              <p className="text-sm text-ink-500">
                No tasks yet — build them from demand lines first.
              </p>
            )}
          </div>
        </Drawer>
      )}

      {confirming && (
        <Drawer title={`Confirm Pick — ${confirming.product_name}`} onClose={() => setConfirming(null)}>
          <div className="flex flex-col gap-4">
            <p className="text-sm text-ink-600">
              Requested {confirming.quantity_requested} from bin {confirming.bin_code ?? "—"}.
              Record what actually came off the shelf; a short pick is recorded as short, and the
              unpicked reservation returns to free stock.
            </p>
            <TextField
              label="Quantity Picked"
              type="number"
              value={String(pickedQty)}
              onChange={(e) => setPickedQty(Number(e.target.value))}
              autoFocus
            />
            {pickedQty < confirming.quantity_requested && (
              <TextField
                label="Short Reason"
                value={shortReason}
                onChange={(e) => setShortReason(e.target.value)}
                placeholder="e.g. Bin held only 18"
              />
            )}
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setConfirming(null)}>
                Cancel
              </Button>
              <Button
                onClick={() => confirmPickMutation.mutate()}
                disabled={confirmPickMutation.isPending}
              >
                {confirmPickMutation.isPending ? "Confirming…" : "Confirm Pick"}
              </Button>
            </div>
          </div>
        </Drawer>
      )}

      {deleting && (
        <ConfirmModal
          title="Delete Pick Wave"
          message={`Delete ${deleting.wave_no}? Cancel it first if stock is still reserved against its tasks.`}
          confirmLabel="Delete"
          busy={deleteMutation.isPending}
          onClose={() => setDeleting(null)}
          onConfirm={() => deleteMutation.mutate(deleting.id)}
        />
      )}
    </div>
  );
}
