import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Minus, Plus, Receipt, Search, ShieldAlert, ShoppingCart, Trash2, X } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Button, Modal, PageHeader, SelectField, Spinner, TextField } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import type {
  InventoryBatch,
  Organization,
  Paginated,
  PaymentMethod,
  PharmacyProduct,
  Sale,
} from "../lib/types";

interface CartLine {
  product: number;
  name: string;
  unit_price: number;
  tax_rate: number;
  quantity: number;
  in_stock: number;
  requires_prescription: boolean;
  is_controlled: boolean;
}

interface Dispensing {
  patient_name: string;
  patient_id_number: string;
  prescriber_name: string;
  prescriber_license: string;
  prescription_reference: string;
}

const PAYMENT_METHODS: { value: PaymentMethod; label: string }[] = [
  { value: "CASH", label: "Cash" },
  { value: "MOBILE_MONEY", label: "Mobile money" },
  { value: "CARD", label: "Card" },
];

const money = (n: number) => n.toLocaleString(undefined, { maximumFractionDigits: 0 });

function OrgPicker({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const orgs = useQuery({
    queryKey: ["organizations"],
    queryFn: () => api<Paginated<Organization>>("/api/organizations/"),
  });
  const retails = (orgs.data?.results ?? []).filter((o) => o.type === "RETAIL");
  return (
    <SelectField label="Selling pharmacy" value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">— select pharmacy —</option>
      {retails.map((o) => (
        <option key={o.id} value={o.id}>
          {o.name}
        </option>
      ))}
    </SelectField>
  );
}

export function PosPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [pickedOrg, setPickedOrg] = useState("");
  const orgId = user?.organization ?? (pickedOrg ? Number(pickedOrg) : null);

  const [search, setSearch] = useState("");
  const [cart, setCart] = useState<CartLine[]>([]);
  const [method, setMethod] = useState<PaymentMethod>("CASH");
  const [tendered, setTendered] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [lastSale, setLastSale] = useState<Sale | null>(null);

  const listings = useQuery({
    queryKey: ["pos-listings", orgId],
    enabled: Boolean(orgId),
    queryFn: () =>
      api<Paginated<PharmacyProduct>>(`/api/inventory/pharmacy-products/?organization=${orgId}`),
  });
  const batches = useQuery({
    queryKey: ["pos-batches", orgId],
    enabled: Boolean(orgId),
    queryFn: () => api<Paginated<InventoryBatch>>(`/api/inventory/batches/?organization=${orgId}`),
  });

  // Sellable on-hand per product: active AND not expired. Expired batches are
  // excluded so the counter can never ring up lapsed stock.
  const stockByProduct = useMemo(() => {
    const m = new Map<number, number>();
    for (const b of batches.data?.results ?? []) {
      if (b.status === "ACTIVE" && b.days_to_expiry >= 0)
        m.set(b.product, (m.get(b.product) ?? 0) + b.quantity_available);
    }
    return m;
  }, [batches.data]);

  const sellable = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (listings.data?.results ?? [])
      .filter((l) => l.is_active && l.retail_price !== null)
      .filter((l) => (q ? l.product_name.toLowerCase().includes(q) : true));
  }, [listings.data, search]);

  const total = cart.reduce((s, l) => s + l.unit_price * l.quantity, 0);
  const tenderedNum = Number(tendered) || 0;
  const change = Math.max(0, tenderedNum - total);

  function addToCart(l: PharmacyProduct) {
    const inStock = stockByProduct.get(l.product) ?? 0;
    setError(null);
    setCart((c) => {
      const found = c.find((x) => x.product === l.product);
      if (found) {
        if (found.quantity + 1 > inStock) {
          setError(`Only ${inStock} of ${l.product_name} in stock.`);
          return c;
        }
        return c.map((x) => (x.product === l.product ? { ...x, quantity: x.quantity + 1 } : x));
      }
      if (inStock < 1) {
        setError(`${l.product_name} is out of stock.`);
        return c;
      }
      return [
        ...c,
        {
          product: l.product,
          name: l.product_name,
          unit_price: Number(l.retail_price),
          tax_rate: 0,
          quantity: 1,
          in_stock: inStock,
          requires_prescription: l.requires_prescription,
          is_controlled: l.is_controlled,
        },
      ];
    });
  }

  function setQty(product: number, delta: number) {
    setCart((c) =>
      c
        .map((x) => {
          if (x.product !== product) return x;
          const q = Math.min(Math.max(0, x.quantity + delta), x.in_stock);
          return { ...x, quantity: q };
        })
        .filter((x) => x.quantity > 0),
    );
  }

  // A sale with any prescription-only or controlled item must be dispensed by a
  // pharmacist and carry patient + prescriber details.
  const needsRx = cart.some((l) => l.requires_prescription || l.is_controlled);
  const isPharmacist =
    !!user &&
    (user.is_superuser || user.roles.includes("PHARMACIST") || user.roles.includes("SYS_ADMIN"));
  const [dispensingOpen, setDispensingOpen] = useState(false);

  const complete = useMutation({
    mutationFn: (dispensing?: Dispensing) =>
      api<Sale>("/api/retail/sales/", {
        method: "POST",
        body: JSON.stringify({
          organization: orgId,
          items: cart.map((l) => ({ product: l.product, quantity: l.quantity })),
          payments: [{ method, amount: String(tenderedNum) }],
          ...(dispensing ? { dispensing } : {}),
        }),
      }),
    onSuccess: (sale) => {
      setLastSale(sale);
      setCart([]);
      setTendered("");
      setError(null);
      setDispensingOpen(false);
      void qc.invalidateQueries({ queryKey: ["pos-batches", orgId] });
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Could not complete the sale."),
  });

  function submit() {
    setError(null);
    if (cart.length === 0) return setError("Add at least one item.");
    if (method === "CASH" && tenderedNum < total)
      return setError("Cash tendered does not cover the total.");
    if (needsRx) {
      if (!isPharmacist)
        return setError("This sale has prescription/controlled items — a pharmacist must complete it.");
      setDispensingOpen(true); // capture prescription details before charging
      return;
    }
    complete.mutate(undefined);
  }

  // For non-cash the exact amount is charged; keep the field in sync for clarity.
  const effectiveTendered = method === "CASH" ? tendered : String(total);

  if (!orgId) {
    return (
      <div>
        <PageHeader title="Point of sale" />
        <div className="max-w-sm rounded-lg border border-line bg-surface-0 p-5">
          <p className="mb-3 text-sm text-ink-600">
            Choose the pharmacy you're selling for to open the till.
          </p>
          <OrgPicker value={pickedOrg} onChange={setPickedOrg} />
        </div>
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="Point of sale" />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_380px]">
        {/* Catalog */}
        <div>
          <div className="mb-3 flex items-center gap-2 rounded-md border border-line bg-surface-0 px-3 py-2">
            <Search className="h-4 w-4 text-ink-500" />
            <input
              className="w-full bg-transparent text-sm outline-none"
              placeholder="Search this pharmacy's products…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              autoFocus
            />
          </div>
          {(listings.isLoading || batches.isLoading) && (
            <div className="flex justify-center py-10">
              <Spinner />
            </div>
          )}
          {listings.data && (
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {sellable.map((l) => {
                const inStock = stockByProduct.get(l.product) ?? 0;
                const out = inStock < 1;
                return (
                  <button
                    key={l.id}
                    onClick={() => addToCart(l)}
                    disabled={out}
                    className="flex flex-col items-start rounded-lg border border-line bg-surface-0 p-3 text-left transition-colors hover:border-brand-600 hover:bg-brand-50/40 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {l.product_image ? (
                      <img
                        src={l.product_image}
                        alt=""
                        className="mb-2 h-16 w-full rounded-md border border-line object-contain"
                        onError={(e) => (e.currentTarget.style.display = "none")}
                      />
                    ) : null}
                    <span className="line-clamp-2 text-sm font-medium text-ink-900">
                      {l.product_name}
                    </span>
                    {l.requires_prescription && (
                      <span className="mt-0.5 rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700">
                        Rx
                      </span>
                    )}
                    <span className="mt-1 font-mono text-sm text-brand-700">
                      {money(Number(l.retail_price))} RWF
                    </span>
                    <span
                      className={`mt-0.5 text-xs ${out ? "text-red-600" : "text-ink-500"}`}
                    >
                      {out ? "Out of stock" : `${inStock} in stock`}
                    </span>
                  </button>
                );
              })}
              {sellable.length === 0 && (
                <p className="col-span-full py-8 text-center text-sm text-ink-500">
                  {search ? "No products match." : "This pharmacy has no priced products yet."}
                </p>
              )}
            </div>
          )}
        </div>

        {/* Cart / payment */}
        <div className="lg:sticky lg:top-20 lg:self-start">
          <div className="flex flex-col rounded-lg border border-line bg-surface-0">
            <div className="flex items-center gap-2 border-b border-line px-4 py-3">
              <ShoppingCart className="h-4 w-4 text-ink-500" />
              <span className="text-sm font-semibold">Current sale</span>
              {cart.length > 0 && (
                <button
                  onClick={() => setCart([])}
                  className="ml-auto text-xs text-ink-500 hover:text-red-600"
                >
                  Clear
                </button>
              )}
            </div>

            <div className="max-h-[40vh] overflow-y-auto">
              {cart.length === 0 && (
                <p className="px-4 py-8 text-center text-sm text-ink-500">
                  Tap a product to start a sale.
                </p>
              )}
              {cart.map((l) => (
                <div
                  key={l.product}
                  className="flex items-center gap-2 border-b border-line px-4 py-2 last:border-0"
                >
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium text-ink-900">{l.name}</div>
                    <div className="font-mono text-xs text-ink-500">
                      {money(l.unit_price)} × {l.quantity} = {money(l.unit_price * l.quantity)}
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => setQty(l.product, -1)}
                      className="rounded-md border border-line p-1 text-ink-600 hover:bg-surface-100"
                      aria-label="Decrease"
                    >
                      <Minus className="h-3.5 w-3.5" />
                    </button>
                    <span className="w-6 text-center text-sm tabular-nums">{l.quantity}</span>
                    <button
                      onClick={() => setQty(l.product, 1)}
                      disabled={l.quantity >= l.in_stock}
                      className="rounded-md border border-line p-1 text-ink-600 hover:bg-surface-100 disabled:opacity-40"
                      aria-label="Increase"
                    >
                      <Plus className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => setCart((c) => c.filter((x) => x.product !== l.product))}
                      className="ml-1 rounded-md p-1 text-ink-500 hover:bg-red-50 hover:text-red-600"
                      aria-label="Remove"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>

            <div className="border-t border-line p-4">
              <div className="mb-3 flex items-baseline justify-between">
                <span className="text-sm text-ink-600">Total</span>
                <span className="font-mono text-xl font-semibold text-ink-900">
                  {money(total)} <span className="text-sm font-normal text-ink-500">RWF</span>
                </span>
              </div>
              <p className="mb-3 -mt-2 text-xs text-ink-500">VAT is included and itemised on the receipt.</p>

              <div className="grid grid-cols-2 gap-2">
                <SelectField
                  label="Payment"
                  value={method}
                  onChange={(e) => setMethod(e.target.value as PaymentMethod)}
                >
                  {PAYMENT_METHODS.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                </SelectField>
                <label className="flex flex-col gap-1.5">
                  <span className="text-xs font-medium uppercase tracking-wide text-ink-500">
                    {method === "CASH" ? "Cash tendered" : "Amount"}
                  </span>
                  <input
                    type="number"
                    value={effectiveTendered}
                    onChange={(e) => setTendered(e.target.value)}
                    disabled={method !== "CASH"}
                    placeholder={String(total)}
                    className="rounded-md border border-line bg-surface-0 px-3 py-2 text-sm outline-none focus:border-brand-600 disabled:opacity-60"
                  />
                </label>
              </div>

              {method === "CASH" && tenderedNum > 0 && (
                <div className="mt-2 flex justify-between text-sm">
                  <span className="text-ink-600">Change</span>
                  <span className="font-mono font-semibold text-ink-900">{money(change)} RWF</span>
                </div>
              )}

              {needsRx && (
                <div
                  className={`mt-3 flex items-start gap-2 rounded-md px-3 py-2 text-xs ${
                    isPharmacist ? "bg-amber-50 text-amber-800" : "bg-red-50 text-red-700"
                  }`}
                >
                  <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
                  {isPharmacist
                    ? "This sale has prescription/controlled items — you'll record the patient & prescriber before charging."
                    : "This sale has prescription/controlled items — a pharmacist must complete it."}
                </div>
              )}

              {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

              <Button
                className="mt-3 w-full"
                onClick={submit}
                disabled={complete.isPending || cart.length === 0 || (needsRx && !isPharmacist)}
              >
                {complete.isPending
                  ? "Completing…"
                  : needsRx
                    ? `Dispense & charge ${money(total)} RWF`
                    : `Charge ${money(total)} RWF`}
              </Button>
            </div>
          </div>
        </div>
      </div>

      {dispensingOpen && (
        <DispensingModal
          pending={complete.isPending}
          error={error}
          onSubmit={(d) => complete.mutate(d)}
          onClose={() => setDispensingOpen(false)}
        />
      )}
      {lastSale && <SaleReceiptModal sale={lastSale} onClose={() => setLastSale(null)} />}
    </div>
  );
}

function DispensingModal({
  pending,
  error,
  onSubmit,
  onClose,
}: {
  pending: boolean;
  error: string | null;
  onSubmit: (d: Dispensing) => void;
  onClose: () => void;
}) {
  const [d, setD] = useState<Dispensing>({
    patient_name: "",
    patient_id_number: "",
    prescriber_name: "",
    prescriber_license: "",
    prescription_reference: "",
  });
  const set = <K extends keyof Dispensing>(k: K, v: string) => setD((p) => ({ ...p, [k]: v }));
  const ready = d.patient_name.trim() && d.prescriber_name.trim();

  return (
    <Modal title="Dispense prescription / controlled items" onClose={onClose}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (ready) onSubmit(d);
        }}
        className="flex flex-col gap-4"
      >
        <p className="text-sm text-ink-500">
          Recorded in the dispensing log with you as the dispensing pharmacist.
        </p>
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Patient name" value={d.patient_name} onChange={(e) => set("patient_name", e.target.value)} required autoFocus />
          <TextField label="Patient ID / passport" value={d.patient_id_number} onChange={(e) => set("patient_id_number", e.target.value)} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Prescribing doctor" value={d.prescriber_name} onChange={(e) => set("prescriber_name", e.target.value)} required />
          <TextField label="Doctor licence no." value={d.prescriber_license} onChange={(e) => set("prescriber_license", e.target.value)} />
        </div>
        <TextField label="Prescription reference" value={d.prescription_reference} onChange={(e) => set("prescription_reference", e.target.value)} />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={!ready || pending}>{pending ? "Dispensing…" : "Confirm & charge"}</Button>
        </div>
      </form>
    </Modal>
  );
}

function SaleReceiptModal({ sale, onClose }: { sale: Sale; onClose: () => void }) {
  const qc = useQueryClient();
  const [voiding, setVoiding] = useState(false);
  const [reason, setReason] = useState("");
  const [status, setStatus] = useState(sale.status);

  const voidSale = useMutation({
    mutationFn: () =>
      api<Sale>(`/api/retail/sales/${sale.id}/void/`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      }),
    onSuccess: (s) => {
      setStatus(s.status);
      setVoiding(false);
      void qc.invalidateQueries({ queryKey: ["pos-batches", sale.organization] });
    },
  });

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/30 p-4 sm:items-center">
      <div className="flex max-h-[calc(100dvh-2rem)] w-full max-w-sm flex-col overflow-hidden rounded-lg border border-line bg-surface-0 shadow-xl">
        <div className="flex shrink-0 items-center justify-between border-b border-line px-5 py-3">
          <div className="flex items-center gap-2">
            <Receipt className="h-4 w-4 text-brand-600" />
            <h2 className="text-base font-semibold">Sale complete</h2>
          </div>
          <button onClick={onClose} aria-label="Close" className="rounded-md px-2 text-ink-500 hover:bg-surface-100">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="overflow-y-auto p-5">
          <div className="mb-3 rounded-lg bg-brand-50/60 p-3 text-center">
            <div className="font-mono text-sm text-ink-600">{sale.sale_number}</div>
            <div className="mt-1 font-mono text-2xl font-semibold text-ink-900">
              {money(Number(sale.total))} RWF
            </div>
            {Number(sale.change_due) > 0 && (
              <div className="mt-1 text-sm text-ink-600">
                Change due: <b>{money(Number(sale.change_due))} RWF</b>
              </div>
            )}
          </div>
          <dl className="mb-4 space-y-1 text-sm">
            <div className="flex justify-between">
              <dt className="text-ink-500">Subtotal (excl. VAT)</dt>
              <dd className="font-mono">{money(Number(sale.subtotal))}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-ink-500">VAT</dt>
              <dd className="font-mono">{money(Number(sale.tax_total))}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-ink-500">Tendered</dt>
              <dd className="font-mono">{money(Number(sale.amount_tendered))}</dd>
            </div>
          </dl>

          {status === "VOIDED" ? (
            <p className="rounded-md bg-red-50 px-3 py-2 text-center text-sm font-medium text-red-700">
              This sale has been voided — stock returned.
            </p>
          ) : voiding ? (
            <div className="flex flex-col gap-2">
              <input
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Reason for voiding…"
                className="rounded-md border border-line bg-surface-0 px-3 py-2 text-sm outline-none focus:border-brand-600"
                autoFocus
              />
              <div className="flex gap-2">
                <Button variant="secondary" className="flex-1" onClick={() => setVoiding(false)}>
                  Cancel
                </Button>
                <button
                  onClick={() => voidSale.mutate()}
                  disabled={!reason.trim() || voidSale.isPending}
                  className="flex-1 rounded-md bg-red-600 px-3 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-40"
                >
                  {voidSale.isPending ? "Voiding…" : "Confirm void"}
                </button>
              </div>
            </div>
          ) : (
            <div className="flex gap-2">
              <Link
                to="/documents"
                className="flex flex-1 items-center justify-center gap-2 rounded-md border border-line bg-surface-0 px-3 py-2 text-sm font-semibold text-ink-900 hover:bg-surface-100"
              >
                <Receipt className="h-4 w-4" /> Receipt
              </Link>
              <Button variant="secondary" className="flex-1" onClick={() => setVoiding(true)}>
                Void sale
              </Button>
            </div>
          )}
          <Button className="mt-3 w-full" onClick={onClose}>
            New sale
          </Button>
        </div>
      </div>
    </div>
  );
}
