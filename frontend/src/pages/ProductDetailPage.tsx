import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Plus, ShieldAlert, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Badge, Button, Card, SelectField, Spinner, TextField } from "../components/ui";
import { api } from "../lib/api";
import type {
  ActiveIngredient,
  FormularyItem,
  Paginated,
  Product,
  ProductBarcode,
  ProductContraindication,
  ProductIngredient,
  ProductSubstitute,
  ProductUomConversion,
} from "../lib/types";
import { StatusChip } from "../components/Status";

function IngredientsSection({ productId }: { productId: number }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [amount, setAmount] = useState("");
  const items = useQuery({
    queryKey: ["product-ingredients", productId],
    queryFn: () =>
      api<Paginated<ProductIngredient>>(`/api/catalog/product-ingredients/?product=${productId}`),
  });
  const add = useMutation({
    mutationFn: async () => {
      const found = await api<Paginated<ActiveIngredient>>(
        `/api/catalog/ingredients/?search=${encodeURIComponent(name)}`,
      );
      const match = found.results.find((i) => i.name.toLowerCase() === name.toLowerCase());
      const ing =
        match ??
        (await api<ActiveIngredient>("/api/catalog/ingredients/", {
          method: "POST",
          body: JSON.stringify({ name }),
        }));
      return api<ProductIngredient>("/api/catalog/product-ingredients/", {
        method: "POST",
        body: JSON.stringify({ product: productId, ingredient: ing.id, amount }),
      });
    },
    onSuccess: () => {
      setName("");
      setAmount("");
      void qc.invalidateQueries({ queryKey: ["product-ingredients", productId] });
    },
  });
  const del = useMutation({
    mutationFn: (id: number) =>
      api<void>(`/api/catalog/product-ingredients/${id}/`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["product-ingredients", productId] }),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    if (name.trim()) add.mutate();
  }

  return (
    <Card className="p-5">
      <h2 className="mb-3 text-sm font-semibold text-ink-900">Active ingredients</h2>
      <ul className="mb-3 flex flex-col gap-1">
        {(items.data?.results ?? []).map((i) => (
          <li
            key={i.id}
            className="flex items-center justify-between rounded-md bg-surface-100 px-3 py-1.5 text-sm"
          >
            <span>
              {i.ingredient_name} {i.amount && <span className="text-ink-500">· {i.amount}</span>}
            </span>
            <button
              onClick={() => del.mutate(i.id)}
              className="text-ink-500 hover:text-red-600"
              aria-label="Remove"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </li>
        ))}
        {items.data?.results.length === 0 && <li className="text-sm text-ink-500">None yet.</li>}
      </ul>
      <form onSubmit={submit} className="flex items-end gap-2">
        <TextField
          label="Ingredient"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="flex-1"
        />
        <TextField
          label="Amount"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder="500mg"
        />
        <Button type="submit" disabled={add.isPending}>
          <Plus className="h-4 w-4" /> Add
        </Button>
      </form>
    </Card>
  );
}

function BarcodesSection({ productId }: { productId: number }) {
  const qc = useQueryClient();
  const [barcode, setBarcode] = useState("");
  const [level, setLevel] = useState("EACH");
  const items = useQuery({
    queryKey: ["product-barcodes", productId],
    queryFn: () =>
      api<Paginated<ProductBarcode>>(`/api/catalog/product-barcodes/?product=${productId}`),
  });
  const add = useMutation({
    mutationFn: () =>
      api<ProductBarcode>("/api/catalog/product-barcodes/", {
        method: "POST",
        body: JSON.stringify({ product: productId, barcode, packaging_level: level }),
      }),
    onSuccess: () => {
      setBarcode("");
      void qc.invalidateQueries({ queryKey: ["product-barcodes", productId] });
    },
  });
  const del = useMutation({
    mutationFn: (id: number) =>
      api<void>(`/api/catalog/product-barcodes/${id}/`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["product-barcodes", productId] }),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    if (barcode.trim()) add.mutate();
  }

  return (
    <Card className="p-5">
      <h2 className="mb-3 text-sm font-semibold text-ink-900">Barcodes</h2>
      <ul className="mb-3 flex flex-col gap-1">
        {(items.data?.results ?? []).map((b) => (
          <li
            key={b.id}
            className="flex items-center justify-between rounded-md bg-surface-100 px-3 py-1.5 text-sm"
          >
            <span className="font-mono">
              {b.barcode} <span className="text-ink-500">· {b.packaging_level}</span>
            </span>
            <button
              onClick={() => del.mutate(b.id)}
              className="text-ink-500 hover:text-red-600"
              aria-label="Remove"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </li>
        ))}
        {items.data?.results.length === 0 && <li className="text-sm text-ink-500">None yet.</li>}
      </ul>
      <form onSubmit={submit} className="flex items-end gap-2">
        <TextField
          label="Barcode"
          value={barcode}
          onChange={(e) => setBarcode(e.target.value)}
          className="flex-1"
        />
        <label className="flex flex-col gap-1.5">
          <span className="text-xs font-medium uppercase tracking-wide text-ink-500">Level</span>
          <select
            className="rounded-md border border-line bg-surface-0 px-3 py-2 text-sm"
            value={level}
            onChange={(e) => setLevel(e.target.value)}
          >
            <option value="EACH">Each</option>
            <option value="BOX">Box</option>
            <option value="CASE">Case</option>
          </select>
        </label>
        <Button type="submit" disabled={add.isPending}>
          <Plus className="h-4 w-4" /> Add
        </Button>
      </form>
    </Card>
  );
}

function ContraindicationsSection({ productId }: { productId: number }) {
  const qc = useQueryClient();
  const [condition, setCondition] = useState("");
  const [icd10, setIcd10] = useState("");
  const [severity, setSeverity] = useState<"PRECAUTION" | "WARNING" | "CONTRAINDICATED">("WARNING");
  const [message, setMessage] = useState("");

  const items = useQuery({
    queryKey: ["product-contraindications", productId],
    queryFn: () =>
      api<Paginated<ProductContraindication>>(
        `/api/catalog/product-contraindications/?product=${productId}`,
      ),
  });

  const add = useMutation({
    mutationFn: () =>
      api<ProductContraindication>("/api/catalog/product-contraindications/", {
        method: "POST",
        body: JSON.stringify({
          product: productId,
          condition,
          icd10_code: icd10,
          severity,
          message,
        }),
      }),
    onSuccess: () => {
      setCondition("");
      setIcd10("");
      setMessage("");
      void qc.invalidateQueries({ queryKey: ["product-contraindications", productId] });
    },
  });

  const del = useMutation({
    mutationFn: (id: number) =>
      api<void>(`/api/catalog/product-contraindications/${id}/`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["product-contraindications", productId] }),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    if (condition.trim()) add.mutate();
  }

  return (
    <Card className="p-5">
      <div className="mb-3 flex items-center gap-2">
        <ShieldAlert className="h-4 w-4 text-amber-600" />
        <h2 className="text-sm font-semibold text-ink-900">
          Contraindications & Clinical Cautions
        </h2>
      </div>
      <ul className="mb-3 flex flex-col gap-2">
        {(items.data?.results ?? []).map((c) => (
          <li
            key={c.id}
            className="flex items-start justify-between rounded-md bg-surface-100 p-2.5 text-sm"
          >
            <div>
              <div className="flex items-center gap-2">
                <span className="font-medium">{c.condition}</span>
                {c.icd10_code && (
                  <span className="font-mono text-xs text-ink-500">[{c.icd10_code}]</span>
                )}
                <Badge
                  tone={
                    c.severity === "CONTRAINDICATED"
                      ? "critical"
                      : c.severity === "WARNING"
                        ? "warning"
                        : "neutral"
                  }
                >
                  {c.severity}
                </Badge>
              </div>
              {c.message && <p className="mt-1 text-xs text-ink-700">{c.message}</p>}
            </div>
            <button
              onClick={() => del.mutate(c.id)}
              className="text-ink-500 hover:text-red-600"
              aria-label="Remove"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </li>
        ))}
        {items.data?.results.length === 0 && (
          <li className="text-sm text-ink-500">None added yet.</li>
        )}
      </ul>
      <form onSubmit={submit} className="flex flex-col gap-2">
        <div className="grid grid-cols-3 gap-2">
          <TextField
            label="Condition"
            value={condition}
            onChange={(e) => setCondition(e.target.value)}
            placeholder="e.g. Renal Impairment"
          />
          <TextField
            label="ICD-10 Code"
            value={icd10}
            onChange={(e) => setIcd10(e.target.value)}
            placeholder="e.g. N18.9"
          />
          <SelectField
            label="Severity"
            value={severity}
            onChange={(e) =>
              setSeverity(e.target.value as "PRECAUTION" | "WARNING" | "CONTRAINDICATED")
            }
          >
            <option value="PRECAUTION">Precaution</option>
            <option value="WARNING">Warning</option>
            <option value="CONTRAINDICATED">Contraindicated</option>
          </SelectField>
        </div>
        <div className="flex items-end gap-2">
          <TextField
            label="Caution Message"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            className="flex-1"
            placeholder="Dispensing advice or warning message"
          />
          <Button type="submit" disabled={add.isPending}>
            <Plus className="h-4 w-4" /> Add
          </Button>
        </div>
      </form>
    </Card>
  );
}

function UomConversionsSection({ productId }: { productId: number }) {
  const qc = useQueryClient();
  const [unitName, setUnitName] = useState("");
  const [factor, setFactor] = useState("10");
  const [price, setPrice] = useState("");

  const items = useQuery({
    queryKey: ["product-uom-conversions", productId],
    queryFn: () =>
      api<Paginated<ProductUomConversion>>(
        `/api/catalog/product-uom-conversions/?product=${productId}`,
      ),
  });

  const add = useMutation({
    mutationFn: () =>
      api<ProductUomConversion>("/api/catalog/product-uom-conversions/", {
        method: "POST",
        body: JSON.stringify({
          product: productId,
          unit_name: unitName,
          conversion_factor: Number(factor),
          price_per_unit: price || null,
        }),
      }),
    onSuccess: () => {
      setUnitName("");
      setPrice("");
      void qc.invalidateQueries({ queryKey: ["product-uom-conversions", productId] });
    },
  });

  const del = useMutation({
    mutationFn: (id: number) =>
      api<void>(`/api/catalog/product-uom-conversions/${id}/`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["product-uom-conversions", productId] }),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    if (unitName.trim()) add.mutate();
  }

  return (
    <Card className="p-5">
      <h2 className="mb-3 text-sm font-semibold text-ink-900">
        Units of Measure & Increment Pricing
      </h2>
      <ul className="mb-3 flex flex-col gap-1">
        {(items.data?.results ?? []).map((u) => (
          <li
            key={u.id}
            className="flex items-center justify-between rounded-md bg-surface-100 px-3 py-1.5 text-sm"
          >
            <span>
              <b className="font-medium">{u.unit_name}</b> ({u.conversion_factor} units per pack)
              {u.price_per_unit && (
                <span className="ml-2 font-mono text-ink-500">RWF {u.price_per_unit}</span>
              )}
            </span>
            <button
              onClick={() => del.mutate(u.id)}
              className="text-ink-500 hover:text-red-600"
              aria-label="Remove"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </li>
        ))}
        {items.data?.results.length === 0 && (
          <li className="text-sm text-ink-500">None added yet.</li>
        )}
      </ul>
      <form onSubmit={submit} className="flex items-end gap-2">
        <TextField
          label="Unit Name"
          value={unitName}
          onChange={(e) => setUnitName(e.target.value)}
          placeholder="e.g. Strip / Tablet"
          className="flex-1"
        />
        <TextField
          label="Factor"
          type="number"
          value={factor}
          onChange={(e) => setFactor(e.target.value)}
          className="w-24"
        />
        <TextField
          label="Price (RWF)"
          value={price}
          onChange={(e) => setPrice(e.target.value)}
          placeholder="Optional"
          className="w-32"
        />
        <Button type="submit" disabled={add.isPending}>
          <Plus className="h-4 w-4" /> Add
        </Button>
      </form>
    </Card>
  );
}

function FormulariesSection({ productId }: { productId: number }) {
  const qc = useQueryClient();
  const [scheme, setScheme] = useState("RSSB / RAMA");
  const [maxPrice, setMaxPrice] = useState("");
  const [copay, setCopay] = useState("15");

  const items = useQuery({
    queryKey: ["formulary-items", productId],
    queryFn: () =>
      api<Paginated<FormularyItem>>(`/api/catalog/formulary-items/?product=${productId}`),
  });

  const add = useMutation({
    mutationFn: () =>
      api<FormularyItem>("/api/catalog/formulary-items/", {
        method: "POST",
        body: JSON.stringify({
          product: productId,
          scheme_name: scheme,
          is_covered: true,
          max_reimbursable_price: maxPrice || null,
          copay_percentage: copay || null,
        }),
      }),
    onSuccess: () => {
      setMaxPrice("");
      void qc.invalidateQueries({ queryKey: ["formulary-items", productId] });
    },
  });

  const del = useMutation({
    mutationFn: (id: number) =>
      api<void>(`/api/catalog/formulary-items/${id}/`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["formulary-items", productId] }),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    if (scheme.trim()) add.mutate();
  }

  return (
    <Card className="p-5">
      <h2 className="mb-3 text-sm font-semibold text-ink-900">
        Insurer Formularies & Reimbursable Coverage
      </h2>
      <ul className="mb-3 flex flex-col gap-1">
        {(items.data?.results ?? []).map((f) => (
          <li
            key={f.id}
            className="flex items-center justify-between rounded-md bg-surface-100 px-3 py-1.5 text-sm"
          >
            <span>
              <b className="font-medium">{f.scheme_name}</b> ·{" "}
              {f.is_covered ? "Covered" : "Not Covered"}
              {f.copay_percentage && (
                <span className="ml-2 font-mono text-ink-500">Co-pay: {f.copay_percentage}%</span>
              )}
              {f.max_reimbursable_price && (
                <span className="ml-2 font-mono text-ink-500">
                  Max: RWF {f.max_reimbursable_price}
                </span>
              )}
            </span>
            <button
              onClick={() => del.mutate(f.id)}
              className="text-ink-500 hover:text-red-600"
              aria-label="Remove"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </li>
        ))}
        {items.data?.results.length === 0 && (
          <li className="text-sm text-ink-500">None added yet.</li>
        )}
      </ul>
      <form onSubmit={submit} className="flex items-end gap-2">
        <TextField
          label="Scheme Name"
          value={scheme}
          onChange={(e) => setScheme(e.target.value)}
          placeholder="e.g. RSSB / RAMA, CBHI, MMI"
          className="flex-1"
        />
        <TextField
          label="Co-pay %"
          value={copay}
          onChange={(e) => setCopay(e.target.value)}
          className="w-24"
        />
        <TextField
          label="Max Reimbursable (RWF)"
          value={maxPrice}
          onChange={(e) => setMaxPrice(e.target.value)}
          className="w-36"
        />
        <Button type="submit" disabled={add.isPending}>
          <Plus className="h-4 w-4" /> Add
        </Button>
      </form>
    </Card>
  );
}

function SubstitutesSection({ productId }: { productId: number }) {
  const qc = useQueryClient();
  const [subName, setSubName] = useState("");
  const [subType, setSubType] = useState<"GENERIC_EQUIVALENT" | "THERAPEUTIC_ALTERNATIVE">(
    "GENERIC_EQUIVALENT",
  );

  const items = useQuery({
    queryKey: ["product-substitutes", productId],
    queryFn: () =>
      api<Paginated<ProductSubstitute>>(`/api/catalog/product-substitutes/?product=${productId}`),
  });

  const add = useMutation({
    mutationFn: async () => {
      const found = await api<Paginated<Product>>(
        `/api/catalog/products/?search=${encodeURIComponent(subName)}`,
      );
      const match = found.results[0];
      if (!match) throw new Error("Substitute product not found.");
      return api<ProductSubstitute>("/api/catalog/product-substitutes/", {
        method: "POST",
        body: JSON.stringify({
          product: productId,
          substitute_product: match.id,
          substitute_type: subType,
        }),
      });
    },
    onSuccess: () => {
      setSubName("");
      void qc.invalidateQueries({ queryKey: ["product-substitutes", productId] });
    },
  });

  const del = useMutation({
    mutationFn: (id: number) =>
      api<void>(`/api/catalog/product-substitutes/${id}/`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["product-substitutes", productId] }),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    if (subName.trim()) add.mutate();
  }

  return (
    <Card className="p-5">
      <h2 className="mb-3 text-sm font-semibold text-ink-900">Generic & Therapeutic Substitutes</h2>
      <ul className="mb-3 flex flex-col gap-1">
        {(items.data?.results ?? []).map((s) => (
          <li
            key={s.id}
            className="flex items-center justify-between rounded-md bg-surface-100 px-3 py-1.5 text-sm"
          >
            <span>
              <b className="font-medium">{s.substitute_generic_name}</b> ({s.substitute_strength}) ·{" "}
              <Badge tone="neutral">{s.substitute_type}</Badge>
            </span>
            <button
              onClick={() => del.mutate(s.id)}
              className="text-ink-500 hover:text-red-600"
              aria-label="Remove"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </li>
        ))}
        {items.data?.results.length === 0 && (
          <li className="text-sm text-ink-500">None added yet.</li>
        )}
      </ul>
      <form onSubmit={submit} className="flex items-end gap-2">
        <TextField
          label="Substitute Product Name"
          value={subName}
          onChange={(e) => setSubName(e.target.value)}
          placeholder="Search medicine..."
          className="flex-1"
        />
        <SelectField
          label="Type"
          value={subType}
          onChange={(e) =>
            setSubType(e.target.value as "GENERIC_EQUIVALENT" | "THERAPEUTIC_ALTERNATIVE")
          }
        >
          <option value="GENERIC_EQUIVALENT">Generic Equivalent</option>
          <option value="THERAPEUTIC_ALTERNATIVE">Therapeutic Alternative</option>
        </SelectField>
        <Button type="submit" disabled={add.isPending}>
          <Plus className="h-4 w-4" /> Add
        </Button>
      </form>
    </Card>
  );
}

export function ProductDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data: product, isLoading } = useQuery({
    queryKey: ["product", Number(id)],
    queryFn: () => api<Product>(`/api/catalog/products/${id}/`),
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-10">
        <Spinner />
      </div>
    );
  }
  if (!product) return <p className="text-sm text-red-600">Product not found.</p>;

  return (
    <div>
      <button
        onClick={() => navigate("/products")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> Catalog
      </button>
      <div className="mb-5 flex items-center gap-3">
        <h1 className="text-xl font-semibold tracking-tight">{product.generic_name}</h1>
        {product.brand_name && <span className="text-ink-500">{product.brand_name}</span>}
        {product.requires_prescription && <Badge>Rx</Badge>}
        {product.is_essential && <Badge tone="success">WHO Essential</Badge>}
        <StatusChip status={product.lifecycle_status ?? "UNKNOWN"} />
      </div>
      <div className="mb-4 grid grid-cols-2 gap-3 rounded-lg border border-line bg-surface-0 p-4 text-sm sm:grid-cols-4">
        <div>
          <div className="text-xs uppercase text-ink-500">Form</div>
          {product.dosage_form}
        </div>
        <div>
          <div className="text-xs uppercase text-ink-500">Strength</div>
          {product.strength || "—"}
        </div>
        <div>
          <div className="text-xs uppercase text-ink-500">Tax class</div>
          {product.tax_class}
        </div>
        <div>
          <div className="text-xs uppercase text-ink-500">Defined Daily Dose</div>
          {product.ddd || "—"}
        </div>
      </div>
      <div className="flex flex-col gap-4">
        <IngredientsSection productId={product.id} />
        <BarcodesSection productId={product.id} />
        <ContraindicationsSection productId={product.id} />
        <UomConversionsSection productId={product.id} />
        <FormulariesSection productId={product.id} />
        <SubstitutesSection productId={product.id} />
      </div>
    </div>
  );
}
