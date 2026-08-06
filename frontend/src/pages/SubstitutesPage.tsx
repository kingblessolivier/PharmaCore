import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Edit2, Plus, RefreshCcw, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Badge, Button, Card, Modal, PageHeader, SelectField, Spinner, TextField } from "../components/ui";
import { api } from "../lib/api";
import type { Paginated, Product, ProductSubstitute } from "../lib/types";

export function SubstitutesPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<ProductSubstitute | null>(null);

  const [productId, setProductId] = useState<number>(0);
  const [subName, setSubName] = useState("");
  const [subStrength, setSubStrength] = useState("");
  const [subType, setSubType] = useState<"GENERIC_EQUIVALENT" | "THERAPEUTIC_ALTERNATIVE">("GENERIC_EQUIVALENT");
  const [notes, setNotes] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["product-substitutes"],
    queryFn: () => api<Paginated<ProductSubstitute>>("/api/catalog/product-substitutes/"),
  });

  const productsQuery = useQuery({
    queryKey: ["all-products"],
    queryFn: () => api<Paginated<Product>>("/api/catalog/products/?page_size=100"),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api<ProductSubstitute>("/api/catalog/product-substitutes/", {
        method: "POST",
        body: JSON.stringify({
          product: productId,
          substitute_generic_name: subName,
          substitute_strength: subStrength,
          substitute_type: subType,
          notes,
        }),
      }),
    onSuccess: () => {
      setCreating(false);
      void qc.invalidateQueries({ queryKey: ["product-substitutes"] });
    },
  });

  const updateMutation = useMutation({
    mutationFn: () =>
      api<ProductSubstitute>(`/api/catalog/product-substitutes/${editing?.id}/`, {
        method: "PATCH",
        body: JSON.stringify({
          substitute_generic_name: subName,
          substitute_strength: subStrength,
          substitute_type: subType,
          notes,
        }),
      }),
    onSuccess: () => {
      setEditing(null);
      void qc.invalidateQueries({ queryKey: ["product-substitutes"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api<void>(`/api/catalog/product-substitutes/${id}/`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["product-substitutes"] }),
  });

  function startCreate() {
    setProductId(productsQuery.data?.results[0]?.id ?? 0);
    setSubName("");
    setSubStrength("");
    setSubType("GENERIC_EQUIVALENT");
    setNotes("");
    setCreating(true);
  }

  function startEdit(s: ProductSubstitute) {
    setEditing(s);
    setSubName(s.substitute_generic_name);
    setSubStrength(s.substitute_strength);
    setSubType(s.substitute_type);
    setNotes(s.notes);
  }

  function submitCreate(e: FormEvent) {
    e.preventDefault();
    if (productId && subName) createMutation.mutate();
  }

  function submitUpdate(e: FormEvent) {
    e.preventDefault();
    if (editing && subName) updateMutation.mutate();
  }

  const filtered = (data?.results ?? []).filter(
    (s) =>
      s.substitute_generic_name.toLowerCase().includes(search.toLowerCase()) ||
      s.notes.toLowerCase().includes(search.toLowerCase()),
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
        title="Generic & Therapeutic Substitutes Directory"
        action={
          <Button onClick={startCreate}>
            <Plus className="h-4 w-4" /> Add Substitute
          </Button>
        }
      />
      <p className="mb-4 text-sm text-ink-500">
        Full CRUD management for bioequivalent generic substitutes and therapeutic alternatives.
      </p>

      <div className="mb-4 flex items-center gap-2 rounded-md border border-line bg-surface-0 px-3 py-2">
        <input
          className="w-full bg-transparent text-sm outline-none"
          placeholder="Filter by substitute medicine or notes..."
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
                <th className="px-4 py-3">Substitute Medicine</th>
                <th className="px-4 py-3">Strength</th>
                <th className="px-4 py-3">Substitution Type</th>
                <th className="px-4 py-3">Notes</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((s) => (
                <tr key={s.id} className="border-b border-line last:border-0 hover:bg-surface-50">
                  <td className="px-4 py-3 font-semibold text-ink-900 flex items-center gap-2">
                    <RefreshCcw className="h-4 w-4 text-brand-600" />
                    {s.substitute_generic_name}
                  </td>
                  <td className="px-4 py-3 font-mono text-ink-700">{s.substitute_strength || "—"}</td>
                  <td className="px-4 py-3">
                    <Badge tone="neutral">{s.substitute_type}</Badge>
                  </td>
                  <td className="px-4 py-3 text-ink-700">{s.notes || "—"}</td>
                  <td className="px-4 py-3 text-right flex items-center justify-end gap-1">
                    <button
                      onClick={() => startEdit(s)}
                      className="rounded-md p-1.5 text-ink-500 hover:bg-surface-200 hover:text-ink-900"
                      aria-label="Edit substitute"
                    >
                      <Edit2 className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => deleteMutation.mutate(s.id)}
                      className="rounded-md p-1.5 text-ink-500 hover:bg-red-50 hover:text-red-600"
                      aria-label="Delete substitute"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-ink-500">
                    {search ? "No substitutes match your filter." : "No generic or therapeutic substitutes mapped yet. Click 'Add Substitute' to create one."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Card>
      )}

      {creating && (
        <Modal title="Add Generic / Therapeutic Substitute" onClose={() => setCreating(false)}>
          <form onSubmit={submitCreate} className="flex flex-col gap-4">
            <SelectField
              label="Primary Medicine"
              value={productId}
              onChange={(e) => setProductId(Number(e.target.value))}
            >
              {(productsQuery.data?.results ?? []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.generic_name} {p.strength} ({p.dosage_form})
                </option>
              ))}
            </SelectField>
            <TextField
              label="Substitute Medicine Name"
              value={subName}
              onChange={(e) => setSubName(e.target.value)}
              placeholder="e.g. Paracetamol, Augmentin"
              required
            />
            <TextField
              label="Substitute Strength"
              value={subStrength}
              onChange={(e) => setSubStrength(e.target.value)}
              placeholder="e.g. 500mg"
            />
            <SelectField
              label="Substitution Type"
              value={subType}
              onChange={(e) =>
                setSubType(e.target.value as "GENERIC_EQUIVALENT" | "THERAPEUTIC_ALTERNATIVE")
              }
            >
              <option value="GENERIC_EQUIVALENT">Generic Equivalent</option>
              <option value="THERAPEUTIC_ALTERNATIVE">Therapeutic Alternative</option>
            </SelectField>
            <TextField
              label="Clinical Notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. Bioequivalent alternative for pediatric suspension"
            />
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setCreating(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? "Adding…" : "Add Substitute"}
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {editing && (
        <Modal title="Edit Generic / Therapeutic Substitute" onClose={() => setEditing(null)}>
          <form onSubmit={submitUpdate} className="flex flex-col gap-4">
            <TextField
              label="Substitute Medicine Name"
              value={subName}
              onChange={(e) => setSubName(e.target.value)}
              required
            />
            <TextField
              label="Substitute Strength"
              value={subStrength}
              onChange={(e) => setSubStrength(e.target.value)}
            />
            <SelectField
              label="Substitution Type"
              value={subType}
              onChange={(e) =>
                setSubType(e.target.value as "GENERIC_EQUIVALENT" | "THERAPEUTIC_ALTERNATIVE")
              }
            >
              <option value="GENERIC_EQUIVALENT">Generic Equivalent</option>
              <option value="THERAPEUTIC_ALTERNATIVE">Therapeutic Alternative</option>
            </SelectField>
            <TextField
              label="Clinical Notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
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
