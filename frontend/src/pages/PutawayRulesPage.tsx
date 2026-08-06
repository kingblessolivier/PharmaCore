import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, FlaskConical, MoveRight, Pencil, Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import {
  Badge,
  Button,
  Card,
  ConfirmModal,
  Modal,
  PageHeader,
  SelectField,
  TextField,
} from "../components/ui";
import { DataGrid } from "../components/DataGrid";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type {
  BinLocation,
  Paginated,
  Product,
  PutawayRule,
  PutawaySuggestion,
  StorageZone,
  Warehouse,
  ZoneType,
} from "../lib/types";

const STRATEGIES: { value: PutawayRule["strategy"]; label: string }[] = [
  { value: "ZONE_BY_CONDITION", label: "Zone matching storage condition" },
  { value: "FIXED_BIN", label: "Fixed bin (always the same slot)" },
  { value: "NEAREST_EMPTY", label: "Nearest empty bin in zone" },
  { value: "ABC_VELOCITY", label: "Fast movers nearest dispatch" },
  { value: "BULK_THEN_PICK", label: "Bulk first, overflow to pick face" },
];

const ZONE_TYPES: ZoneType[] = [
  "AMBIENT",
  "COLD_CHAIN",
  "FREEZER",
  "CONTROLLED_SAFE",
  "HAZARDOUS",
];

const BLANK = {
  name: "",
  strategy: "ZONE_BY_CONDITION" as PutawayRule["strategy"],
  priority: 100,
  warehouse: 0,
  match_product: 0,
  match_zone_type: "" as ZoneType | "",
  match_controlled_only: false,
  match_cold_chain_only: false,
  match_abc_class: "",
  target_zone: 0,
  target_bin: 0,
  is_active: true,
};

export function PutawayRulesPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { user } = useAuth();
  const orgId = user?.organization ?? 0;

  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<PutawayRule | null>(null);
  const [deleting, setDeleting] = useState<PutawayRule | null>(null);
  const [simulating, setSimulating] = useState(false);
  const [simProduct, setSimProduct] = useState(0);
  const [simWarehouse, setSimWarehouse] = useState(0);
  const [simResult, setSimResult] = useState<PutawaySuggestion | null>(null);
  const [form, setForm] = useState({ ...BLANK });
  const [error, setError] = useState("");

  const rulesQuery = useQuery({
    queryKey: ["putaway-rules", orgId],
    queryFn: () =>
      api<Paginated<PutawayRule>>(`/api/inventory/putaway-rules/?organization=${orgId}`),
    enabled: orgId > 0,
  });

  const warehousesQuery = useQuery({
    queryKey: ["warehouses"],
    queryFn: () => api<Paginated<Warehouse>>("/api/inventory/warehouses/"),
  });

  const zonesQuery = useQuery({
    queryKey: ["storage-zones"],
    queryFn: () => api<Paginated<StorageZone>>("/api/inventory/storage-zones/"),
  });

  const binsQuery = useQuery({
    queryKey: ["bin-locations"],
    queryFn: () => api<Paginated<BinLocation>>("/api/inventory/bin-locations/"),
  });

  const productsQuery = useQuery({
    queryKey: ["products", "for-putaway"],
    queryFn: () => api<Paginated<Product>>("/api/catalog/products/?page_size=500"),
    enabled: creating || editing !== null || simulating,
  });

  const saveMutation = useMutation({
    mutationFn: () =>
      api<PutawayRule>(
        editing ? `/api/inventory/putaway-rules/${editing.id}/` : "/api/inventory/putaway-rules/",
        {
          method: editing ? "PATCH" : "POST",
          body: JSON.stringify({
            ...form,
            organization: orgId,
            warehouse: form.warehouse || null,
            match_product: form.match_product || null,
            target_zone: form.target_zone || null,
            target_bin: form.target_bin || null,
          }),
        },
      ),
    onSuccess: () => {
      close();
      void qc.invalidateQueries({ queryKey: ["putaway-rules"] });
    },
    onError: (e: Error) => setError(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) =>
      api<void>(`/api/inventory/putaway-rules/${id}/`, { method: "DELETE" }),
    onSuccess: () => {
      setDeleting(null);
      void qc.invalidateQueries({ queryKey: ["putaway-rules"] });
    },
  });

  const simulateMutation = useMutation({
    mutationFn: () => {
      const wh = simWarehouse ? `&warehouse=${simWarehouse}` : "";
      return api<PutawaySuggestion>(
        `/api/inventory/putaway-rules/simulate/?organization=${orgId}&product=${simProduct}${wh}`,
      );
    },
    onSuccess: (result) => setSimResult(result),
    onError: (e: Error) => setError(e.message),
  });

  function close() {
    setCreating(false);
    setEditing(null);
    setError("");
    setForm({ ...BLANK });
  }

  function openEdit(r: PutawayRule) {
    setEditing(r);
    setForm({
      name: r.name,
      strategy: r.strategy,
      priority: r.priority,
      warehouse: r.warehouse ?? 0,
      match_product: r.match_product ?? 0,
      match_zone_type: r.match_zone_type,
      match_controlled_only: r.match_controlled_only,
      match_cold_chain_only: r.match_cold_chain_only,
      match_abc_class: r.match_abc_class,
      target_zone: r.target_zone ?? 0,
      target_bin: r.target_bin ?? 0,
      is_active: r.is_active,
    });
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (form.name.trim()) saveMutation.mutate();
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
        title="Put-away Rules"
        action={
          <div className="flex items-center gap-2">
            <Button variant="secondary" onClick={() => setSimulating(true)}>
              <FlaskConical className="h-4 w-4" /> Simulate
            </Button>
            <Button onClick={() => setCreating(true)}>
              <Plus className="h-4 w-4" /> Add Rule
            </Button>
          </div>
        }
      />
      <p className="mb-4 text-sm text-ink-500">
        Where a received lot goes, decided by policy rather than by whoever is holding the
        trolley. Rules are tried in priority order and the first match wins. When no rule
        matches, the product&rsquo;s own label storage condition still decides — a cold-chain
        product is never defaulted onto an ambient shelf.
      </p>

      <DataGrid<PutawayRule>
        rows={rulesQuery.data?.results ?? []}
        loading={rulesQuery.isLoading}
        getRowId={(r) => r.id}
        storageKey="putaway-rules"
        exportName="putaway-rules"
        searchPlaceholder="Search rules by name, strategy or target…"
        emptyMessage="No put-away rules yet — receipts fall back to the label storage condition."
        columns={[
          {
            key: "priority",
            header: "Priority",
            align: "right",
            numeric: true,
            value: (r) => r.priority,
            render: (r) => <span className="font-mono font-semibold">{r.priority}</span>,
          },
          { key: "name", header: "Rule" },
          {
            key: "strategy",
            header: "Strategy",
            render: (r) => (
              <Badge tone="neutral">
                {STRATEGIES.find((s) => s.value === r.strategy)?.label ?? r.strategy}
              </Badge>
            ),
          },
          {
            key: "criteria",
            header: "Matches",
            sortable: false,
            render: (r) => (
              <span className="text-xs text-ink-600">
                {[
                  r.match_product_name,
                  r.match_zone_type || null,
                  r.match_cold_chain_only ? "cold chain" : null,
                  r.match_controlled_only ? "controlled" : null,
                  r.match_abc_class ? `class ${r.match_abc_class}` : null,
                ]
                  .filter(Boolean)
                  .join(" · ") || "everything"}
              </span>
            ),
          },
          {
            key: "target",
            header: "Target",
            value: (r) => r.target_bin_code ?? r.target_zone_name ?? "—",
            render: (r) => (
              <span className="font-mono text-xs">
                {r.target_bin_code ?? r.target_zone_name ?? "—"}
              </span>
            ),
          },
          { key: "warehouse_name", header: "Warehouse", value: (r) => r.warehouse_name ?? "all" },
          {
            key: "is_active",
            header: "Status",
            align: "center",
            value: (r) => (r.is_active ? "Active" : "Inactive"),
            render: (r) => (
              <Badge tone={r.is_active ? "success" : "neutral"}>
                {r.is_active ? "Active" : "Inactive"}
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

      {(creating || editing) && (
        <Modal title={editing ? `Edit ${editing.name}` : "Add Put-away Rule"} onClose={close}>
          <form onSubmit={submit} className="flex flex-col gap-4">
            {error && (
              <div className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-700">{error}</div>
            )}
            <TextField
              label="Rule Name"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="e.g. Cold chain to the cold room"
              required
              autoFocus
            />
            <div className="grid grid-cols-2 gap-3">
              <SelectField
                label="Strategy"
                value={form.strategy}
                onChange={(e) =>
                  setForm({ ...form, strategy: e.target.value as PutawayRule["strategy"] })
                }
              >
                {STRATEGIES.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </SelectField>
              <TextField
                label="Priority (lower runs first)"
                type="number"
                value={String(form.priority)}
                onChange={(e) => setForm({ ...form, priority: Number(e.target.value) })}
              />
            </div>

            <div className="rounded-md border border-line p-3">
              <h3 className="mb-2 text-xs font-semibold uppercase text-ink-500">
                Criteria — blank means &ldquo;don&rsquo;t care&rdquo;
              </h3>
              <div className="flex flex-col gap-3">
                <SelectField
                  label="Specific Product"
                  value={form.match_product}
                  onChange={(e) => setForm({ ...form, match_product: Number(e.target.value) })}
                >
                  <option value={0}>— Any product —</option>
                  {(productsQuery.data?.results ?? []).map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.generic_name} {p.strength}
                    </option>
                  ))}
                </SelectField>
                <div className="grid grid-cols-2 gap-3">
                  <SelectField
                    label="Zone Type"
                    value={form.match_zone_type}
                    onChange={(e) =>
                      setForm({ ...form, match_zone_type: e.target.value as ZoneType | "" })
                    }
                  >
                    <option value="">— Any —</option>
                    {ZONE_TYPES.map((z) => (
                      <option key={z} value={z}>
                        {z}
                      </option>
                    ))}
                  </SelectField>
                  <SelectField
                    label="ABC Class"
                    value={form.match_abc_class}
                    onChange={(e) => setForm({ ...form, match_abc_class: e.target.value })}
                  >
                    <option value="">— Any —</option>
                    <option value="A">A</option>
                    <option value="B">B</option>
                    <option value="C">C</option>
                  </SelectField>
                </div>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={form.match_cold_chain_only}
                    onChange={(e) =>
                      setForm({ ...form, match_cold_chain_only: e.target.checked })
                    }
                  />
                  Cold-chain products only
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={form.match_controlled_only}
                    onChange={(e) =>
                      setForm({ ...form, match_controlled_only: e.target.checked })
                    }
                  />
                  Controlled substances only
                </label>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <SelectField
                label="Target Zone"
                value={form.target_zone}
                onChange={(e) => setForm({ ...form, target_zone: Number(e.target.value) })}
              >
                <option value={0}>— Decide from condition —</option>
                {(zonesQuery.data?.results ?? []).map((z) => (
                  <option key={z.id} value={z.id}>
                    {z.name} ({z.zone_type})
                  </option>
                ))}
              </SelectField>
              <SelectField
                label="Target Bin"
                value={form.target_bin}
                onChange={(e) => setForm({ ...form, target_bin: Number(e.target.value) })}
              >
                <option value={0}>— None —</option>
                {(binsQuery.data?.results ?? []).map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.bin_code} ({b.zone_name})
                  </option>
                ))}
              </SelectField>
            </div>
            <SelectField
              label="Warehouse"
              value={form.warehouse}
              onChange={(e) => setForm({ ...form, warehouse: Number(e.target.value) })}
            >
              <option value={0}>— All facilities —</option>
              {(warehousesQuery.data?.results ?? []).map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                </option>
              ))}
            </SelectField>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
              />
              Active
            </label>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={close}>
                Cancel
              </Button>
              <Button type="submit" disabled={saveMutation.isPending}>
                {saveMutation.isPending ? "Saving…" : editing ? "Save Changes" : "Add Rule"}
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {simulating && (
        <Modal
          title="Simulate Put-away"
          onClose={() => {
            setSimulating(false);
            setSimResult(null);
          }}
        >
          <div className="flex flex-col gap-4">
            <p className="text-sm text-ink-600">
              Dry-run the rule set against a product — which rule wins, and which bin it picks.
            </p>
            <SelectField
              label="Product"
              value={simProduct}
              onChange={(e) => setSimProduct(Number(e.target.value))}
            >
              <option value={0}>— Select product —</option>
              {(productsQuery.data?.results ?? []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.generic_name} {p.strength}
                </option>
              ))}
            </SelectField>
            <SelectField
              label="Warehouse"
              value={simWarehouse}
              onChange={(e) => setSimWarehouse(Number(e.target.value))}
            >
              <option value={0}>— Any —</option>
              {(warehousesQuery.data?.results ?? []).map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                </option>
              ))}
            </SelectField>
            <Button
              onClick={() => simulateMutation.mutate()}
              disabled={!simProduct || simulateMutation.isPending}
            >
              <FlaskConical className="h-4 w-4" />
              {simulateMutation.isPending ? "Running…" : "Run Simulation"}
            </Button>

            {simResult && (
              <Card className="p-4 text-sm">
                <div className="flex items-center gap-2 font-semibold text-ink-900">
                  {simResult.zone_name ?? "No zone"}
                  <MoveRight className="h-4 w-4 text-ink-400" />
                  <span className="font-mono">{simResult.bin_code ?? "no free bin"}</span>
                </div>
                <p className="mt-2 text-xs text-ink-600">{simResult.reason}</p>
                <div className="mt-3 flex flex-wrap gap-2 text-xs">
                  <Badge tone="neutral">{simResult.strategy}</Badge>
                  <Badge tone={simResult.storage_compliant ? "success" : "danger"}>
                    {simResult.storage_compliant ? "Storage compliant" : "Not compliant"}
                  </Badge>
                  <Badge tone="neutral">requires {simResult.required_zone_type}</Badge>
                  {simResult.rule_name && <Badge tone="neutral">rule: {simResult.rule_name}</Badge>}
                </div>
                {simResult.warning && (
                  <div className="mt-3 rounded-md bg-red-50 px-3 py-2 text-xs text-red-700">
                    {simResult.warning}
                  </div>
                )}
              </Card>
            )}
          </div>
        </Modal>
      )}

      {deleting && (
        <ConfirmModal
          title="Delete Put-away Rule"
          message={`Delete "${deleting.name}"? Receipts will fall through to the next matching rule.`}
          confirmLabel="Delete"
          busy={deleteMutation.isPending}
          onClose={() => setDeleting(null)}
          onConfirm={() => deleteMutation.mutate(deleting.id)}
        />
      )}
    </div>
  );
}
