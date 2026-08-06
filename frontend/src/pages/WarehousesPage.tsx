import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Building2, Pencil, Plus, Trash2, Warehouse } from "lucide-react";
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
import type {
  Paginated,
  Warehouse as WarehouseType,
  WarehouseOccupancy,
} from "../lib/types";

const TYPES: { value: WarehouseType["warehouse_type"]; label: string }[] = [
  { value: "MAIN", label: "Main distribution store" },
  { value: "SATELLITE", label: "Satellite / cross-dock" },
  { value: "COLD_STORE", label: "Dedicated cold store" },
  { value: "BONDED", label: "Bonded (customs-controlled)" },
  { value: "QUARANTINE", label: "Quarantine / hold store" },
  { value: "DISPENSARY", label: "Dispensary back-store" },
];

const BLANK = {
  code: "",
  name: "",
  warehouse_type: "MAIN" as WarehouseType["warehouse_type"],
  address_line: "",
  district: "",
  contact_person: "",
  contact_phone: "",
  is_default: false,
  is_active: true,
};

export function WarehousesPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [editing, setEditing] = useState<WarehouseType | null>(null);
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<WarehouseType | null>(null);
  const [inspecting, setInspecting] = useState<WarehouseType | null>(null);
  const [form, setForm] = useState({ ...BLANK });
  const [error, setError] = useState("");

  const warehousesQuery = useQuery({
    queryKey: ["warehouses"],
    queryFn: () => api<Paginated<WarehouseType>>("/api/inventory/warehouses/"),
  });

  const occupancyQuery = useQuery({
    queryKey: ["warehouse-occupancy", inspecting?.id],
    queryFn: () =>
      api<WarehouseOccupancy>(`/api/inventory/warehouses/${inspecting!.id}/occupancy/`),
    enabled: inspecting !== null,
  });

  const saveMutation = useMutation({
    mutationFn: () =>
      api<WarehouseType>(
        editing ? `/api/inventory/warehouses/${editing.id}/` : "/api/inventory/warehouses/",
        { method: editing ? "PATCH" : "POST", body: JSON.stringify(form) },
      ),
    onSuccess: () => {
      close();
      void qc.invalidateQueries({ queryKey: ["warehouses"] });
    },
    onError: (e: Error) => setError(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) =>
      api<void>(`/api/inventory/warehouses/${id}/`, { method: "DELETE" }),
    onSuccess: () => {
      setDeleting(null);
      void qc.invalidateQueries({ queryKey: ["warehouses"] });
    },
  });

  function close() {
    setCreating(false);
    setEditing(null);
    setError("");
    setForm({ ...BLANK });
  }

  function openEdit(w: WarehouseType) {
    setEditing(w);
    setForm({
      code: w.code,
      name: w.name,
      warehouse_type: w.warehouse_type,
      address_line: w.address_line,
      district: w.district,
      contact_person: w.contact_person,
      contact_phone: w.contact_phone,
      is_default: w.is_default,
      is_active: w.is_active,
    });
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (form.code.trim() && form.name.trim()) saveMutation.mutate();
  }

  const rows = warehousesQuery.data?.results ?? [];

  return (
    <div className="max-w-6xl">
      <button
        onClick={() => navigate("/inventory")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> Inventory Home
      </button>

      <PageHeader
        title="Warehouses & Facilities"
        action={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" /> Add Warehouse
          </Button>
        }
      />
      <p className="mb-4 text-sm text-ink-500">
        Every facility this organization stores stock in — main store, cross-dock, bonded
        warehouse, quarantine hold. Zones and bins hang off a warehouse, so stock is
        addressable down to facility → zone → bin.
      </p>

      <DataGrid<WarehouseType>
        rows={rows}
        loading={warehousesQuery.isLoading}
        getRowId={(w) => w.id}
        storageKey="warehouses"
        exportName="warehouses"
        searchPlaceholder="Search by code, name, type or district…"
        emptyMessage="No warehouses yet. Add the main store to begin."
        onRowClick={(w) => setInspecting(w)}
        columns={[
          {
            key: "code",
            header: "Code",
            render: (w) => (
              <span className="flex items-center gap-2 font-mono font-semibold text-ink-900">
                <Warehouse className="h-4 w-4 text-brand-600" />
                {w.code}
              </span>
            ),
          },
          { key: "name", header: "Facility Name" },
          {
            key: "warehouse_type",
            header: "Type",
            render: (w) => (
              <Badge tone={w.warehouse_type === "COLD_STORE" ? "warning" : "neutral"}>
                {TYPES.find((t) => t.value === w.warehouse_type)?.label ?? w.warehouse_type}
              </Badge>
            ),
          },
          { key: "district", header: "District", value: (w) => w.district || "—" },
          { key: "zones_count", header: "Zones", align: "center", numeric: true, value: (w) => w.zones_count },
          { key: "bins_count", header: "Bins", align: "center", numeric: true, value: (w) => w.bins_count },
          {
            key: "is_default",
            header: "Default",
            align: "center",
            value: (w) => (w.is_default ? "Default" : ""),
            render: (w) => (w.is_default ? <Badge tone="success">Default</Badge> : <span className="text-ink-400">—</span>),
          },
          {
            key: "is_active",
            header: "Status",
            align: "center",
            value: (w) => (w.is_active ? "Active" : "Inactive"),
            render: (w) => (
              <Badge tone={w.is_active ? "success" : "neutral"}>
                {w.is_active ? "Active" : "Inactive"}
              </Badge>
            ),
          },
          {
            key: "actions",
            header: "Actions",
            align: "right",
            fixed: true,
            sortable: false,
            render: (w) => (
              <div className="flex justify-end gap-1">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    openEdit(w);
                  }}
                  className="rounded-md p-1.5 text-ink-500 hover:bg-surface-100 hover:text-ink-900"
                  aria-label="Edit warehouse"
                >
                  <Pencil className="h-4 w-4" />
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setDeleting(w);
                  }}
                  className="rounded-md p-1.5 text-ink-500 hover:bg-red-50 hover:text-red-600"
                  aria-label="Delete warehouse"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ),
          },
        ]}
      />

      {(creating || editing) && (
        <Modal
          title={editing ? `Edit ${editing.name}` : "Add Warehouse"}
          onClose={close}
        >
          <form onSubmit={submit} className="flex flex-col gap-4">
            {error && (
              <div className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-700">{error}</div>
            )}
            <div className="grid grid-cols-2 gap-3">
              <TextField
                label="Code"
                value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value })}
                placeholder="e.g. WH1"
                required
                autoFocus
              />
              <SelectField
                label="Facility Type"
                value={form.warehouse_type}
                onChange={(e) =>
                  setForm({
                    ...form,
                    warehouse_type: e.target.value as WarehouseType["warehouse_type"],
                  })
                }
              >
                {TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </SelectField>
            </div>
            <TextField
              label="Facility Name"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="e.g. Kigali Main Distribution Store"
              required
            />
            <div className="grid grid-cols-2 gap-3">
              <TextField
                label="Address"
                value={form.address_line}
                onChange={(e) => setForm({ ...form, address_line: e.target.value })}
              />
              <TextField
                label="District"
                value={form.district}
                onChange={(e) => setForm({ ...form, district: e.target.value })}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <TextField
                label="Contact Person"
                value={form.contact_person}
                onChange={(e) => setForm({ ...form, contact_person: e.target.value })}
              />
              <TextField
                label="Contact Phone"
                value={form.contact_phone}
                onChange={(e) => setForm({ ...form, contact_phone: e.target.value })}
              />
            </div>
            <div className="flex flex-col gap-2 text-sm">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={form.is_default}
                  onChange={(e) => setForm({ ...form, is_default: e.target.checked })}
                />
                Default facility — stock lands here when a receipt names no warehouse
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
                {saveMutation.isPending ? "Saving…" : editing ? "Save Changes" : "Add Warehouse"}
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {inspecting && (
        <Modal
          title={`${inspecting.name} — Zone Occupancy`}
          onClose={() => setInspecting(null)}
        >
          {occupancyQuery.isLoading && <p className="text-sm text-ink-500">Loading…</p>}
          {occupancyQuery.data && occupancyQuery.data.zones.length === 0 && (
            <p className="text-sm text-ink-500">
              No storage zones in this facility yet — create one under Zones &amp; Bins.
            </p>
          )}
          <div className="flex flex-col gap-3">
            {(occupancyQuery.data?.zones ?? []).map((z) => (
              <Card key={z.zone} className="p-4">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-2 text-sm font-semibold text-ink-900">
                    <Building2 className="h-4 w-4 text-brand-600" />
                    {z.zone_name}
                  </span>
                  <Badge tone={z.zone_type === "COLD_CHAIN" ? "warning" : "neutral"}>
                    {z.zone_type}
                  </Badge>
                </div>
                <div className="mt-3 h-2 w-full rounded-full bg-surface-100">
                  <div
                    className="h-2 rounded-full bg-brand-600"
                    style={{ width: `${Math.min(z.utilisation_percent, 100)}%` }}
                  />
                </div>
                <div className="mt-2 grid grid-cols-4 gap-2 text-xs text-ink-600">
                  <div>
                    <div className="font-mono font-semibold text-ink-900">
                      {z.bins_occupied}/{z.bins_total}
                    </div>
                    bins used ({z.utilisation_percent}%)
                  </div>
                  <div>
                    <div className="font-mono font-semibold text-ink-900">{z.batches}</div>
                    batches
                  </div>
                  <div>
                    <div className="font-mono font-semibold text-ink-900">{z.units}</div>
                    units
                  </div>
                  <div>
                    <div className="font-mono font-semibold text-ink-900">{z.stock_value}</div>
                    stock value
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </Modal>
      )}

      {deleting && (
        <ConfirmModal
          title="Delete Warehouse"
          message={`Delete "${deleting.name}"? Zones in this facility will be detached, not deleted.`}
          confirmLabel="Delete"
          busy={deleteMutation.isPending}
          onClose={() => setDeleting(null)}
          onConfirm={() => deleteMutation.mutate(deleting.id)}
        />
      )}
    </div>
  );
}
