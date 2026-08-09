/* -------------------------------------------------------------------------- */
/* A product's packaging chain.                                                */
/*                                                                             */
/* This screen used to edit ProductUomConversion — a table with the right       */
/* shape, zero rows, and no readers anywhere in the system. It now edits        */
/* ProductUnit, which pricing, the till, FEFO allocation and every stock        */
/* figure actually convert through.                                            */
/*                                                                             */
/* The rule the form enforces: every level states its size in BASE units, not   */
/* in the level below. A case of 24 boxes of 100 is 2400, not 24 — measuring    */
/* against the base is what keeps a conversion one multiplication instead of a  */
/* walk that compounds rounding at every hop.                                   */
/* -------------------------------------------------------------------------- */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Boxes, Info, Layers, Plus, Scissors, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Button, PageHeader, SelectField, TextField } from "../components/ui";
import { api } from "../lib/api";
import type { Paginated, Product, ProductUnit } from "../lib/types";
import { Drawer } from "../components/RecordKit";

const UNIT_CODES = [
  { value: "TABLET", label: "Tablet" },
  { value: "CAPSULE", label: "Capsule" },
  { value: "SACHET", label: "Sachet" },
  { value: "SUPPOSITORY", label: "Suppository" },
  { value: "BOTTLE", label: "Bottle" },
  { value: "TUBE", label: "Tube" },
  { value: "VIAL", label: "Vial" },
  { value: "AMPOULE", label: "Ampoule" },
  { value: "DEVICE", label: "Device" },
  { value: "BAG", label: "Bag" },
  { value: "STRIP", label: "Strip" },
  { value: "PACK", label: "Pack" },
  { value: "CASE", label: "Case" },
  { value: "CARTON", label: "Carton" },
  { value: "ML", label: "Millilitre" },
  { value: "G", label: "Gram" },
  { value: "UNIT", label: "Unit" },
];

const SPLITS = [
  { value: "1", label: "Whole units only" },
  { value: "2", label: "May be halved" },
  { value: "4", label: "May be quartered" },
];

export function UomPage() {
  const qc = useQueryClient();
  const [productId, setProductId] = useState(0);
  const [adding, setAdding] = useState(false);

  const products = useQuery({
    queryKey: ["all-products"],
    queryFn: () => api<Paginated<Product>>("/api/catalog/products/?page_size=500"),
  });
  const product = (products.data?.results ?? []).find((p) => p.id === productId);

  const units = useQuery({
    queryKey: ["product-units", productId],
    enabled: productId > 0,
    queryFn: () => api<Paginated<ProductUnit>>(`/api/catalog/product-units/?product=${productId}`),
  });
  const rows = [...(units.data?.results ?? [])].sort((a, b) => a.level - b.level);
  const hasBase = rows.some((u) => u.is_base);

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["product-units", productId] });
    void qc.invalidateQueries({ queryKey: ["all-products"] });
  };

  const remove = useMutation({
    mutationFn: (id: number) =>
      api<void>(`/api/catalog/product-units/${id}/`, { method: "DELETE" }),
    onSuccess: invalidate,
  });

  const setSplit = useMutation({
    mutationFn: (divisibility: number) =>
      api<Product>(`/api/catalog/products/${productId}/`, {
        method: "PATCH",
        body: JSON.stringify({ divisibility }),
      }),
    onSuccess: invalidate,
  });

  return (
    <div className="space-y-4">
      <PageHeader
        title="Pack sizes"
        action={
          <Button onClick={() => setAdding(true)} disabled={productId === 0}>
            <Plus className="h-4 w-4" /> Add a pack size
          </Button>
        }
      />

      <div className="max-w-md">
        <SelectField
          label="Medicine"
          value={String(productId)}
          onChange={(e) => setProductId(Number(e.target.value))}
        >
          <option value="0">Choose a medicine…</option>
          {(products.data?.results ?? []).map((p) => (
            <option key={p.id} value={p.id}>
              {`${p.generic_name} ${p.strength}`.trim()}
            </option>
          ))}
        </SelectField>
      </div>

      {productId === 0 && (
        <div className="rounded-lg border border-dashed border-line py-12 text-center text-sm text-ink-500">
          Choose a medicine to see how it is packed.
        </div>
      )}

      {productId > 0 && (
        <>
          {!hasBase && !units.isLoading && (
            <div className="flex items-start gap-2 rounded-lg border border-warning-200 bg-warning-50 px-4 py-3 text-sm text-warning-900">
              <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
              <span>
                No single unit recorded yet. Start with the smallest amount you can dispense — one
                tablet, one bottle, one vial — then add the boxes and cartons.
              </span>
            </div>
          )}

          <div className="overflow-x-auto rounded-lg border border-line bg-surface-0">
            <table className="w-full text-sm">
              <thead className="border-b border-line bg-surface-100 text-left text-xs uppercase tracking-wide text-ink-500">
                <tr>
                  <th className="px-4 py-2">#</th>
                  <th className="px-3 py-2">Pack size</th>
                  <th className="px-3 py-2">Printed on the box</th>
                  <th className="px-3 py-2 text-right">How many it contains</th>
                  <th className="px-3 py-2">Barcode</th>
                  <th className="px-3 py-2 text-right">Price</th>
                  <th className="px-3 py-2">Default for</th>
                  <th className="px-4 py-2" />
                </tr>
              </thead>
              <tbody>
                {rows.map((u) => (
                  <tr key={u.id} className="border-b border-line last:border-0">
                    <td className="px-4 py-2 tabular-nums text-ink-500">{u.level}</td>
                    <td className="px-3 py-2 font-medium text-ink-900">
                      <span className="flex items-center gap-1.5">
                        {u.is_base ? (
                          <Layers className="h-3.5 w-3.5 text-brand-600" aria-hidden />
                        ) : (
                          <Boxes className="h-3.5 w-3.5 text-ink-400" aria-hidden />
                        )}
                        {u.code_display}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-ink-600">{u.name || "—"}</td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {Number(u.factor_to_base).toLocaleString()}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-ink-500">{u.barcode || "—"}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-ink-600">
                      {u.price ? Number(u.price).toLocaleString() : "—"}
                    </td>
                    <td className="px-3 py-2 text-xs text-ink-500">
                      {[
                        u.is_base && "the single",
                        u.is_purchase_default && "ordering",
                        u.is_sale_default && "dispensing",
                      ]
                        .filter(Boolean)
                        .join(" · ") || "—"}
                    </td>
                    <td className="px-4 py-2 text-right">
                      <button
                        onClick={() => remove.mutate(u.id)}
                        className="text-ink-400 hover:text-danger-600"
                        aria-label={`Remove ${u.code_display}`}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
                {rows.length === 0 && !units.isLoading && (
                  <tr>
                    <td colSpan={8} className="px-4 py-8 text-center text-ink-500">
                      Nothing recorded yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Splitting is a clinical decision, so it belongs to the medicine
              rather than to a packaging level. A score line is not authority to
              split — an enteric or modified-release coating destroyed by
              halving doses the whole thing at once. */}
          <div className="max-w-xl rounded-lg border border-line bg-surface-0 p-4">
            <div className="mb-1 flex items-center gap-2 text-sm font-semibold text-ink-900">
              <Scissors className="h-4 w-4 text-ink-500" aria-hidden />
              May this be split?
            </div>
            <p className="mb-3 text-xs text-ink-500">
              Only a scored, immediate-release tablet may be halved. Enteric-coated and
              modified-release forms may not.
            </p>
            <SelectField
              label="Dispensing"
              value={String(product?.divisibility ?? 1)}
              onChange={(e) => setSplit.mutate(Number(e.target.value))}
            >
              {SPLITS.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </SelectField>
          </div>
        </>
      )}

      {adding && (
        <AddLevel
          productId={productId}
          hasBase={hasBase}
          nextLevel={rows.length ? Math.max(...rows.map((r) => r.level)) + 1 : 0}
          onClose={() => setAdding(false)}
          onSaved={() => {
            invalidate();
            setAdding(false);
          }}
        />
      )}
    </div>
  );
}

function AddLevel({
  productId,
  hasBase,
  nextLevel,
  onClose,
  onSaved,
}: {
  productId: number;
  hasBase: boolean;
  nextLevel: number;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [code, setCode] = useState(hasBase ? "PACK" : "TABLET");
  const [name, setName] = useState("");
  const [factor, setFactor] = useState(hasBase ? "100" : "1");
  const [barcode, setBarcode] = useState("");
  const [price, setPrice] = useState("");
  const [weight, setWeight] = useState("");
  const [volume, setVolume] = useState("");
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () =>
      api<ProductUnit>("/api/catalog/product-units/", {
        method: "POST",
        body: JSON.stringify({
          product: productId,
          code,
          name,
          factor_to_base: factor,
          level: hasBase ? nextLevel : 0,
          is_base: !hasBase,
          barcode,
          price: price || null,
          // Blank is "not measured", which is a null. A zero would claim the
          // carton weighs nothing, and a freight total built on that is worse
          // than no total at all.
          gross_weight_g: weight || null,
          volume_ml: volume || null,
        }),
      }),
    onSuccess: onSaved,
    onError: (e) => setError(e instanceof Error ? e.message : "Could not save that level."),
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    save.mutate();
  };

  return (
    <Drawer title={hasBase ? "Add a pack size" : "What is the single unit?"} onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        <p className="text-xs text-ink-500">
          {hasBase
            ? "How many singles are inside — a carton of 24 boxes of 100 tablets contains 2400 tablets, not 24 boxes."
            : "The smallest amount you can dispense: one tablet, one bottle, one vial."}
        </p>
        <SelectField label="Pack size" value={code} onChange={(e) => setCode(e.target.value)}>
          {UNIT_CODES.map((u) => (
            <option key={u.value} value={u.value}>
              {u.label}
            </option>
          ))}
        </SelectField>
        <TextField
          label="Printed on the box"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Box of 100 tablets"
        />
        <TextField
          label="How many singles it contains"
          value={factor}
          onChange={(e) => setFactor(e.target.value)}
          disabled={!hasBase}
        />
        <TextField
          label="Barcode on this pack size"
          value={barcode}
          onChange={(e) => setBarcode(e.target.value)}
        />
        <TextField
          label="Price for one (optional)"
          value={price}
          onChange={(e) => setPrice(e.target.value)}
          placeholder="Leave blank to scale from the base price"
        />
        {/* Recorded per level because a carton is not twenty times the volume
            of the box inside it — packaging and voids are most of the
            difference. Freight is billed on whichever of the two is larger. */}
        <div className="grid grid-cols-2 gap-3">
          <TextField
            label="Weight of one (g)"
            type="number"
            value={weight}
            onChange={(e) => setWeight(e.target.value)}
            placeholder="Packaging included"
          />
          <TextField
            label="Space it takes (mL)"
            type="number"
            value={volume}
            onChange={(e) => setVolume(e.target.value)}
            placeholder="1 litre = 1000"
          />
        </div>
        {error && <p className="text-sm text-danger-700">{error}</p>}
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={save.isPending}>
            Save
          </Button>
        </div>
      </form>
    </Drawer>
  );
}
