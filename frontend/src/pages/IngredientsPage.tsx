import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Edit2, FlaskConical, Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Card, Modal, PageHeader, Spinner, TextField } from "../components/ui";
import { api } from "../lib/api";
import type { ActiveIngredient, Paginated } from "../lib/types";

export function IngredientsPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<ActiveIngredient | null>(null);
  const [name, setName] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["active-ingredients"],
    queryFn: () => api<Paginated<ActiveIngredient>>("/api/catalog/active-ingredients/"),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api<ActiveIngredient>("/api/catalog/active-ingredients/", {
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
      api<ActiveIngredient>(`/api/catalog/active-ingredients/${editing?.id}/`, {
        method: "PUT",
        body: JSON.stringify({ name }),
      }),
    onSuccess: () => {
      setEditing(null);
      void qc.invalidateQueries({ queryKey: ["active-ingredients"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api<void>(`/api/catalog/active-ingredients/${id}/`, { method: "DELETE" }),
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
    <div className="max-w-5xl">
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
      <p className="mb-4 text-sm text-ink-500">
        Full CRUD management for International Nonproprietary Names (INN) active ingredients.
      </p>

      {isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {data && (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-line bg-surface-100 text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-3">Active Ingredient (INN)</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((ing) => (
                <tr key={ing.id} className="border-b border-line last:border-0 hover:bg-surface-50">
                  <td className="px-4 py-3 font-semibold text-ink-900 flex items-center gap-2">
                    <FlaskConical className="h-4 w-4 text-brand-600" />
                    {ing.name}
                  </td>
                  <td className="px-4 py-3 text-right flex items-center justify-end gap-1">
                    <button
                      onClick={() => startEdit(ing)}
                      className="rounded-md p-1.5 text-ink-500 hover:bg-surface-200 hover:text-ink-900"
                      aria-label="Edit ingredient"
                    >
                      <Edit2 className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => deleteMutation.mutate(ing.id)}
                      className="rounded-md p-1.5 text-ink-500 hover:bg-red-50 hover:text-red-600"
                      aria-label="Delete ingredient"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
              {data.results.length === 0 && (
                <tr>
                  <td colSpan={2} className="px-4 py-8 text-center text-ink-500">
                    No active ingredients recorded yet. Click "Add Active Ingredient" to create one.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Card>
      )}

      {creating && (
        <Modal title="Add Active Ingredient (INN)" onClose={() => setCreating(false)}>
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
        </Modal>
      )}

      {editing && (
        <Modal title="Edit Active Ingredient (INN)" onClose={() => setEditing(null)}>
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
        </Modal>
      )}
    </div>
  );
}
