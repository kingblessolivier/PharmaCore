import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Banknote,
  CloudOff,
  CreditCard,
  Minus,
  Plus,
  ScanLine,
  Smartphone,
  Trash2,
  TriangleAlert,
  WifiOff,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Drawer, ErrorNote, Field, Grid, Input, Section } from "../components/RecordKit";
import { Badge, Button } from "../components/ui";
import { api } from "../lib/api";
import { money } from "../lib/format";
import {
  enqueue,
  flush,
  newClientReference,
  queueSize,
  watchConnectivity,
  type QueuedSale,
} from "../lib/offlineQueue";
import { useDefaultOrg } from "../lib/recordData";
import type { ActivePromotion, ScanResult } from "../lib/retail";

interface Line {
  product: number;
  label: string;
  quantity: number;
  unit_price: string;
  tax_rate: string;
  requires_prescription: boolean;
  is_controlled: boolean;
  on_hand: number;
}

type Tender = "CASH" | "MOBILE_MONEY" | "CARD";

const TENDERS: { key: Tender; label: string; hotkey: string; icon: typeof Banknote }[] = [
  { key: "CASH", label: "Cash", hotkey: "F2", icon: Banknote },
  { key: "MOBILE_MONEY", label: "Mobile money", hotkey: "F3", icon: Smartphone },
  { key: "CARD", label: "Card", hotkey: "F4", icon: CreditCard },
];

/* -------------------------------------------------------------------------- */

/** The till's own arithmetic. Recomputed locally so the totals keep working
 *  with no connection — the server agrees, it does not decide. */
function totals(lines: Line[], discount: number) {
  const gross = lines.reduce((s, l) => s + Number(l.unit_price) * l.quantity, 0);
  const net = Math.max(gross - discount, 0);
  const tax = lines.reduce((s, l) => {
    const rate = Number(l.tax_rate);
    if (rate <= 0) return s;
    const lineTotal = Number(l.unit_price) * l.quantity;
    return s + (lineTotal * rate) / (100 + rate);
  }, 0);
  return { gross, net, tax };
}

/* -------------------------------------------------------------------------- */

function DispensingDrawer({
  onClose,
  onConfirm,
}: {
  onClose: () => void;
  onConfirm: (details: Record<string, string>) => void;
}) {
  const [form, setForm] = useState({
    patient_name: "",
    patient_id_number: "",
    prescriber_name: "",
    prescriber_license: "",
    prescription_reference: "",
  });
  const set = (patch: Partial<typeof form>) => setForm({ ...form, ...patch });

  return (
    <Drawer
      title="Dispensing details"
      subtitle="Required before a prescription-only or controlled item can leave the counter."
      width="max-w-2xl"
      onClose={onClose}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={() => onConfirm(form)}
            disabled={!form.patient_name.trim() || !form.prescriber_name.trim()}
          >
            Confirm &amp; take payment
          </Button>
        </div>
      }
    >
      <Section title="Patient">
        <Grid cols={2}>
          <Field label="Name">
            <Input
              autoFocus
              value={form.patient_name}
              onChange={(e) => set({ patient_name: e.target.value })}
            />
          </Field>
          <Field label="ID number">
            <Input
              value={form.patient_id_number}
              onChange={(e) => set({ patient_id_number: e.target.value })}
            />
          </Field>
        </Grid>
      </Section>
      <Section title="Prescriber">
        <Grid cols={2}>
          <Field label="Doctor">
            <Input
              value={form.prescriber_name}
              onChange={(e) => set({ prescriber_name: e.target.value })}
            />
          </Field>
          <Field label="Licence">
            <Input
              value={form.prescriber_license}
              onChange={(e) => set({ prescriber_license: e.target.value })}
            />
          </Field>
        </Grid>
        <Field label="Prescription reference">
          <Input
            value={form.prescription_reference}
            onChange={(e) => set({ prescription_reference: e.target.value })}
          />
        </Field>
      </Section>
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

export function PosPage() {
  const { orgId } = useDefaultOrg();
  const qc = useQueryClient();
  const scanRef = useRef<HTMLInputElement>(null);

  const [lines, setLines] = useState<Line[]>([]);
  const [code, setCode] = useState("");
  const [notice, setNotice] = useState<{ text: string; tone: "info" | "warn" } | null>(null);
  const [tenders, setTenders] = useState<Record<Tender, string>>({
    CASH: "",
    MOBILE_MONEY: "",
    CARD: "",
  });
  const [couponCode, setCouponCode] = useState("");
  const [discount, setDiscount] = useState(0);
  const [dispensingOpen, setDispensingOpen] = useState(false);
  const [online, setOnline] = useState(navigator.onLine);
  const [pending, setPending] = useState(0);

  const { gross, net, tax } = useMemo(() => totals(lines, discount), [lines, discount]);
  const tendered = useMemo(
    () => Object.values(tenders).reduce((s, v) => s + Number(v || 0), 0),
    [tenders],
  );
  const needsPharmacist = lines.some((l) => l.requires_prescription || l.is_controlled);

  /* The scan field is the till's home position. Anything that steals focus has
     to give it back, or the next scan lands in the wrong box. */
  const focusScan = useCallback(() => {
    window.setTimeout(() => scanRef.current?.focus(), 0);
  }, []);

  useEffect(focusScan, [focusScan]);

  const refreshQueue = useCallback(() => {
    void queueSize().then(setPending);
  }, []);
  useEffect(refreshQueue, [refreshQueue]);

  const drain = useCallback(async () => {
    const result = await flush((sale) =>
      api("/api/retail/offline/sync/", { method: "POST", body: JSON.stringify(sale) }),
    );
    setPending(result.remaining);
    if (result.synced > 0) {
      setNotice({ text: `${result.synced} queued sale(s) synced.`, tone: "info" });
      void qc.invalidateQueries({ queryKey: ["sales"] });
    }
    return result;
  }, [qc]);

  useEffect(() => {
    const stop = watchConnectivity((up) => {
      setOnline(up);
      if (up) void drain();
    });
    // `online` fires when the interface comes up, not when the server is
    // reachable, so the queue is also retried on a timer.
    const timer = window.setInterval(() => {
      if (navigator.onLine) void drain();
    }, 30_000);
    return () => {
      stop();
      window.clearInterval(timer);
    };
  }, [drain]);

  const { data: promotions = [] } = useQuery({
    queryKey: ["active-promotions"],
    enabled: online,
    queryFn: () => api<ActivePromotion[]>("/api/retail/counter/promotions/"),
  });

  /* ---------------------------------------------------------------- scanning */

  const addLine = useCallback((hit: Extract<ScanResult, { found: true }>) => {
    setLines((current) => {
      const existing = current.findIndex((l) => l.product === hit.product);
      if (existing >= 0) {
        const copy = [...current];
        copy[existing] = { ...copy[existing], quantity: copy[existing].quantity + hit.units };
        return copy;
      }
      return [
        ...current,
        {
          product: hit.product,
          label: hit.label,
          // A carton barcode adds the carton, not one tablet.
          quantity: hit.units,
          unit_price: hit.unit_price || "0",
          tax_rate: "18",
          requires_prescription: hit.requires_prescription,
          is_controlled: hit.is_controlled,
          on_hand: hit.on_hand,
        },
      ];
    });
  }, []);

  const scan = useMutation({
    mutationFn: (value: string) =>
      api<ScanResult>(
        `/api/retail/counter/scan/?organization=${orgId}&code=${encodeURIComponent(value)}`,
      ),
    onSuccess: (result) => {
      if (result.found) {
        addLine(result);
        setNotice(
          result.on_hand <= 0
            ? { text: `${result.label} shows no stock on hand.`, tone: "warn" }
            : null,
        );
      }
      setCode("");
      focusScan();
    },
    onError: () => {
      setNotice({ text: `Nothing matches ${code}.`, tone: "warn" });
      setCode("");
      focusScan();
    },
  });

  /* -------------------------------------------------------------- promotions */

  const applyCoupon = useMutation({
    mutationFn: (value: string) =>
      api<{ applied: boolean; reason: string; discount: string }>(
        "/api/retail/counter/apply-promotion/",
        { method: "POST", body: JSON.stringify({ code: value, organization: orgId }) },
      ),
    onSuccess: (result) => {
      setDiscount(result.applied ? Number(result.discount) : 0);
      setNotice({ text: result.reason, tone: result.applied ? "info" : "warn" });
      focusScan();
    },
  });

  /* ---------------------------------------------------------------- checkout */

  const setTender = (key: Tender, value: string) =>
    setTenders((current) => ({ ...current, [key]: value }));

  const payExactly = (key: Tender) => {
    const outstanding = Math.max(net - tendered, 0);
    if (outstanding > 0) setTender(key, String(outstanding));
  };

  const reset = () => {
    setLines([]);
    setTenders({ CASH: "", MOBILE_MONEY: "", CARD: "" });
    setDiscount(0);
    setCouponCode("");
    focusScan();
  };

  const takePayment = useCallback(
    async (dispensing?: Record<string, string>) => {
      if (lines.length === 0 || tendered < net) return;

      const sale: QueuedSale = {
        client_reference: newClientReference(),
        organization: orgId ?? 0,
        items: lines.map((l) => ({
          product: l.product,
          quantity: l.quantity,
          unit_price: l.unit_price,
          tax_rate: l.tax_rate,
          label: l.label,
        })),
        payments: TENDERS.filter((t) => Number(tenders[t.key]) > 0).map((t) => ({
          method: t.key,
          amount: tenders[t.key],
        })),
        dispensing,
        total: String(net),
        queued_at: new Date().toISOString(),
        attempts: 0,
      };

      // Queue first, send second. If the send fails the sale is already on disk;
      // the other order loses it.
      await enqueue(sale);
      refreshQueue();
      reset();

      const result = await drain();
      setNotice(
        result.failed > 0
          ? { text: "Sale held offline — it will sync when the connection returns.", tone: "warn" }
          : { text: `Sale complete. Change ${money(tendered - net)}.`, tone: "info" },
      );
    },
    [lines, tendered, net, tenders, orgId, drain, refreshQueue],
  );

  /* ---------------------------------------------------------------- keyboard */

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // A scanner is a keyboard that types fast and presses Enter. F-keys are
      // the tender shortcuts a cashier learns in a day and then never looks at.
      if (e.key === "F2" || e.key === "F3" || e.key === "F4") {
        e.preventDefault();
        const tender = TENDERS.find((t) => t.hotkey === e.key);
        if (tender) payExactly(tender.key);
        return;
      }
      if (e.key === "F8") {
        e.preventDefault();
        reset();
        return;
      }
      if (e.key === "F9" && lines.length > 0 && tendered >= net) {
        e.preventDefault();
        if (needsPharmacist) setDispensingOpen(true);
        else void takePayment();
        return;
      }
      if (e.key === "Escape") {
        focusScan();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  /* ------------------------------------------------------------------ render */

  const outstanding = Math.max(net - tendered, 0);
  const change = Math.max(tendered - net, 0);

  return (
    <div className="flex h-[calc(100vh-7rem)] flex-col gap-3">
      {/* Connection and queue state, always visible. A cashier must know the
          till is holding sales without having to go looking. */}
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-semibold tracking-tight text-ink-900">Counter</h1>
        {online ? (
          <Badge tone="success">Online</Badge>
        ) : (
          <Badge tone="warning">
            <WifiOff className="mr-1 inline h-3 w-3" />
            Offline — still selling
          </Badge>
        )}
        {pending > 0 && (
          <Badge tone="info">
            <CloudOff className="mr-1 inline h-3 w-3" />
            {pending} sale{pending === 1 ? "" : "s"} waiting to sync
          </Badge>
        )}
        <span className="ml-auto text-xs text-ink-500">
          F2 cash · F3 MoMo · F4 card · F8 clear · F9 pay
        </span>
      </div>

      <div className="grid min-h-0 flex-1 gap-3 lg:grid-cols-[1fr_22rem]">
        {/* Basket ------------------------------------------------------- */}
        <div className="flex min-h-0 flex-col rounded-lg border border-line bg-surface-0">
          <div className="border-b border-line p-3">
            <div className="relative">
              <ScanLine className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-ink-400" />
              <input
                ref={scanRef}
                value={code}
                onChange={(e) => setCode(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && code.trim()) {
                    e.preventDefault();
                    scan.mutate(code.trim());
                  }
                }}
                placeholder="Scan a barcode, or type a code and press Enter"
                className="h-12 w-full rounded-md border border-line bg-surface-0 pl-11 pr-3 text-base text-ink-900 outline-none focus:border-brand-500"
                autoComplete="off"
                spellCheck={false}
              />
            </div>
            {notice && (
              <p
                className={`mt-2 flex items-center gap-1.5 text-sm ${
                  notice.tone === "warn" ? "text-warning-700" : "text-ink-600"
                }`}
              >
                {notice.tone === "warn" && <TriangleAlert className="h-3.5 w-3.5" />}
                {notice.text}
              </p>
            )}
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto">
            {lines.length === 0 ? (
              <div className="flex h-full items-center justify-center p-8 text-center text-sm text-ink-500">
                Scan the first item to start a sale.
              </div>
            ) : (
              <ul className="divide-y divide-line">
                {lines.map((line, index) => (
                  <li key={line.product} className="flex items-center gap-3 px-3 py-2.5">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="truncate text-ink-900">{line.label}</span>
                        {line.is_controlled && <Badge tone="danger">Controlled</Badge>}
                        {line.requires_prescription && !line.is_controlled && (
                          <Badge tone="warning">Rx</Badge>
                        )}
                      </div>
                      <div className="text-xs text-ink-500">
                        {money(line.unit_price)} each
                        {line.quantity > line.on_hand && (
                          <span className="ml-2 text-danger-700">
                            only {line.on_hand} in stock
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-1">
                      <button
                        aria-label="Less"
                        className="rounded border border-line p-1 text-ink-600 hover:bg-surface-100"
                        onClick={() => {
                          setLines((c) =>
                            c
                              .map((l, i) =>
                                i === index ? { ...l, quantity: l.quantity - 1 } : l,
                              )
                              .filter((l) => l.quantity > 0),
                          );
                          focusScan();
                        }}
                      >
                        <Minus className="h-3.5 w-3.5" />
                      </button>
                      <span className="w-10 text-center tabular-nums text-ink-900">
                        {line.quantity}
                      </span>
                      <button
                        aria-label="More"
                        className="rounded border border-line p-1 text-ink-600 hover:bg-surface-100"
                        onClick={() => {
                          setLines((c) =>
                            c.map((l, i) => (i === index ? { ...l, quantity: l.quantity + 1 } : l)),
                          );
                          focusScan();
                        }}
                      >
                        <Plus className="h-3.5 w-3.5" />
                      </button>
                    </div>
                    <span className="w-24 shrink-0 text-right tabular-nums text-ink-900">
                      {money(Number(line.unit_price) * line.quantity)}
                    </span>
                    <button
                      aria-label="Remove"
                      className="shrink-0 rounded p-1 text-ink-400 hover:text-danger-600"
                      onClick={() => {
                        setLines((c) => c.filter((_, i) => i !== index));
                        focusScan();
                      }}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* Payment ------------------------------------------------------ */}
        <div className="flex min-h-0 flex-col gap-3 overflow-y-auto">
          <div className="rounded-lg border border-line bg-surface-0 p-3">
            <dl className="space-y-1 text-sm">
              <div className="flex justify-between">
                <dt className="text-ink-600">Subtotal</dt>
                <dd className="tabular-nums">{money(gross)}</dd>
              </div>
              {discount > 0 && (
                <div className="flex justify-between text-success-700">
                  <dt>Discount</dt>
                  <dd className="tabular-nums">−{money(discount)}</dd>
                </div>
              )}
              <div className="flex justify-between text-ink-500">
                <dt>of which VAT</dt>
                <dd className="tabular-nums">{money(tax)}</dd>
              </div>
              <div className="flex justify-between border-t border-line pt-2 text-lg font-semibold text-ink-900">
                <dt>Total</dt>
                <dd className="tabular-nums">{money(net)}</dd>
              </div>
            </dl>
          </div>

          <div className="rounded-lg border border-line bg-surface-0 p-3">
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-500">
              Coupon
            </div>
            <div className="flex gap-2">
              <Input
                value={couponCode}
                onChange={(e) => setCouponCode(e.target.value.toUpperCase())}
                placeholder="SAVE10"
                disabled={!online}
              />
              <Button
                variant="secondary"
                onClick={() => applyCoupon.mutate(couponCode)}
                disabled={!couponCode.trim() || applyCoupon.isPending || !online}
              >
                Apply
              </Button>
            </div>
            {promotions.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {promotions.slice(0, 4).map((p) => (
                  <button
                    key={p.code}
                    className="rounded border border-line px-1.5 py-0.5 text-xs text-ink-600 hover:bg-surface-100"
                    onClick={() => {
                      setCouponCode(p.code);
                      applyCoupon.mutate(p.code);
                    }}
                    title={p.name}
                  >
                    {p.code}
                  </button>
                ))}
              </div>
            )}
            {!online && (
              <p className="mt-2 text-xs text-ink-500">
                Coupons need the server. The sale can still be completed.
              </p>
            )}
          </div>

          <div className="rounded-lg border border-line bg-surface-0 p-3">
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-500">
              Tender
            </div>
            <div className="space-y-2">
              {TENDERS.map(({ key, label, hotkey, icon: Icon }) => (
                <div key={key} className="flex items-center gap-2">
                  <button
                    className="flex w-32 shrink-0 items-center gap-1.5 rounded-md border border-line px-2 py-1.5 text-sm text-ink-700 hover:bg-surface-100"
                    onClick={() => payExactly(key)}
                    title={`${label} — ${hotkey}`}
                  >
                    <Icon className="h-4 w-4 text-ink-400" />
                    {label}
                    <span className="ml-auto text-[10px] text-ink-400">{hotkey}</span>
                  </button>
                  <Input
                    value={tenders[key]}
                    onChange={(e) => setTender(key, e.target.value)}
                    className="text-right tabular-nums"
                    placeholder="0"
                  />
                </div>
              ))}
            </div>
            <dl className="mt-3 space-y-1 border-t border-line pt-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-ink-600">Tendered</dt>
                <dd className="tabular-nums">{money(tendered)}</dd>
              </div>
              <div
                className={`flex justify-between font-semibold ${
                  outstanding > 0 ? "text-danger-700" : "text-success-700"
                }`}
              >
                <dt>{outstanding > 0 ? "Still to pay" : "Change"}</dt>
                <dd className="tabular-nums">
                  {money(outstanding > 0 ? outstanding : change)}
                </dd>
              </div>
            </dl>
          </div>

          <ErrorNote error={scan.error ?? applyCoupon.error} />

          <div className="mt-auto flex gap-2">
            <Button variant="ghost" onClick={reset} disabled={lines.length === 0}>
              Clear (F8)
            </Button>
            <Button
              className="flex-1"
              onClick={() => (needsPharmacist ? setDispensingOpen(true) : void takePayment())}
              disabled={lines.length === 0 || outstanding > 0}
            >
              {needsPharmacist ? "Dispense & pay" : "Take payment"} (F9)
            </Button>
          </div>
        </div>
      </div>

      {dispensingOpen && (
        <DispensingDrawer
          onClose={() => {
            setDispensingOpen(false);
            focusScan();
          }}
          onConfirm={(details) => {
            setDispensingOpen(false);
            void takePayment(details);
          }}
        />
      )}
    </div>
  );
}
