import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Edit2, Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Badge, Button, Card, Modal, PageHeader, SelectField, Spinner, TextField } from "../components/ui";
import { api } from "../lib/api";
import type { ActiveIngredient, Paginated, ProductInteraction } from "../lib/types";

export function InteractionsPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<ProductInteraction | null>(null);

  const [ingA, setIngA] = useState<number>(0);
  const [ingB, setIngB] = useState<number>(0);
  const [severity, setSeverity] = useState<"MINOR" | "MODERATE" | "MAJOR">("MODERATE");
  const [effect, setEffect] = useState("");
  const [management, setManagement] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["product-interactions"],
    queryFn: () => api<Paginated<ProductInteraction>>("/api/catalog/product-interactions/"),
  });

  const ingredientsQuery = useQuery({
    queryKey: ["all-ingredients"],
    queryFn: () => api<Paginated<ActiveIngredient>>("/api/catalog/active-ingredients/?page_size=100"),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api<ProductInteraction>("/api/catalog/product-interactions/", {
        method: "POST",
        body: JSON.stringify({
          ingredient_a: ingA,
          ingredient_b: ingB,
          severity,
          effect,
          management,
        }),
      }),
    onSuccess: () => {
      setCreating(false);
      void qc.invalidateQueries({ queryKey: ["product-interactions"] });
    },
  });

  const updateMutation = useMutation({
    mutationFn: () =>
      api<ProductInteraction>(`/api/catalog/product-interactions/${editing?.id}/`, {
        method: "PATCH",
        body: JSON.stringify({
          severity,
          effect,
          management,
        }),
      }),
    onSuccess: () => {
      setEditing(null);
      void qc.invalidateQueries({ queryKey: ["product-interactions"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api<void>(`/api/catalog/product-interactions/${id}/`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["product-interactions"] }),
  });

  function startCreate() {
    const list = ingredientsQuery.data?.results ?? [];
    setIngA(list[0]?.id ?? 0);
    setIngB(list[1]?.id ?? list[0]?.id ?? 0);
    setSeverity("MODERATE");
    setEffect("");
    setManagement("");
    setCreating(true);
  }

  function startEdit(i: ProductInteraction) {
    setEditing(i);
    setSeverity(i.severity);
    setEffect(i.effect || "");
    setManagement(i.management || "");
  }

  function submitCreate(e: FormEvent) {
    e.preventDefault();
    if (ingA && ingB) createMutation.mutate();
  }

  function submitUpdate(e: FormEvent) {
    e.preventDefault();
    if (editing) updateMutation.mutate();
  }

  const filtered = (data?.results ?? []).filter(
    (i) =>
      i.ingredient_a_name.toLowerCase().includes(search.toLowerCase()) ||
      i.ingredient_b_name.toLowerCase().includes(search.toLowerCase()) ||
      i.effect.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="max-w-5xl">
      <button
        onClick={() => navigate("/catalog")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> Catalog Home
      </button>

      <PageHeader
        title="Clinical Drug-Drug Interactions & Safety Directory"
        action={
          <Button onClick={startCreate}>
            <Plus className="h-4 w-4" /> Add Drug Interaction
          </Button>
        }
      />
      <p className="mb-4 text-sm text-ink-500">
        Full CRUD management for active pharmaceutical ingredient interaction rules and DrugBank severity alerts.
      </p>

      <div className="mb-4 flex items-center gap-2 rounded-md border border-line bg-surface-0 px-3 py-2">
        <input
          className="w-full bg-transparent text-sm outline-none"
          placeholder="Search by ingredient A, ingredient B, or clinical outcome..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

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
                <th className="px-4 py-3">Active Ingredient A</th>
                <th className="px-4 py-3">Active Ingredient B</th>
                <th className="px-4 py-3">Severity</th>
                <th className="px-4 py-3">Clinical Effect</th>
                <th className="px-4 py-3">Management / Advice</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((i) => (
                <tr key={i.id} className="border-b border-line last:border-0 hover:bg-surface-50">
                  <td className="px-4 py-3 font-semibold text-ink-900">{i.ingredient_a_name}</td>
                  <td className="px-4 py-3 font-semibold text-ink-900">{i.ingredient_b_name}</td>
                  <td className="px-4 py-3">
                    <Badge
                      tone={
                        i.severity === "MAJOR"
                          ? "critical"
                          : i.severity === "MODERATE"
                            ? "warning"
                            : "neutral"
                      }
                    >
                      {i.severity}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-ink-700">{i.effect || "—"}</td>
                  <td className="px-4 py-3 text-ink-700">{i.management || "—"}</td>
                  <td className="px-4 py-3 text-right flex items-center justify-end gap-1">
                    <button
                      onClick={() => startEdit(i)}
                      className="rounded-md p-1.5 text-ink-500 hover:bg-surface-200 hover:text-ink-900"
                      aria-label="Edit interaction"
                    >
                      <Edit2 className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => deleteMutation.mutate(i.id)}
                      className="rounded-md p-1.5 text-ink-500 hover:bg-red-50 hover:text-red-600"
                      aria-label="Delete interaction"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-ink-500">
                    {search ? "No drug interactions match your search." : "No clinical drug interactions recorded. Click 'Add Drug Interaction' to create one."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Card>
      )}

      {creating && (
        <Modal title="Add Drug Interaction Rule" onClose={() => setCreating(false)}>
          <form onSubmit={submitCreate} className="flex flex-col gap-4">
            <SelectField
              label="Ingredient A"
              value={ingA}
              onChange={(e) => setIngA(Number(e.target.value))}
            >
              {(ingredientsQuery.data?.results ?? []).map((ing) => (
                <option key={ing.id} value={ing.id}>
                  {ing.name}
                </option>
              ))}
            </SelectField>
            <SelectField
              label="Ingredient B"
              value={ingB}
              onChange={(e) => setIngB(Number(e.target.value))}
            >
              {(ingredientsQuery.data?.results ?? []).map((ing) => (
                <option key={ing.id} value={ing.id}>
                  {ing.name}
                </option>
              ))}
            </SelectField>
            <SelectField
              label="Severity"
              value={severity}
              onChange={(e) => setSeverity(e.target.value as "MINOR" | "MODERATE" | "MAJOR")}
            >
              <option value="MINOR">Minor</option>
              <option value="MODERATE">Moderate</option>
              <option value="MAJOR">Major</option>
            </SelectField>
            <TextField
              label="Clinical Effect"
              value={effect}
              onChange={(e) => setEffect(e.target.value)}
              placeholder="e.g. Increased risk of bleeding or nephrotoxicity"
            />
            <TextField
              label="Management Advice"
              value={management}
              onChange={(e) => setManagement(e.target.value)}
              placeholder="e.g. Avoid co-administration or monitor renal function"
            />
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setCreating(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? "Adding…" : "Add Interaction"}
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {editing && (
        <Modal title="Edit Drug Interaction Rule" onClose={() => setEditing(null)}>
          <form onSubmit={submitUpdate} className="flex flex-col gap-4">
            <div className="text-sm font-medium text-ink-900">
              Interaction: <span className="text-brand-700">{editing.ingredient_a_name}</span> + <span className="text-brand-700">{editing.ingredient_b_name}</span>
            </div>
            <SelectField
              label="Severity"
              value={severity}
              onChange={(e) => setSeverity(e.target.value as "MINOR" | "MODERATE" | "MAJOR")}
            >
              <option value="MINOR">Minor</option>
              <option value="MODERATE">Moderate</option>
              <option value="MAJOR">Major</option>
            </SelectField>
            <TextField
              label="Clinical Effect"
              value={effect}
              onChange={(e) => setEffect(e.target.value)}
            />
            <TextField
              label="Management Advice"
              value={management}
              onChange={(e) => setManagement(e.target.value)}
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
