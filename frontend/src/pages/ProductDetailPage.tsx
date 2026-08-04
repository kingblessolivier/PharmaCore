import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Badge, Button, Card, Spinner, TextField } from "../components/ui";
import { api } from "../lib/api";
import type { ActiveIngredient, Paginated, Product, ProductBarcode, ProductIngredient } from "../lib/types";

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
      // Find or create the ingredient, then link it to the product.
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
    mutationFn: (id: number) => api<void>(`/api/catalog/product-ingredients/${id}/`, { method: "DELETE" }),
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
          <li key={i.id} className="flex items-center justify-between rounded-md bg-surface-100 px-3 py-1.5 text-sm">
            <span>
              {i.ingredient_name} {i.amount && <span className="text-ink-500">· {i.amount}</span>}
            </span>
            <button onClick={() => del.mutate(i.id)} className="text-ink-500 hover:text-red-600" aria-label="Remove">
              <Trash2 className="h-4 w-4" />
            </button>
          </li>
        ))}
        {items.data?.results.length === 0 && <li className="text-sm text-ink-500">None yet.</li>}
      </ul>
      <form onSubmit={submit} className="flex items-end gap-2">
        <TextField label="Ingredient" value={name} onChange={(e) => setName(e.target.value)} className="flex-1" />
        <TextField label="Amount" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="500mg" />
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
    queryFn: () => api<Paginated<ProductBarcode>>(`/api/catalog/product-barcodes/?product=${productId}`),
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
    mutationFn: (id: number) => api<void>(`/api/catalog/product-barcodes/${id}/`, { method: "DELETE" }),
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
          <li key={b.id} className="flex items-center justify-between rounded-md bg-surface-100 px-3 py-1.5 text-sm">
            <span className="font-mono">
              {b.barcode} <span className="text-ink-500">· {b.packaging_level}</span>
            </span>
            <button onClick={() => del.mutate(b.id)} className="text-ink-500 hover:text-red-600" aria-label="Remove">
              <Trash2 className="h-4 w-4" />
            </button>
          </li>
        ))}
        {items.data?.results.length === 0 && <li className="text-sm text-ink-500">None yet.</li>}
      </ul>
      <form onSubmit={submit} className="flex items-end gap-2">
        <TextField label="Barcode" value={barcode} onChange={(e) => setBarcode(e.target.value)} className="flex-1" />
        <label className="flex flex-col gap-1.5">
          <span className="text-xs font-medium uppercase tracking-wide text-ink-500">Level</span>
          <select className="rounded-md border border-line bg-surface-0 px-3 py-2 text-sm" value={level} onChange={(e) => setLevel(e.target.value)}>
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
    <div className="max-w-3xl">
      <button onClick={() => navigate("/products")} className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900">
        <ArrowLeft className="h-4 w-4" /> Catalog
      </button>
      <div className="mb-5 flex items-center gap-3">
        <h1 className="text-xl font-semibold tracking-tight">{product.generic_name}</h1>
        {product.brand_name && <span className="text-ink-500">{product.brand_name}</span>}
        {product.requires_prescription && <Badge>Rx</Badge>}
      </div>
      <div className="mb-4 grid grid-cols-2 gap-3 rounded-lg border border-line bg-surface-0 p-4 text-sm sm:grid-cols-4">
        <div><div className="text-xs uppercase text-ink-500">Form</div>{product.dosage_form}</div>
        <div><div className="text-xs uppercase text-ink-500">Strength</div>{product.strength || "—"}</div>
        <div><div className="text-xs uppercase text-ink-500">Tax class</div>{product.tax_class}</div>
        <div><div className="text-xs uppercase text-ink-500">ATC</div>{product.atc_code || "—"}</div>
      </div>
      <div className="flex flex-col gap-4">
        <IngredientsSection productId={product.id} />
        <BarcodesSection productId={product.id} />
      </div>
    </div>
  );
}
