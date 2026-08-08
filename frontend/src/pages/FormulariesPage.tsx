import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Edit2, Plus, ShieldCheck, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Badge, Button, PageHeader, SelectField, TextField } from "../components/ui";
import { api } from "../lib/api";
import type { FormularyItem, Paginated, Product } from "../lib/types";
import { DataGrid } from "../components/DataGrid";
import { Drawer } from "../components/RecordKit";

export function FormulariesPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<FormularyItem | null>(null);

  const [productId, setProductId] = useState<number>(0);
  const [schemeName, setSchemeName] = useState("");
  const [isCovered, setIsCovered] = useState(true);
  const [maxPrice, setMaxPrice] = useState("");
  const [copay, setCopay] = useState("");
  const [priorAuth, setPriorAuth] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["formulary-items"],
    queryFn: () => api<Paginated<FormularyItem>>("/api/catalog/formulary-items/"),
  });

  const productsQuery = useQuery({
    queryKey: ["all-products"],
    queryFn: () => api<Paginated<Product>>("/api/catalog/products/?page_size=100"),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api<FormularyItem>("/api/catalog/formulary-items/", {
        method: "POST",
        body: JSON.stringify({
          product: productId,
          scheme_name: schemeName,
          is_covered: isCovered,
          max_reimbursable_price: maxPrice ? Number(maxPrice) : null,
          copay_percentage: copay ? Number(copay) : null,
          requires_prior_auth: priorAuth,
        }),
      }),
    onSuccess: () => {
      setCreating(false);
      void qc.invalidateQueries({ queryKey: ["formulary-items"] });
    },
  });

  const updateMutation = useMutation({
    mutationFn: () =>
      api<FormularyItem>(`/api/catalog/formulary-items/${editing?.id}/`, {
        method: "PATCH",
        body: JSON.stringify({
          scheme_name: schemeName,
          is_covered: isCovered,
          max_reimbursable_price: maxPrice ? Number(maxPrice) : null,
          copay_percentage: copay ? Number(copay) : null,
          requires_prior_auth: priorAuth,
        }),
      }),
    onSuccess: () => {
      setEditing(null);
      void qc.invalidateQueries({ queryKey: ["formulary-items"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api<void>(`/api/catalog/formulary-items/${id}/`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["formulary-items"] }),
  });

  function startCreate() {
    setProductId(productsQuery.data?.results[0]?.id ?? 0);
    setSchemeName("RSSB / RAMA");
    setIsCovered(true);
    setMaxPrice("");
    setCopay("");
    setPriorAuth(false);
    setCreating(true);
  }

  function startEdit(f: FormularyItem) {
    setEditing(f);
    setSchemeName(f.scheme_name);
    setIsCovered(f.is_covered);
    setMaxPrice(f.max_reimbursable_price ?? "");
    setCopay(f.copay_percentage ?? "");
    setPriorAuth(f.requires_prior_auth);
  }

  function submitCreate(e: FormEvent) {
    e.preventDefault();
    if (productId && schemeName) createMutation.mutate();
  }

  function submitUpdate(e: FormEvent) {
    e.preventDefault();
    if (editing && schemeName) updateMutation.mutate();
  }

  const filtered = (data?.results ?? []).filter(
    (f) =>
      f.scheme_name.toLowerCase().includes(search.toLowerCase()) ||
      f.product_generic_name.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div>
      <button
        onClick={() => navigate("/catalog")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> Catalog Home
      </button>

      <PageHeader
        title="Insurer Formularies & Reimbursable Coverage"
        action={
          <Button onClick={startCreate}>
            <Plus className="h-4 w-4" /> Add Formulary Entry
          </Button>
        }
      />
      <p className="mb-4 text-sm text-ink-500 max-w-3xl">
        Full CRUD management for RSSB / RAMA, CBHI, MMI, and private insurer formularies and co-pay rules.
      </p>

      <div className="mb-4 flex items-center gap-2 rounded-md border border-line bg-surface-0 px-3 py-2">
        <input
          className="w-full bg-transparent text-sm outline-none"
          placeholder="Filter by scheme name or medicine name..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <DataGrid<FormularyItem>
        rows={filtered}
        loading={isLoading}
        getRowId={(r) => r.id}
        storageKey="formulary-items"
        exportName="formulary-items"
        searchPlaceholder="Search by scheme or medicine…"
        emptyMessage="No formulary entries recorded."
        columns={[
          {
            key: "scheme_name",
            header: "Insurer / scheme",
            value: (f) => f.scheme_name,
            render: (f) => (
              <span className="flex items-center gap-2 font-medium text-ink-900">
                <ShieldCheck className="h-4 w-4 text-brand-600" />
                {f.scheme_name}
              </span>
            ),
          },
          {
            key: "product_generic_name",
            header: "Medicine",
            value: (f) => f.product_generic_name,
          },
          {
            key: "is_covered",
            header: "Coverage",
            value: (f) => (f.is_covered ? "Covered" : "Not covered"),
            render: (f) => (
              <Badge tone={f.is_covered ? "success" : "critical"}>
                {f.is_covered ? "Covered" : "Not covered"}
              </Badge>
            ),
          },
          {
            key: "max_reimbursable_price",
            header: "Max reimbursable",
            align: "right",
            numeric: true,
            value: (f) => Number(f.max_reimbursable_price ?? 0),
            render: (f) => (
              <span className="font-mono text-ink-700">
                {f.max_reimbursable_price ? `RWF ${f.max_reimbursable_price}` : "—"}
              </span>
            ),
          },
          {
            key: "copay_percentage",
            header: "Co-pay",
            align: "right",
            numeric: true,
            value: (f) => Number(f.copay_percentage ?? 0),
            render: (f) => (
              <span className="font-mono text-ink-700">
                {f.copay_percentage ? `${f.copay_percentage}%` : "—"}
              </span>
            ),
          },
          {
            key: "requires_prior_auth",
            header: "Prior auth",
            value: (f) => (f.requires_prior_auth ? "Required" : "No"),
            render: (f) =>
              f.requires_prior_auth ? (
                <Badge tone="warning">Required</Badge>
              ) : (
                <span className="text-xs text-ink-500">No</span>
              ),
          },
          {
            key: "actions",
            header: "",
            align: "right",
            fixed: true,
            sortable: false,
            render: (f) => (
              <div className="flex items-center justify-end gap-1">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    startEdit(f);
                  }}
                  className="rounded-md p-1.5 text-ink-500 hover:bg-surface-200 hover:text-ink-900"
                  aria-label="Edit"
                >
                  <Edit2 className="h-4 w-4" />
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteMutation.mutate(f.id);
                  }}
                  className="rounded-md p-1.5 text-ink-500 hover:bg-danger-50 hover:text-danger-600"
                  aria-label="Delete"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ),
          },
        ]}
      />

      {creating && (
        <Drawer title="Add Formulary Entry" onClose={() => setCreating(false)}>
          <form onSubmit={submitCreate} className="flex flex-col gap-4">
            <SelectField
              label="Medicine"
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
              label="Insurer / Scheme Name"
              value={schemeName}
              onChange={(e) => setSchemeName(e.target.value)}
              placeholder="e.g. RSSB / RAMA, CBHI, MMI, SANLAM"
              required
            />
            <TextField
              label="Max Reimbursable Price (RWF)"
              type="number"
              value={maxPrice}
              onChange={(e) => setMaxPrice(e.target.value)}
              placeholder="e.g. 1500"
            />
            <TextField
              label="Co-pay Percentage (%)"
              type="number"
              value={copay}
              onChange={(e) => setCopay(e.target.value)}
              placeholder="e.g. 15"
            />
            <label className="flex items-center gap-2 text-sm text-ink-900">
              <input
                type="checkbox"
                checked={priorAuth}
                onChange={(e) => setPriorAuth(e.target.checked)}
                className="rounded border-line"
              />
              Requires Prior Authorization
            </label>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setCreating(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? "Saving…" : "Save Entry"}
              </Button>
            </div>
          </form>
        </Drawer>
      )}

      {editing && (
        <Drawer title="Edit Formulary Entry" onClose={() => setEditing(null)}>
          <form onSubmit={submitUpdate} className="flex flex-col gap-4">
            <div className="text-sm font-medium text-ink-900">
              Medicine: <span className="text-brand-700">{editing.product_generic_name}</span>
            </div>
            <TextField
              label="Insurer / Scheme Name"
              value={schemeName}
              onChange={(e) => setSchemeName(e.target.value)}
              required
            />
            <TextField
              label="Max Reimbursable Price (RWF)"
              type="number"
              value={maxPrice}
              onChange={(e) => setMaxPrice(e.target.value)}
            />
            <TextField
              label="Co-pay Percentage (%)"
              type="number"
              value={copay}
              onChange={(e) => setCopay(e.target.value)}
            />
            <label className="flex items-center gap-2 text-sm text-ink-900">
              <input
                type="checkbox"
                checked={priorAuth}
                onChange={(e) => setPriorAuth(e.target.checked)}
                className="rounded border-line"
              />
              Requires Prior Authorization
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
