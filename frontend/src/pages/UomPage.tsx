import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Edit2, Layers, Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Badge, Button, PageHeader, SelectField, TextField } from "../components/ui";
import { api } from "../lib/api";
import type { Paginated, Product, ProductUomConversion } from "../lib/types";
import { DataGrid } from "../components/DataGrid";
import { Drawer } from "../components/RecordKit";

export function UomPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<ProductUomConversion | null>(null);

  const [productId, setProductId] = useState<number>(0);
  const [unitName, setUnitName] = useState("");
  const [conversionFactor, setConversionFactor] = useState("10");
  const [pricePerUnit, setPricePerUnit] = useState("");
  const [isDefault, setIsDefault] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["product-uom-conversions"],
    queryFn: () => api<Paginated<ProductUomConversion>>("/api/catalog/product-uom-conversions/"),
  });

  const productsQuery = useQuery({
    queryKey: ["all-products"],
    queryFn: () => api<Paginated<Product>>("/api/catalog/products/?page_size=100"),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api<ProductUomConversion>("/api/catalog/product-uom-conversions/", {
        method: "POST",
        body: JSON.stringify({
          product: productId,
          unit_name: unitName,
          conversion_factor: Number(conversionFactor),
          price_per_unit: pricePerUnit ? Number(pricePerUnit) : null,
          is_default_dispensing: isDefault,
        }),
      }),
    onSuccess: () => {
      setCreating(false);
      void qc.invalidateQueries({ queryKey: ["product-uom-conversions"] });
    },
  });

  const updateMutation = useMutation({
    mutationFn: () =>
      api<ProductUomConversion>(`/api/catalog/product-uom-conversions/${editing?.id}/`, {
        method: "PATCH",
        body: JSON.stringify({
          unit_name: unitName,
          conversion_factor: Number(conversionFactor),
          price_per_unit: pricePerUnit ? Number(pricePerUnit) : null,
          is_default_dispensing: isDefault,
        }),
      }),
    onSuccess: () => {
      setEditing(null);
      void qc.invalidateQueries({ queryKey: ["product-uom-conversions"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api<void>(`/api/catalog/product-uom-conversions/${id}/`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["product-uom-conversions"] }),
  });

  function startCreate() {
    setProductId(productsQuery.data?.results[0]?.id ?? 0);
    setUnitName("Strip");
    setConversionFactor("10");
    setPricePerUnit("");
    setIsDefault(false);
    setCreating(true);
  }

  function startEdit(u: ProductUomConversion) {
    setEditing(u);
    setUnitName(u.unit_name);
    setConversionFactor(String(u.conversion_factor));
    setPricePerUnit(u.price_per_unit ? String(u.price_per_unit) : "");
    setIsDefault(u.is_default_dispensing);
  }

  function submitCreate(e: FormEvent) {
    e.preventDefault();
    if (productId && unitName) createMutation.mutate();
  }

  function submitUpdate(e: FormEvent) {
    e.preventDefault();
    if (editing && unitName) updateMutation.mutate();
  }

  const filtered = (data?.results ?? []).filter(
    (u) =>
      u.unit_name.toLowerCase().includes(search.toLowerCase()) ||
      String(u.product).includes(search),
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
        title="Units of Measure & OTC Increment Pricing Directory"
        action={
          <Button onClick={startCreate}>
            <Plus className="h-4 w-4" /> Add UoM Conversion
          </Button>
        }
      />
      <p className="mb-4 text-sm text-ink-500 max-w-3xl">
        Full CRUD management for pack-to-strip and tablet conversions and OTC increment pricing.
      </p>

      <div className="mb-4 flex items-center gap-2 rounded-md border border-line bg-surface-0 px-3 py-2">
        <input
          className="w-full bg-transparent text-sm outline-none"
          placeholder="Filter by unit name (e.g. Strip, Tablet, Box)..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <DataGrid<ProductUomConversion>
        rows={filtered}
        loading={isLoading}
        getRowId={(r) => r.id}
        storageKey="uom-conversions"
        exportName="uom-conversions"
        searchPlaceholder="Search units…"
        emptyMessage="No unit conversions recorded."
        columns={[
          {
            key: "unit_name",
            header: "Unit",
            value: (u) => u.unit_name,
            render: (u) => (
              <span className="flex items-center gap-2 font-medium text-ink-900">
                <Layers className="h-4 w-4 text-brand-600" />
                {u.unit_name}
              </span>
            ),
          },
          {
            key: "conversion_factor",
            header: "Conversion",
            align: "right",
            numeric: true,
            value: (u) => Number(u.conversion_factor),
            render: (u) => (
              <span className="font-mono text-ink-700">{u.conversion_factor}x per pack</span>
            ),
          },
          {
            key: "price_per_unit",
            header: "Unit price",
            align: "right",
            numeric: true,
            value: (u) => Number(u.price_per_unit ?? 0),
            render: (u) => (
              <span className="font-mono text-ink-700">
                {u.price_per_unit ? `RWF ${u.price_per_unit}` : "—"}
              </span>
            ),
          },
          {
            key: "is_default_dispensing",
            header: "Default dispensing unit",
            value: (u) => (u.is_default_dispensing ? "Yes" : "No"),
            render: (u) =>
              u.is_default_dispensing ? (
                <Badge tone="success">Default</Badge>
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
            render: (u) => (
              <div className="flex items-center justify-end gap-1">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    startEdit(u);
                  }}
                  className="rounded-md p-1.5 text-ink-500 hover:bg-surface-200 hover:text-ink-900"
                  aria-label="Edit"
                >
                  <Edit2 className="h-4 w-4" />
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteMutation.mutate(u.id);
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
        <Drawer title="Add UoM Conversion" onClose={() => setCreating(false)}>
          <form onSubmit={submitCreate} className="flex flex-col gap-4">
            <SelectField
              label="Target Medicine"
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
              label="Unit Name"
              value={unitName}
              onChange={(e) => setUnitName(e.target.value)}
              placeholder="e.g. Strip, Tablet, Ampoule"
              required
            />
            <TextField
              label="Conversion Factor (Units per Pack)"
              type="number"
              value={conversionFactor}
              onChange={(e) => setConversionFactor(e.target.value)}
              required
            />
            <TextField
              label="Unit Price (RWF)"
              type="number"
              value={pricePerUnit}
              onChange={(e) => setPricePerUnit(e.target.value)}
              placeholder="e.g. 100"
            />
            <label className="flex items-center gap-2 text-sm text-ink-900">
              <input
                type="checkbox"
                checked={isDefault}
                onChange={(e) => setIsDefault(e.target.checked)}
                className="rounded border-line"
              />
              Default Dispensing Unit
            </label>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setCreating(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? "Adding…" : "Add Conversion"}
              </Button>
            </div>
          </form>
        </Drawer>
      )}

      {editing && (
        <Drawer title="Edit UoM Conversion" onClose={() => setEditing(null)}>
          <form onSubmit={submitUpdate} className="flex flex-col gap-4">
            <TextField
              label="Unit Name"
              value={unitName}
              onChange={(e) => setUnitName(e.target.value)}
              required
            />
            <TextField
              label="Conversion Factor (Units per Pack)"
              type="number"
              value={conversionFactor}
              onChange={(e) => setConversionFactor(e.target.value)}
              required
            />
            <TextField
              label="Unit Price (RWF)"
              type="number"
              value={pricePerUnit}
              onChange={(e) => setPricePerUnit(e.target.value)}
            />
            <label className="flex items-center gap-2 text-sm text-ink-900">
              <input
                type="checkbox"
                checked={isDefault}
                onChange={(e) => setIsDefault(e.target.checked)}
                className="rounded border-line"
              />
              Default Dispensing Unit
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
