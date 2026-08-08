import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Edit2, FlaskConical, Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Button, PageHeader, TextField } from "../components/ui";
import { api } from "../lib/api";
import type { ActiveIngredient, Paginated } from "../lib/types";
import { DataGrid } from "../components/DataGrid";
import { Drawer } from "../components/RecordKit";

export function IngredientsPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<ActiveIngredient | null>(null);
  const [name, setName] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["active-ingredients"],
    queryFn: () => api<Paginated<ActiveIngredient>>("/api/catalog/ingredients/"),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api<ActiveIngredient>("/api/catalog/ingredients/", {
        method: "POST",
        body: JSON.stringify({ name }),
      }),
    onSuccess: () => {
      setName("");
      setCreating(false);
      void qc.invalidateQueries({ queryKey: ["active-ingredients"] });
    },
  });

  const updateMutation = useMutation({
    mutationFn: () =>
      api<ActiveIngredient>(`/api/catalog/ingredients/${editing?.id}/`, {
        method: "PUT",
        body: JSON.stringify({ name }),
      }),
    onSuccess: () => {
      setEditing(null);
      void qc.invalidateQueries({ queryKey: ["active-ingredients"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api<void>(`/api/catalog/ingredients/${id}/`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["active-ingredients"] }),
  });

  function startCreate() {
    setName("");
    setCreating(true);
  }

  function startEdit(ing: ActiveIngredient) {
    setEditing(ing);
    setName(ing.name);
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
    <div>
      <button
        onClick={() => navigate("/catalog")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> Catalog Home
      </button>

      <PageHeader
        title="Active Pharmaceutical Ingredients (INN Master)"
        action={
          <Button onClick={startCreate}>
            <Plus className="h-4 w-4" /> Add Active Ingredient
          </Button>
        }
      />
      <p className="mb-4 text-sm text-ink-500 max-w-3xl">
        Full CRUD management for International Nonproprietary Names (INN) active ingredients.
      </p>

      <DataGrid<ActiveIngredient>
        rows={data?.results ?? []}
        loading={isLoading}
        getRowId={(i) => i.id}
        storageKey="active-ingredients"
        exportName="active-ingredients"
        searchPlaceholder="Search ingredients by INN…"
        emptyMessage="No active ingredients recorded yet."
        columns={[
          {
            key: "name",
            header: "Active ingredient (INN)",
            value: (i) => i.name,
            render: (i) => (
              <span className="flex items-center gap-2 font-medium text-ink-900">
                <FlaskConical className="h-4 w-4 text-brand-600" />
                {i.name}
              </span>
            ),
          },
          {
            key: "actions",
            header: "",
            align: "right",
            fixed: true,
            sortable: false,
            render: (i) => (
              <div className="flex items-center justify-end gap-1">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    startEdit(i);
                  }}
                  className="rounded-md p-1.5 text-ink-500 hover:bg-surface-200 hover:text-ink-900"
                  aria-label="Edit ingredient"
                >
                  <Edit2 className="h-4 w-4" />
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteMutation.mutate(i.id);
                  }}
                  className="rounded-md p-1.5 text-ink-500 hover:bg-danger-50 hover:text-danger-600"
                  aria-label="Delete ingredient"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ),
          },
        ]}
      />

      {creating && (
        <Drawer title="Add Active Ingredient (INN)" onClose={() => setCreating(false)}>
          <form onSubmit={submitCreate} className="flex flex-col gap-4">
            <TextField
              label="Ingredient Name (INN)"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Paracetamol, Amoxicillin, Ibuprofen"
              required
              autoFocus
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
        <Drawer title="Edit Active Ingredient (INN)" onClose={() => setEditing(null)}>
          <form onSubmit={submitUpdate} className="flex flex-col gap-4">
            <TextField
              label="Ingredient Name (INN)"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
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
