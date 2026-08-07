import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Edit2, Factory, Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Badge, Button, PageHeader, TextField } from "../components/ui";
import { api } from "../lib/api";
import type { Manufacturer, Paginated } from "../lib/types";
import { DataGrid } from "../components/DataGrid";
import { Drawer } from "../components/RecordKit";

export function ManufacturersPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Manufacturer | null>(null);

  const [name, setName] = useState("");
  const [country, setCountry] = useState("");
  const [isActive, setIsActive] = useState(true);

  const { data, isLoading } = useQuery({
    queryKey: ["manufacturers"],
    queryFn: () => api<Paginated<Manufacturer>>("/api/catalog/manufacturers/"),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api<Manufacturer>("/api/catalog/manufacturers/", {
        method: "POST",
        body: JSON.stringify({ name, country, is_active: isActive }),
      }),
    onSuccess: () => {
      setName("");
      setCountry("");
      setCreating(false);
      void qc.invalidateQueries({ queryKey: ["manufacturers"] });
    },
  });

  const updateMutation = useMutation({
    mutationFn: () =>
      api<Manufacturer>(`/api/catalog/manufacturers/${editing?.id}/`, {
        method: "PUT",
        body: JSON.stringify({ name, country, is_active: isActive }),
      }),
    onSuccess: () => {
      setEditing(null);
      void qc.invalidateQueries({ queryKey: ["manufacturers"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api<void>(`/api/catalog/manufacturers/${id}/`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["manufacturers"] }),
  });

  function startCreate() {
    setName("");
    setCountry("");
    setIsActive(true);
    setCreating(true);
  }

  function startEdit(m: Manufacturer) {
    setEditing(m);
    setName(m.name);
    setCountry(m.country || "");
    setIsActive(m.is_active);
  }

  function submitCreate(e: FormEvent) {
    e.preventDefault();
    if (name.trim()) createMutation.mutate();
  }

  function submitUpdate(e: FormEvent) {
    e.preventDefault();
    if (name.trim() && editing) updateMutation.mutate();
  }

  return (
    <div className="max-w-5xl">
      <button
        onClick={() => navigate("/catalog")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> Catalog Home
      </button>

      <PageHeader
        title="Pharmaceutical Manufacturers Directory"
        action={
          <Button onClick={startCreate}>
            <Plus className="h-4 w-4" /> Add Manufacturer
          </Button>
        }
      />
      <p className="mb-4 text-sm text-ink-500">
        Full CRUD management for pharmaceutical manufacturing companies and GMP compliance status.
      </p>

      <DataGrid<Manufacturer>
        rows={data?.results ?? []}
        loading={isLoading}
        getRowId={(m) => m.id}
        storageKey="manufacturers"
        exportName="manufacturers"
        searchPlaceholder="Search manufacturers by name or country…"
        emptyMessage="No manufacturers recorded yet."
        columns={[
          {
            key: "name",
            header: "Manufacturer",
            value: (m) => m.name,
            render: (m) => (
              <span className="flex items-center gap-2 font-medium text-ink-900">
                <Factory className="h-4 w-4 text-brand-600" />
                {m.name}
              </span>
            ),
          },
          { key: "country", header: "Country of origin", value: (m) => m.country || "—" },
          {
            key: "is_active",
            header: "GMP status",
            value: (m) => (m.is_active ? "Compliant" : "Inactive"),
            render: (m) => (
              <Badge tone={m.is_active ? "success" : "warning"}>
                {m.is_active ? "Compliant / Active" : "Inactive"}
              </Badge>
            ),
          },
          {
            key: "actions",
            header: "",
            align: "right",
            fixed: true,
            sortable: false,
            render: (m) => (
              <div className="flex items-center justify-end gap-1">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    startEdit(m);
                  }}
                  className="rounded-md p-1.5 text-ink-500 hover:bg-surface-200 hover:text-ink-900"
                  aria-label="Edit manufacturer"
                >
                  <Edit2 className="h-4 w-4" />
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteMutation.mutate(m.id);
                  }}
                  className="rounded-md p-1.5 text-ink-500 hover:bg-danger-50 hover:text-danger-600"
                  aria-label="Delete manufacturer"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ),
          },
        ]}
      />

      {creating && (
        <Drawer title="Add Manufacturer" onClose={() => setCreating(false)}>
          <form onSubmit={submitCreate} className="flex flex-col gap-4">
            <TextField
              label="Manufacturer Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Novartis, Rwanda Pharmaceutical Ltd"
              required
              autoFocus
            />
            <TextField
              label="Country of Origin"
              value={country}
              onChange={(e) => setCountry(e.target.value)}
              placeholder="e.g. Switzerland, Rwanda, India"
            />
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setCreating(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? "Adding…" : "Add"}
              </Button>
            </div>
          </form>
        </Drawer>
      )}

      {editing && (
        <Drawer title="Edit Manufacturer" onClose={() => setEditing(null)}>
          <form onSubmit={submitUpdate} className="flex flex-col gap-4">
            <TextField
              label="Manufacturer Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
            <TextField
              label="Country of Origin"
              value={country}
              onChange={(e) => setCountry(e.target.value)}
            />
            <label className="flex items-center gap-2 text-sm text-ink-900">
              <input
                type="checkbox"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                className="rounded border-line"
              />
              Compliant / Active Manufacturer
            </label>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setEditing(null)}>
                Cancel
              </Button>
              <Button type="submit" disabled={updateMutation.isPending}>
                {updateMutation.isPending ? "Saving…" : "Save Changes"}
              </Button>
            </div>
          </form>
        </Drawer>
      )}
    </div>
  );
}
