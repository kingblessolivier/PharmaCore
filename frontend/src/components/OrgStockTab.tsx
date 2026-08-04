import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PackagePlus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { api, ApiError } from "../lib/api";
import type { InventoryBatch, Paginated, Product } from "../lib/types";
import { Button, Modal, SelectField, Spinner, TextField } from "./ui";

function ExpiryCell({ date, days }: { date: string; days: number }) {
  const cls =
    days < 0 ? "text-red-700 font-medium" : days <= 90 ? "text-amber-700 font-medium" : "text-ink-700";
  const note = days < 0 ? " (expired)" : days <= 90 ? ` (${days}d)` : "";
  return (
    <span className={`font-mono text-xs ${cls}`}>
      {date}
      {note}
    </span>
  );
}

function IntakeModal({ organizationId, onClose }: { organizationId: number; onClose: () => void }) {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [productId, setProductId] = useState("");
  const [batchNumber, setBatchNumber] = useState("");
  const [expiry, setExpiry] = useState("");
  const [mfg, setMfg] = useState("");
  const [quantity, setQuantity] = useState("");
  const [cost, setCost] = useState("");
  const [location, setLocation] = useState("");
  const [error, setError] = useState<string | null>(null);

  const products = useQuery({
    queryKey: ["catalog-search", search],
    queryFn: () =>
      api<Paginated<Product>>(`/api/catalog/products/?search=${encodeURIComponent(search)}`),
  });

  const mutation = useMutation({
    mutationFn: () =>
      api<InventoryBatch>("/api/inventory/intake", {
        method: "POST",
        body: JSON.stringify({
          organization: organizationId,
          product: Number(productId),
          batch_number: batchNumber,
          expiry_date: expiry,
          manufacture_date: mfg || null,
          quantity: Number(quantity),
          wholesale_cost: cost || null,
          storage_location: location,
        }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["batches", organizationId] });
      onClose();
    },
    onError: (err) =>
      setError(err instanceof ApiError ? `Could not receive stock: ${err.message}` : "Failed."),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!productId) return setError("Pick a product.");
    mutation.mutate();
  }

  return (
    <Modal title="Receive stock (intake)" onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <TextField
          label="Search the medicine catalog"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="e.g. amoxicillin"
          autoFocus
        />
        <SelectField label="Product" value={productId} onChange={(e) => setProductId(e.target.value)}>
          <option value="">— select —</option>
          {(products.data?.results ?? []).map((p) => (
            <option key={p.id} value={p.id}>
              {p.generic_name} {p.strength} ({p.dosage_form})
            </option>
          ))}
        </SelectField>
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Batch / lot number" value={batchNumber} onChange={(e) => setBatchNumber(e.target.value)} required />
          <TextField label="Quantity" type="number" value={quantity} onChange={(e) => setQuantity(e.target.value)} required />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Expiry date" type="date" value={expiry} onChange={(e) => setExpiry(e.target.value)} required />
          <TextField label="Manufacture date" type="date" value={mfg} onChange={(e) => setMfg(e.target.value)} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Wholesale cost (RWF)" type="number" value={cost} onChange={(e) => setCost(e.target.value)} />
          <TextField label="Storage location" value={location} onChange={(e) => setLocation(e.target.value)} />
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? "Receiving…" : "Receive stock"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export function OrgStockTab({ organizationId }: { organizationId: number }) {
  const [intake, setIntake] = useState(false);
  const { data, isLoading, isError } = useQuery({
    queryKey: ["batches", organizationId],
    queryFn: () => api<Paginated<InventoryBatch>>(`/api/inventory/batches/?organization=${organizationId}`),
  });

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-ink-900">Stock on hand</h2>
          <p className="text-xs text-ink-500">Batch level, sorted first-expired-first-out (FEFO).</p>
        </div>
        <Button onClick={() => setIntake(true)}>
          <PackagePlus className="h-4 w-4" /> Receive stock
        </Button>
      </div>

      {isLoading && (
        <div className="flex justify-center py-8">
          <Spinner />
        </div>
      )}
      {isError && <p className="text-sm text-red-600">Failed to load stock.</p>}

      {data && (
        <div className="overflow-hidden rounded-lg border border-line bg-surface-0">
          <table className="w-full text-sm">
            <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-2.5">Medicine</th>
                <th className="px-4 py-2.5">Batch</th>
                <th className="px-4 py-2.5">Expiry</th>
                <th className="px-4 py-2.5 text-right">Qty</th>
                <th className="px-4 py-2.5 text-right">Cost</th>
                <th className="px-4 py-2.5">Location</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((b) => (
                <tr key={b.id} className="border-b border-line last:border-0 hover:bg-surface-100">
                  <td className="px-4 py-2.5 font-medium">{b.product_name}</td>
                  <td className="px-4 py-2.5 font-mono text-ink-700">{b.batch_number}</td>
                  <td className="px-4 py-2.5">
                    <ExpiryCell date={b.expiry_date} days={b.days_to_expiry} />
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono">{b.quantity_available}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-ink-700">{b.wholesale_cost ?? "—"}</td>
                  <td className="px-4 py-2.5 text-ink-700">{b.storage_location || "—"}</td>
                </tr>
              ))}
              {data.results.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-ink-500">
                    No stock yet. Receive an intake to add batches.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {intake && <IntakeModal organizationId={organizationId} onClose={() => setIntake(false)} />}
    </div>
  );
}
