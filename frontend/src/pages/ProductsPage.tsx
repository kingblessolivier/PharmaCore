import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Search, Trash2, Upload } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Badge, Button, ConfirmModal, PageHeader, SelectField, TextField } from "../components/ui";
import { DataGrid } from "../components/DataGrid";
import { ImageUpload } from "../components/ImageUpload";
import { api, ApiError, assetUrl } from "../lib/api";
import { useAuth } from "../lib/auth";
import { isAdmin } from "../lib/roles";
import type { Paginated, Product, TaxClass } from "../lib/types";
import { Drawer } from "../components/RecordKit";

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
  units_per_pack: number;
  route_of_administration: string;
  fda_registration_number: string;
  tax_class: TaxClass;
  storage_condition: string;
  requires_prescription: boolean;
  is_controlled_substance: boolean;
  controlled_schedule: string;
  reorder_level: number;
  reorder_quantity: number;
  rra_item_code: string;
  image_url: string;
  leaflet_url: string;
  min_temp_c: string;
  max_temp_c: string;
  ddd: string;
  is_essential: boolean;
  rxnorm_id: string;
  lifecycle_status: "ACTIVE" | "DISCONTINUED" | "OBSOLETE" | "PENDING_APPROVAL";
}

const ROUTES = [
  "",
  "ORAL",
  "IV",
  "IM",
  "SUBCUTANEOUS",
  "TOPICAL",
  "INHALATION",
  "OPHTHALMIC",
  "NASAL",
  "RECTAL",
  "OTHER",
];

// Minimal CSV parse: first row = headers, rest = values. Handles quoted fields.
function parseCsv(text: string): Record<string, string>[] {
  const rows: string[][] = [];
  let field = "";
  let row: string[] = [];
  let inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQuotes) {
      if (c === '"' && text[i + 1] === '"') {
        field += '"';
        i++;
      } else if (c === '"') inQuotes = false;
      else field += c;
    } else if (c === '"') inQuotes = true;
    else if (c === ",") {
      row.push(field);
      field = "";
    } else if (c === "\n" || c === "\r") {
      if (field !== "" || row.length) {
        row.push(field);
        rows.push(row);
        row = [];
        field = "";
      }
      if (c === "\r" && text[i + 1] === "\n") i++;
    } else field += c;
  }
  if (field !== "" || row.length) {
    row.push(field);
    rows.push(row);
  }
  if (rows.length < 2) return [];
  const headers = rows[0].map((h) => h.trim());
  return rows.slice(1).map((r) => {
    const o: Record<string, string> = {};
    headers.forEach((h, idx) => (o[h] = (r[idx] ?? "").trim()));
    return o;
  });
}

interface ImportResult {
  created: number;
  updated: number;
  errors: { row: number; error: string }[];
}

function ImportModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [text, setText] = useState("");
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const rows = parseCsv(text);

  const mutation = useMutation({
    mutationFn: () =>
      api<ImportResult>("/api/catalog/products/import/", {
        method: "POST",
        body: JSON.stringify({ rows }),
      }),
    onSuccess: (r) => {
      setResult(r);
      void qc.invalidateQueries({ queryKey: ["products"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Import failed."),
  });

  return (
    <Drawer title="Import medicines from CSV" onClose={onClose}>
      <div className="flex flex-col gap-3">
        <p className="text-xs text-ink-500">
          First row = column headers. Recognised columns: <code>generic_name</code> (required),
          brand_name, strength, dosage_form, pack_size, units_per_pack, gtin, atc_code, tax_class,
          requires_prescription, is_controlled_substance, storage_condition,
          fda_registration_number, reorder_level. Existing products (matched by GTIN or
          name+strength) are updated.
        </p>
        <input
          type="file"
          accept=".csv,text/csv"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void f.text().then(setText);
          }}
          className="text-sm"
        />
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={8}
          placeholder="generic_name,strength,dosage_form,tax_class,requires_prescription&#10;Paracetamol,500mg,TABLET,B,false"
          className="rounded-md border border-line bg-surface-0 px-3 py-2 font-mono text-xs outline-none focus:border-brand-600"
        />
        <div className="text-xs text-ink-500">{rows.length} row(s) parsed.</div>

        {result && (
          <div className="rounded-md bg-green-50 px-3 py-2 text-sm text-green-800">
            Imported: <b>{result.created}</b> created, <b>{result.updated}</b> updated
            {result.errors.length > 0 && (
              <div className="mt-1 text-red-700">
                {result.errors.length} row(s) skipped:
                <ul className="list-inside list-disc">
                  {result.errors.slice(0, 5).map((e, i) => (
                    <li key={i}>
                      Row {e.row}: {e.error}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
        {error && <p className="text-sm text-red-600">{error}</p>}

        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            {result ? "Done" : "Cancel"}
          </Button>
          <Button
            onClick={() => mutation.mutate()}
            disabled={rows.length === 0 || mutation.isPending}
          >
            {mutation.isPending ? "Importing…" : `Import ${rows.length} row(s)`}
          </Button>
        </div>
      </div>
    </Drawer>
  );
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
    units_per_pack: product?.units_per_pack ?? 1,
    route_of_administration: product?.route_of_administration ?? "",
    fda_registration_number: product?.fda_registration_number ?? "",
    tax_class: product?.tax_class ?? "B",
    storage_condition: product?.storage_condition ?? "AMBIENT",
    requires_prescription: product?.requires_prescription ?? false,
    is_controlled_substance: product?.is_controlled_substance ?? false,
    controlled_schedule: product?.controlled_schedule ?? "",
    reorder_level: product?.reorder_level ?? 0,
    reorder_quantity: product?.reorder_quantity ?? 0,
    rra_item_code: product?.rra_item_code ?? "",
    image_url: product?.image_url ?? "",
    leaflet_url: product?.leaflet_url ?? "",
    min_temp_c: product?.min_temp_c ?? "",
    max_temp_c: product?.max_temp_c ?? "",
    ddd: product?.ddd ?? "",
    is_essential: product?.is_essential ?? false,
    rxnorm_id: product?.rxnorm_id ?? "",
    lifecycle_status: product?.lifecycle_status ?? "ACTIVE",
  });
  const [error, setError] = useState<string | null>(null);

  const set = <K extends keyof ProductForm>(k: K, v: ProductForm[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  const mutation = useMutation({
    mutationFn: () => {
      // Empty temps → null (the field is nullable); everything else passes through.
      const payload = {
        ...form,
        min_temp_c: form.min_temp_c === "" ? null : form.min_temp_c,
        max_temp_c: form.max_temp_c === "" ? null : form.max_temp_c,
      };
      return api<Product>(
        editing ? `/api/catalog/products/${product!.id}/` : "/api/catalog/products/",
        {
          method: editing ? "PATCH" : "POST",
          body: JSON.stringify(payload),
        },
      );
    },
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
    <Drawer title={editing ? "Edit medicine" : "New medicine"} onClose={onClose}>
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
        <div className="grid grid-cols-2 gap-3">
          <TextField
            label="WHO Defined Daily Dose (DDD)"
            value={form.ddd}
            onChange={(e) => set("ddd", e.target.value)}
            placeholder="e.g. 500mg/day"
          />
          <TextField
            label="RxNorm ID"
            value={form.rxnorm_id}
            onChange={(e) => set("rxnorm_id", e.target.value)}
            placeholder="e.g. 308182"
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <SelectField
            label="Lifecycle Status"
            value={form.lifecycle_status}
            onChange={(e) =>
              set(
                "lifecycle_status",
                e.target.value as "ACTIVE" | "DISCONTINUED" | "OBSOLETE" | "PENDING_APPROVAL",
              )
            }
          >
            <option value="ACTIVE">Active</option>
            <option value="DISCONTINUED">Discontinued</option>
            <option value="OBSOLETE">Obsolete</option>
            <option value="PENDING_APPROVAL">Pending Approval</option>
          </SelectField>
          <label className="flex items-center gap-2 pt-6 text-sm text-ink-700">
            <input
              type="checkbox"
              checked={form.is_essential}
              onChange={(e) => set("is_essential", e.target.checked)}
            />
            WHO Essential Medicine (EML)
          </label>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <SelectField
            label="Route of administration"
            value={form.route_of_administration}
            onChange={(e) => set("route_of_administration", e.target.value)}
          >
            {ROUTES.map((r) => (
              <option key={r} value={r}>
                {r || "—"}
              </option>
            ))}
          </SelectField>
          <TextField
            label="Units per pack"
            type="number"
            value={String(form.units_per_pack)}
            onChange={(e) => set("units_per_pack", Number(e.target.value))}
          />
        </div>
        <TextField
          label="Rwanda FDA registration no."
          value={form.fda_registration_number}
          onChange={(e) => set("fda_registration_number", e.target.value)}
        />
        <div className="grid grid-cols-2 gap-3">
          <TextField
            label="Reorder level"
            type="number"
            value={String(form.reorder_level)}
            onChange={(e) => set("reorder_level", Number(e.target.value))}
          />
          <TextField
            label="Reorder quantity"
            type="number"
            value={String(form.reorder_quantity)}
            onChange={(e) => set("reorder_quantity", Number(e.target.value))}
          />
        </div>
        <div className="grid grid-cols-2 items-center gap-3">
          <label className="flex items-center gap-2 py-2 text-sm text-ink-700">
            <input
              type="checkbox"
              checked={form.requires_prescription}
              onChange={(e) => set("requires_prescription", e.target.checked)}
            />
            Prescription required
          </label>
          <label className="flex items-center gap-2 py-2 text-sm text-ink-700">
            <input
              type="checkbox"
              checked={form.is_controlled_substance}
              onChange={(e) => set("is_controlled_substance", e.target.checked)}
            />
            Controlled substance
          </label>
        </div>

        {form.is_controlled_substance && (
          <TextField
            label="Controlled schedule"
            value={form.controlled_schedule}
            onChange={(e) => set("controlled_schedule", e.target.value)}
            placeholder="e.g. Schedule 2"
          />
        )}
        <div className="grid grid-cols-2 gap-3">
          <TextField
            label="Pack size"
            value={form.pack_size}
            onChange={(e) => set("pack_size", e.target.value)}
            placeholder="e.g. 10×10 tablets"
          />
          <TextField
            label="RRA (EBM) item code"
            value={form.rra_item_code}
            onChange={(e) => set("rra_item_code", e.target.value)}
          />
        </div>
        {form.storage_condition !== "AMBIENT" && (
          <div className="grid grid-cols-2 gap-3">
            <TextField
              label="Min temp (°C)"
              type="number"
              value={form.min_temp_c}
              onChange={(e) => set("min_temp_c", e.target.value)}
              placeholder="e.g. 2"
            />
            <TextField
              label="Max temp (°C)"
              type="number"
              value={form.max_temp_c}
              onChange={(e) => set("max_temp_c", e.target.value)}
              placeholder="e.g. 8"
            />
          </div>
        )}
        {/* A photograph is how a counter assistant confirms the box in their
            hand is the product on the screen, so it needs to be easy enough to
            add that somebody actually does it. */}
        <ImageUpload
          value={form.image_url}
          onChange={(url) => set("image_url", url)}
          purpose="product"
          label="Product photograph"
          hint="Shown at the counter and on the B2B storefront."
        />
        <TextField
          label="Patient leaflet URL"
          value={form.leaflet_url}
          onChange={(e) => set("leaflet_url", e.target.value)}
          placeholder="https://…"
        />
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
    </Drawer>
  );
}

export function ProductsPage() {
  const { user } = useAuth();
  const admin = isAdmin(user);
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const [importing, setImporting] = useState(false);
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
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => setImporting(true)}>
                <Upload className="h-4 w-4" /> Import CSV
              </Button>
              <Button onClick={() => setCreating(true)}>
                <Plus className="h-4 w-4" /> New medicine
              </Button>
            </div>
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

      <DataGrid<Product>
        rows={data?.results ?? []}
        loading={isLoading}
        getRowId={(p) => p.id}
        storageKey="products"
        exportName="products"
        searchPlaceholder="Filter loaded medicines…"
        emptyMessage={search ? "No medicines match your search." : "No medicines yet."}
        columns={[
          {
            key: "generic_name",
            header: "Medicine",
            value: (p) => `${p.generic_name} ${p.brand_name}`.trim(),
            render: (p) => (
              <div className="flex items-center gap-3">
                {p.image_url ? (
                  <img
                    src={assetUrl(p.image_url)}
                    alt=""
                    className="h-9 w-9 shrink-0 rounded-md border border-line object-contain"
                    onError={(e) => (e.currentTarget.style.visibility = "hidden")}
                  />
                ) : (
                  <div className="h-9 w-9 shrink-0 rounded-md border border-line bg-surface-100" />
                )}
                <div>
                  <Link
                    to={`/products/${p.id}`}
                    className="font-medium text-ink-900 hover:text-brand-700 hover:underline"
                  >
                    {p.generic_name}
                  </Link>
                  {p.brand_name && <div className="text-xs text-ink-500">{p.brand_name}</div>}
                </div>
              </div>
            ),
          },
          { key: "dosage_form", header: "Form", value: (p) => p.dosage_form },
          {
            key: "strength",
            header: "Strength",
            value: (p) => p.strength || "—",
            render: (p) => <span className="font-mono text-ink-700">{p.strength || "—"}</span>,
          },
          {
            key: "tax_class",
            header: "Tax",
            value: (p) => p.tax_class,
            render: (p) => <span className="font-mono">{p.tax_class}</span>,
          },
          {
            key: "requires_prescription",
            header: "Rx",
            value: (p) => (p.requires_prescription ? "Rx" : ""),
            render: (p) => (p.requires_prescription ? <Badge>Rx</Badge> : null),
          },
          {
            key: "is_controlled_substance",
            header: "Controlled",
            value: (p) => (p.is_controlled_substance ? p.controlled_schedule || "Yes" : ""),
            render: (p) =>
              p.is_controlled_substance ? (
                <Badge tone="danger">{p.controlled_schedule || "Controlled"}</Badge>
              ) : null,
          },
          {
            key: "manufacturer_name",
            header: "Manufacturer",
            value: (p) => p.manufacturer_name ?? "—",
          },
          {
            key: "storage_condition",
            header: "Storage",
            value: (p) => p.storage_condition,
            // Cold chain is the difference between stock and spoiled stock, so
            // it is named rather than left to the reader to infer.
            render: (p) =>
              p.storage_condition === "COLD_CHAIN" ? (
                <Badge tone="info">Cold chain</Badge>
              ) : p.storage_condition === "FROZEN" ? (
                <Badge tone="info">Frozen</Badge>
              ) : (
                <span className="text-ink-500">Ambient</span>
              ),
          },
          {
            key: "pack_size",
            header: "Pack",
            value: (p) => p.pack_size || "—",
          },
          {
            key: "reorder_level",
            header: "Reorder at",
            numeric: true,
            align: "right",
            value: (p) => p.reorder_level,
          },
          /* Everything below ships hidden. The product master carries 35 fields
             and a reader wants eight of them — but which eight depends on the
             job, so the rest are one click away in the column picker rather
             than unavailable. */
          {
            key: "route_of_administration",
            header: "Route",
            defaultHidden: true,
            value: (p) => p.route_of_administration,
          },
          { key: "atc_code", header: "ATC", defaultHidden: true, value: (p) => p.atc_code || "—" },
          {
            key: "gtin",
            header: "GTIN",
            defaultHidden: true,
            value: (p) => p.gtin || "—",
            render: (p) => <span className="font-mono text-xs">{p.gtin || "—"}</span>,
          },
          {
            key: "fda_registration_number",
            header: "FDA reg.",
            defaultHidden: true,
            value: (p) => p.fda_registration_number || "—",
          },
          {
            key: "unit_of_measure",
            header: "Unit",
            defaultHidden: true,
            value: (p) => p.unit_of_measure || "—",
          },
          {
            key: "units_per_pack",
            header: "Per pack",
            defaultHidden: true,
            numeric: true,
            align: "right",
            value: (p) => p.units_per_pack,
          },
          {
            key: "divisibility",
            header: "May be split",
            defaultHidden: true,
            value: (p) => ((p.divisibility ?? 1) > 1 ? `1/${p.divisibility}` : "whole only"),
          },
          {
            key: "is_essential",
            header: "Essential (WHO)",
            defaultHidden: true,
            value: (p) => (p.is_essential ? "Yes" : "No"),
          },
          {
            key: "reorder_quantity",
            header: "Reorder qty",
            defaultHidden: true,
            numeric: true,
            align: "right",
            value: (p) => p.reorder_quantity,
          },
          {
            key: "lifecycle_status",
            header: "Lifecycle",
            defaultHidden: true,
            value: (p) => p.lifecycle_status,
          },
          {
            key: "rra_item_code",
            header: "RRA code",
            defaultHidden: true,
            value: (p) => p.rra_item_code || "—",
          },
          ...(admin
            ? [
                {
                  key: "actions",
                  header: "Actions",
                  align: "right" as const,
                  fixed: true,
                  sortable: false,
                  render: (p: Product) => (
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
                  ),
                },
              ]
            : []),
        ]}
      />
      {isError && <p className="text-sm text-red-600">Failed to load products.</p>}

      {importing && <ImportModal onClose={() => setImporting(false)} />}
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
