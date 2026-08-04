import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Search, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import {
  Badge,
  Button,
  ConfirmModal,
  Modal,
  PageHeader,
  SelectField,
  Spinner,
  TextField,
} from "../components/ui";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { isAdmin } from "../lib/roles";
import type { Paginated, Product, TaxClass } from "../lib/types";

const DOSAGE_FORMS = [
  "TABLET",
  "CAPSULE",
  "SYRUP",
  "INJECTION",
  "OINTMENT",
  "DROPS",
  "INHALER",
  "OTHER",
];
const TAX_CLASSES: { value: TaxClass; label: string }[] = [
  { value: "A", label: "A — Exempt" },
  { value: "B", label: "B — 18% VAT" },
  { value: "C", label: "C — Zero-rated" },
  { value: "D", label: "D — Special" },
];
const STORAGE = ["AMBIENT", "COLD_CHAIN", "FROZEN"];

interface ProductForm {
  generic_name: string;
  brand_name: string;
  dosage_form: string;
  strength: string;
  pack_size: string;
  tax_class: TaxClass;
  storage_condition: string;
  requires_prescription: boolean;
  reorder_level: number;
}

function ProductFormModal({ product, onClose }: { product?: Product; onClose: () => void }) {
  const qc = useQueryClient();
  const editing = Boolean(product);
  const [form, setForm] = useState<ProductForm>({
    generic_name: product?.generic_name ?? "",
    brand_name: product?.brand_name ?? "",
    dosage_form: product?.dosage_form ?? "TABLET",
    strength: product?.strength ?? "",
    pack_size: product?.pack_size ?? "",
    tax_class: product?.tax_class ?? "B",
    storage_condition: product?.storage_condition ?? "AMBIENT",
    requires_prescription: product?.requires_prescription ?? false,
    reorder_level: product?.reorder_level ?? 0,
  });
  const [error, setError] = useState<string | null>(null);

  const set = <K extends keyof ProductForm>(k: K, v: ProductForm[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  const mutation = useMutation({
    mutationFn: () =>
      api<Product>(editing ? `/api/catalog/products/${product!.id}/` : "/api/catalog/products/", {
        method: editing ? "PATCH" : "POST",
        body: JSON.stringify(form),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["products"] });
      onClose();
    },
    onError: (err) => {
      setError(
        err instanceof ApiError && err.status === 403
          ? "You don't have permission to do that."
          : "Could not save the product.",
      );
    },
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    mutation.mutate();
  }

  return (
    <Modal title={editing ? "Edit medicine" : "New medicine"} onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <TextField
          label="Generic name"
          value={form.generic_name}
          onChange={(e) => set("generic_name", e.target.value)}
          required
          autoFocus
        />
        <TextField
          label="Brand name"
          value={form.brand_name}
          onChange={(e) => set("brand_name", e.target.value)}
        />
        <div className="grid grid-cols-2 gap-3">
          <SelectField
            label="Form"
            value={form.dosage_form}
            onChange={(e) => set("dosage_form", e.target.value)}
          >
            {DOSAGE_FORMS.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </SelectField>
          <TextField
            label="Strength"
            value={form.strength}
            onChange={(e) => set("strength", e.target.value)}
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <SelectField
            label="Tax class"
            value={form.tax_class}
            onChange={(e) => set("tax_class", e.target.value as TaxClass)}
          >
            {TAX_CLASSES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </SelectField>
          <SelectField
            label="Storage"
            value={form.storage_condition}
            onChange={(e) => set("storage_condition", e.target.value)}
          >
            {STORAGE.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </SelectField>
        </div>
        <div className="grid grid-cols-2 items-end gap-3">
          <TextField
            label="Reorder level"
            type="number"
            value={String(form.reorder_level)}
            onChange={(e) => set("reorder_level", Number(e.target.value))}
          />
          <label className="flex items-center gap-2 py-2 text-sm text-ink-700">
            <input
              type="checkbox"
              checked={form.requires_prescription}
              onChange={(e) => set("requires_prescription", e.target.checked)}
            />
            Prescription required
          </label>
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? "Saving…" : editing ? "Save changes" : "Create"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export function ProductsPage() {
  const { user } = useAuth();
  const admin = isAdmin(user);
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Product | null>(null);
  const [deleting, setDeleting] = useState<Product | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["products", search],
    queryFn: () =>
      api<Paginated<Product>>(`/api/catalog/products/?search=${encodeURIComponent(search)}`),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api<void>(`/api/catalog/products/${id}/`, { method: "DELETE" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["products"] });
      setDeleting(null);
    },
  });

  return (
    <div>
      <PageHeader
        title="Catalog"
        action={
          admin && (
            <Button onClick={() => setCreating(true)}>
              <Plus className="h-4 w-4" /> New medicine
            </Button>
          )
        }
      />

      <div className="mb-4 flex items-center gap-2 rounded-md border border-line bg-surface-0 px-3 py-2">
        <Search className="h-4 w-4 text-ink-500" />
        <input
          className="w-full bg-transparent text-sm outline-none"
          placeholder="Search medicines by name, ATC, or GTIN…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}
      {isError && <p className="text-sm text-red-600">Failed to load products.</p>}

      {data && (
        <div className="overflow-hidden rounded-lg border border-line bg-surface-0">
          <table className="w-full text-sm">
            <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-2.5">Medicine</th>
                <th className="px-4 py-2.5">Form</th>
                <th className="px-4 py-2.5">Strength</th>
                <th className="px-4 py-2.5">Tax</th>
                <th className="px-4 py-2.5">Rx</th>
                {admin && <th className="px-4 py-2.5 text-right">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {data.results.map((p) => (
                <tr key={p.id} className="border-b border-line last:border-0 hover:bg-surface-100">
                  <td className="px-4 py-2.5">
                    <div className="font-medium">{p.generic_name}</div>
                    {p.brand_name && <div className="text-xs text-ink-500">{p.brand_name}</div>}
                  </td>
                  <td className="px-4 py-2.5 text-ink-700">{p.dosage_form}</td>
                  <td className="px-4 py-2.5 font-mono text-ink-700">{p.strength || "—"}</td>
                  <td className="px-4 py-2.5 font-mono">{p.tax_class}</td>
                  <td className="px-4 py-2.5">
                    {p.requires_prescription && <Badge>Rx</Badge>}
                  </td>
                  {admin && (
                    <td className="px-4 py-2.5">
                      <div className="flex justify-end gap-1">
                        <button
                          onClick={() => setEditing(p)}
                          className="rounded-md p-1.5 text-ink-500 hover:bg-surface-100 hover:text-ink-900"
                          aria-label={`Edit ${p.generic_name}`}
                        >
                          <Pencil className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => setDeleting(p)}
                          className="rounded-md p-1.5 text-ink-500 hover:bg-red-50 hover:text-red-600"
                          aria-label={`Delete ${p.generic_name}`}
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
              {data.results.length === 0 && (
                <tr>
                  <td colSpan={admin ? 6 : 5} className="px-4 py-8 text-center text-ink-500">
                    {search ? "No medicines match your search." : "No medicines yet."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {creating && <ProductFormModal onClose={() => setCreating(false)} />}
      {editing && <ProductFormModal product={editing} onClose={() => setEditing(null)} />}
      {deleting && (
        <ConfirmModal
          title="Delete medicine"
          message={`Delete "${deleting.generic_name}"? This is recorded in the audit log.`}
          busy={deleteMutation.isPending}
          onConfirm={() => deleteMutation.mutate(deleting.id)}
          onClose={() => setDeleting(null)}
        />
      )}
    </div>
  );
}
