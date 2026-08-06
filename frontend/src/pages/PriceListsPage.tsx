import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Edit2, Plus, Tag, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Badge, Button, Modal, PageHeader, SelectField, Spinner, TextField } from "../components/ui";
import { api } from "../lib/api";
import type { Paginated, PriceList } from "../lib/types";

export function PriceListsPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<PriceList | null>(null);

  const [name, setName] = useState("");
  const [listType, setListType] = useState<"WHOLESALE" | "RETAIL" | "PROMOTIONAL" | "CONTRACT">("RETAIL");
  const [isActive, setIsActive] = useState(true);

  const { data, isLoading } = useQuery({
    queryKey: ["price-lists"],
    queryFn: () => api<Paginated<PriceList>>("/api/catalog/price-lists/"),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api<PriceList>("/api/catalog/price-lists/", {
        method: "POST",
        body: JSON.stringify({ name, list_type: listType, is_active: isActive }),
      }),
    onSuccess: () => {
      setName("");
      setCreating(false);
      void qc.invalidateQueries({ queryKey: ["price-lists"] });
    },
  });

  const updateMutation = useMutation({
    mutationFn: () =>
      api<PriceList>(`/api/catalog/price-lists/${editing?.id}/`, {
        method: "PUT",
        body: JSON.stringify({ name, list_type: listType, is_active: isActive }),
      }),
    onSuccess: () => {
      setEditing(null);
      void qc.invalidateQueries({ queryKey: ["price-lists"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api<void>(`/api/catalog/price-lists/${id}/`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["price-lists"] }),
  });

  function startCreate() {
    setName("");
    setListType("RETAIL");
    setIsActive(true);
    setCreating(true);
  }

  function startEdit(pl: PriceList) {
    setEditing(pl);
    setName(pl.name);
    setListType(pl.list_type);
    setIsActive(pl.is_active);
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
        title="Price Lists & Tiered Pricing Engine"
        action={
          <Button onClick={startCreate}>
            <Plus className="h-4 w-4" /> Create Price List
          </Button>
        }
      />
      <p className="mb-4 text-sm text-ink-500">
        Full CRUD management for effective-dated retail, wholesale, contract, and promotional price lists.
      </p>

      {isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {data && (
        <div className="flex flex-col gap-4">
          <div className="overflow-hidden rounded-lg border border-line bg-surface-0">
            <table className="w-full text-sm">
              <thead className="border-b border-line bg-surface-100 text-left text-xs uppercase tracking-wide text-ink-500">
                <tr>
                  <th className="px-4 py-3">Price List Name</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.results.map((pl) => (
                  <tr key={pl.id} className="border-b border-line last:border-0 hover:bg-surface-50">
                    <td className="px-4 py-3 font-medium text-ink-900 flex items-center gap-2">
                      <Tag className="h-4 w-4 text-brand-600" />
                      {pl.name}
                    </td>
                    <td className="px-4 py-3">
                      <Badge tone="neutral">{pl.list_type}</Badge>
                    </td>
                    <td className="px-4 py-3">
                      <Badge tone={pl.is_active ? "success" : "warning"}>
                        {pl.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-right flex items-center justify-end gap-1">
                      <button
                        onClick={() => startEdit(pl)}
                        className="rounded-md p-1.5 text-ink-500 hover:bg-surface-200 hover:text-ink-900"
                        aria-label="Edit price list"
                      >
                        <Edit2 className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => deleteMutation.mutate(pl.id)}
                        className="rounded-md p-1.5 text-ink-500 hover:bg-red-50 hover:text-red-600"
                        aria-label="Delete price list"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))}
                {data.results.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-ink-500">
                      No price lists configured yet. Click "Create Price List" above to add one.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {creating && (
        <Modal title="Create Price List" onClose={() => setCreating(false)}>
          <form onSubmit={submitCreate} className="flex flex-col gap-4">
            <TextField
              label="Price List Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Retail Standard 2026, Wholesale Tier A"
              required
              autoFocus
            />
            <SelectField
              label="Type"
              value={listType}
              onChange={(e) =>
                setListType(e.target.value as "WHOLESALE" | "RETAIL" | "PROMOTIONAL" | "CONTRACT")
              }
            >
              <option value="RETAIL">Retail</option>
              <option value="WHOLESALE">Wholesale</option>
              <option value="PROMOTIONAL">Promotional</option>
              <option value="CONTRACT">Contract</option>
            </SelectField>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setCreating(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? "Creating…" : "Create"}
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {editing && (
        <Modal title="Edit Price List" onClose={() => setEditing(null)}>
          <form onSubmit={submitUpdate} className="flex flex-col gap-4">
            <TextField
              label="Price List Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
            <SelectField
              label="Type"
              value={listType}
              onChange={(e) =>
                setListType(e.target.value as "WHOLESALE" | "RETAIL" | "PROMOTIONAL" | "CONTRACT")
              }
            >
              <option value="RETAIL">Retail</option>
              <option value="WHOLESALE">Wholesale</option>
              <option value="PROMOTIONAL">Promotional</option>
              <option value="CONTRACT">Contract</option>
            </SelectField>
            <label className="flex items-center gap-2 text-sm text-ink-900">
              <input
                type="checkbox"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                className="rounded border-line"
              />
              Active Price List
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
        </Modal>
      )}
    </div>
  );
}
