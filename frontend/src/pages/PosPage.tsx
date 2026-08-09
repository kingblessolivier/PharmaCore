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
import { CounterCover } from "../components/CounterCover";
import { SafetyCheck, type Screening } from "../components/SafetyCheck";
import { Substitutes } from "../components/Substitutes";
import type { Quote } from "../lib/insurance";
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
import type { CounterSearchHit, CounterSearchResponse, SaleUnit } from "../lib/types";

interface Line {
  product: number;
  label: string;
  /** The pack sizes this medicine is sold in. */
  sale_units: SaleUnit[];
  /** How many of each pack size, keyed by unit code. A customer taking three
   *  boxes and four loose tablets is one line with two entries, not two lines
   *  for the same medicine. */
  quantities: Record<string, number>;
  /** 1 whole only, 2 halves, 4 quarters — approved per product. */
  divisibility: number;
  split_note: string;
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

/** What one line comes to, and how many single units it draws off the shelf.
 *
 * A customer taking three boxes and four loose tablets is one line: the boxes
 * and the loose tablets are the same medicine at two pack sizes, and a receipt
 * that splits them into two lines reads as two purchases. */
/** One item per pack size actually taken.
 *
 * The screen shows one line per medicine; the sale records what left the shelf
 * at each size, because three boxes and four loose tablets come off stock
 * differently and are priced differently. */
function saleItems(line: Line) {
  const sizes = line.sale_units.length
    ? line.sale_units
    : [{ code: "", unit_price: line.unit_price } as SaleUnit];
  return sizes
    .filter((u) => (line.quantities[u.code] ?? 0) > 0)
    .map((u) => ({
      product: line.product,
      quantity: line.quantities[u.code],
      unit: u.code || undefined,
      unit_price: u.unit_price || line.unit_price,
      tax_rate: line.tax_rate,
      label: line.label,
    }));
}

/** What one single unit costs — what the insurer's split is quoted against. */
function baseUnitPrice(line: Line): string {
  const base = line.sale_units.find((u) => u.is_base);
  return base?.unit_price ?? line.unit_price;
}

function lineTotals(line: Line) {
  let money = 0;
  let dispensed = 0;
  for (const unit of line.sale_units) {
    const qty = line.quantities[unit.code] ?? 0;
    if (!qty) continue;
    money += Number(unit.unit_price) * qty;
    dispensed += Number(unit.factor_to_base) * qty;
  }
  // A medicine with no pack sizes recorded behaves as it always did.
  if (line.sale_units.length === 0) {
    const qty = line.quantities[""] ?? 0;
    money += Number(line.unit_price) * qty;
    dispensed += qty;
  }
  return { money, dispensed };
}

/** How much one press of +/- moves a pack size.
 *
 * A single tablet a pharmacist has approved for halving steps by a half. A box
 * always steps by a whole box: half a box of a hundred is fifty tablets, and
 * the person meant one of those two things. */
function step(line: Line, unit: SaleUnit | undefined, direction: 1 | -1): number {
  const current = line.quantities[unit?.code ?? ""] ?? 0;
  const splittable = (unit?.is_base ?? true) && line.divisibility > 1;
  const size = splittable ? 1 / line.divisibility : 1;
  return Math.max(0, Math.round((current + direction * size) * 1000) / 1000);
}

function totals(lines: Line[], discount: number) {
  const gross = lines.reduce((s, l) => s + lineTotals(l).money, 0);
  const net = Math.max(gross - discount, 0);
  const tax = lines.reduce((s, l) => {
    const rate = Number(l.tax_rate);
    if (rate <= 0) return s;
    return s + (lineTotals(l).money * rate) / (100 + rate);
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

  /* The insurer's answer, obtained before the goods move. `due` is what the
     person at the counter actually has to hand over: the scheme's share is not
     collected here, it is claimed. */
  const [quote, setQuote] = useState<Quote | null>(null);
  /* A major interaction is not a warning to scroll past. The sale is held until
     somebody acknowledges it — the pharmacist keeps the judgement, but the
     system stops pretending it never noticed. */
  const [screening, setScreening] = useState<Screening | null>(null);
  /** Which line is asking for an alternative, if any. */
  const [substitutesFor, setSubstitutesFor] = useState<number | null>(null);
  const [overrideNote, setOverrideNote] = useState("");
  const blocked = screening?.requires_override === true && overrideNote.trim().length === 0;
  const [memberNumber, setMemberNumber] = useState("");
  const covered = quote?.eligible === true;
  const due = covered ? Number(quote?.patient_pays ?? net) : net;
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
        const line = copy[existing];
        copy[existing] = {
          ...line,
          quantities: { ...line.quantities, "": (line.quantities[""] ?? 0) + hit.units },
        };
        return copy;
      }
      return [
        ...current,
        {
          product: hit.product,
          label: hit.label,
          // A carton barcode adds the carton, not one tablet.
          quantities: { "": hit.units },
          sale_units: [],
          divisibility: 1,
          split_note: "",
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

  /* ------------------------------------------------------------- typing */
  /* Most pharmacies here have no barcode labelling, so typing a name is not a
     fallback to scanning — it is the primary way a line gets onto the basket.
     The scanner path is untouched: a scanner types fast and presses Enter, and
     `looks_like_a_barcode` on the server tells the two apart without asking the
     cashier which mode they are in. */

  const [highlight, setHighlight] = useState(0);
  const typed = code.trim();
  /* A barcode is answered by Enter, not by a dropdown; suppress the list for one
     so a scan never flashes a menu on its way past. */
  const isBarcode = typed.length >= 8 && /^\d+$/.test(typed);

  const search = useQuery({
    queryKey: ["counter-search", orgId, typed],
    enabled: orgId != null && typed.length >= 2 && !isBarcode,
    queryFn: () =>
      api<CounterSearchResponse>(
        `/api/retail/counter/search/?organization=${orgId}&q=${encodeURIComponent(typed)}`,
      ),
    /* Keep the previous list on screen while the next one loads, so the rows do
       not blink out from under a finger already moving toward them. */
    placeholderData: (prev) => prev,
  });

  const hits = search.data?.results ?? [];
  const showList = !isBarcode && typed.length >= 2 && hits.length > 0;

  useEffect(() => setHighlight(0), [typed]);

  /* A typed hit carries the medicine's packaging chain, so the line starts on
     the unit the pharmacy sells by default — a box where boxes are the usual
     sale, a tablet where they are not — and the cashier can change it per line
     without retyping the product. */
  const addHit = useCallback(
    (hit: CounterSearchHit) => {
      const units = hit.sale_units ?? [];
      const preferred = units.find((u) => u.is_default) ?? units.find((u) => u.is_base);

      setLines((current) => {
        const at = current.findIndex((l) => l.product === hit.product);
        if (at >= 0) {
          // Already on the ticket — add one more of the usual pack size rather
          // than starting a second line for the same medicine.
          const copy = [...current];
          const line = copy[at];
          const code = preferred?.code ?? "";
          copy[at] = {
            ...line,
            quantities: { ...line.quantities, [code]: (line.quantities[code] ?? 0) + 1 },
          };
          return copy;
        }
        return [
          ...current,
          {
            product: hit.product,
            label: hit.label,
            quantities: { [preferred?.code ?? ""]: 1 },
            sale_units: units,
            divisibility: hit.divisibility ?? 1,
            split_note: hit.split_note ?? "",
            unit_price: preferred?.unit_price || hit.unit_price || "0",
            tax_rate: "18",
            requires_prescription: hit.requires_prescription,
            is_controlled: hit.is_controlled,
            on_hand: hit.on_hand,
          },
        ];
      });
      setNotice(
        hit.on_hand <= 0 ? { text: `${hit.label} shows no stock on hand.`, tone: "warn" } : null,
      );
      setCode("");
      focusScan();
    },
    [focusScan],
  );

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
    const outstanding = Math.max(due - tendered, 0);
    if (outstanding > 0) setTender(key, String(outstanding));
  };

  const reset = () => {
    setLines([]);
    setTenders({ CASH: "", MOBILE_MONEY: "", CARD: "" });
    setDiscount(0);
    setQuote(null);
    setMemberNumber("");
    setScreening(null);
    setOverrideNote("");
    setCouponCode("");
    focusScan();
  };

  const takePayment = useCallback(
    async (dispensing?: Record<string, string>) => {
      if (lines.length === 0 || tendered < due || blocked) return;

      const sale: QueuedSale = {
        client_reference: newClientReference(),
        organization: orgId ?? 0,
        items: lines.flatMap((l) => saleItems(l)),
        payments: TENDERS.filter((t) => Number(tenders[t.key]) > 0).map((t) => ({
          method: t.key,
          amount: tenders[t.key],
        })),
        dispensing,
        total: String(due),
        // Carried so the sale can be reconciled against the claim the scheme
        // will settle, rather than the two being matched up by hand later.
        member_number: memberNumber || undefined,
        // Kept with the sale: a dispensing decision that overrode a major
        // interaction has to be answerable for afterwards.
        screening_override: overrideNote.trim() || undefined,
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
          : { text: `Sale complete. Change ${money(tendered - due)}.`, tone: "info" },
      );
    },
    [lines, tendered, due, tenders, orgId, drain, refreshQueue, memberNumber, blocked],
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

  const outstanding = Math.max(due - tendered, 0);
  const change = Math.max(tendered - due, 0);

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
                  if (showList && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
                    e.preventDefault();
                    setHighlight((i) =>
                      e.key === "ArrowDown" ? Math.min(i + 1, hits.length - 1) : Math.max(i - 1, 0),
                    );
                    return;
                  }
                  if (e.key === "Escape" && showList) {
                    e.preventDefault();
                    setCode("");
                    return;
                  }
                  if (e.key !== "Enter" || !typed) return;
                  e.preventDefault();
                  /* A visible list means the cashier is choosing, so Enter takes
                     what is highlighted. Otherwise it is a scan or a bare code. */
                  if (showList && hits[highlight]) {
                    addHit(hits[highlight]);
                  } else {
                    scan.mutate(typed);
                  }
                }}
                placeholder="Scan a barcode, or type a medicine name"
                className="h-12 w-full rounded-md border border-line bg-surface-0 pl-11 pr-3 text-base text-ink-900 outline-none focus:border-brand-500"
                autoComplete="off"
                spellCheck={false}
                role="combobox"
                aria-expanded={showList}
                aria-controls="counter-search-results"
              />
              {showList && (
                <ul
                  id="counter-search-results"
                  className="absolute left-0 right-0 top-14 z-30 max-h-80 overflow-y-auto rounded-md border border-line bg-surface-0 py-1 shadow-lg"
                >
                  {hits.map((hit, i) => (
                    <li key={hit.product}>
                      <button
                        type="button"
                        onMouseDown={(e) => e.preventDefault()}
                        onMouseEnter={() => setHighlight(i)}
                        onClick={() => addHit(hit)}
                        className={`flex w-full items-center justify-between gap-3 px-3 py-2 text-left ${
                          i === highlight ? "bg-brand-50" : "hover:bg-surface-100"
                        }`}
                      >
                        <span className="min-w-0">
                          <span className="block truncate text-sm font-medium text-ink-900">
                            {hit.label}
                            {hit.brand_name && (
                              <span className="ml-1.5 font-normal text-ink-500">
                                ({hit.brand_name})
                              </span>
                            )}
                          </span>
                          <span className="block truncate text-xs text-ink-500">
                            {[hit.dosage_form, hit.pack_size].filter(Boolean).join(" · ")}
                            {hit.requires_prescription && " · prescription"}
                            {hit.is_controlled && " · controlled"}
                          </span>
                        </span>
                        <span className="shrink-0 text-right">
                          <span className="block text-sm tabular-nums text-ink-900">
                            {hit.unit_price ? money(Number(hit.unit_price)) : "no price"}
                          </span>
                          {/* Stock is the thing that decides whether this row is
                              usable, so it is never further away than the price. */}
                          <span
                            className={`block text-xs tabular-nums ${
                              hit.on_hand > 0 ? "text-ink-500" : "text-danger-600"
                            }`}
                          >
                            {hit.on_hand > 0 ? `${hit.on_hand} in stock` : "out of stock"}
                          </span>
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            {!isBarcode && typed.length >= 2 && hits.length === 0 && !search.isFetching && (
              <p className="mt-2 text-sm text-ink-500">
                Nothing here matches “{typed}”. Check the spelling, or search by the active
                ingredient.
              </p>
            )}
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
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-ink-500">
                        {(() => {
                          const { dispensed } = lineTotals(line);
                          const singles = line.sale_units.find((u) => u.is_base)?.label ?? "units";
                          return dispensed > line.on_hand ? (
                            <>
                              <span className="text-danger-700">
                                needs {dispensed.toLocaleString()} {singles.toLowerCase()} · only{" "}
                                {line.on_hand.toLocaleString()} on the shelf
                              </span>
                              {/* An empty shelf was a dead end: the customer
                                  left for a pharmacy holding the same molecule
                                  under a different brand. */}
                              <button
                                onClick={() =>
                                  setSubstitutesFor(
                                    substitutesFor === line.product ? null : line.product,
                                  )
                                }
                                className="text-brand-600 hover:underline"
                              >
                                {substitutesFor === line.product ? "Hide" : "What else can I give?"}
                              </button>
                            </>
                          ) : (
                            <span>
                              {dispensed.toLocaleString()} {singles.toLowerCase()} ·{" "}
                              {line.on_hand.toLocaleString()} on the shelf
                            </span>
                          );
                        })()}

                        {/* Which packaging level this line counts. Switching it
                            reprices the line, because a box is not a hundred
                            times a loose tablet — breaking a pack costs the
                            pharmacy the ability to sell or return it sealed. */}
                        {/* One row per pack size this medicine is sold in, so a
                            customer taking three boxes and four loose tablets is
                            one line with two counts. */}
                      </div>

                      <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1.5">
                        {(line.sale_units.length
                          ? line.sale_units
                          : [{ code: "", label: "Units", is_base: true } as SaleUnit]
                        ).map((unit) => {
                          const qty = line.quantities[unit.code] ?? 0;
                          const change = (direction: 1 | -1) => {
                            setLines((c) =>
                              c
                                .map((l, i) =>
                                  i === index
                                    ? {
                                        ...l,
                                        quantities: {
                                          ...l.quantities,
                                          [unit.code]: step(l, unit, direction),
                                        },
                                      }
                                    : l,
                                )
                                .filter((l) => lineTotals(l).dispensed > 0),
                            );
                            focusScan();
                          };
                          return (
                            <span key={unit.code || "each"} className="flex items-center gap-1">
                              <button
                                aria-label={`One less ${unit.label}`}
                                disabled={qty <= 0}
                                className="rounded border border-line p-1 text-ink-600 hover:bg-surface-100 disabled:opacity-40"
                                onClick={() => change(-1)}
                              >
                                <Minus className="h-3 w-3" />
                              </button>
                              <span className="w-10 text-center tabular-nums text-ink-900">
                                {qty % 1 === 0 ? qty : qty.toFixed(2)}
                              </span>
                              <button
                                aria-label={`One more ${unit.label}`}
                                className="rounded border border-line p-1 text-ink-600 hover:bg-surface-100"
                                onClick={() => change(+1)}
                              >
                                <Plus className="h-3 w-3" />
                              </button>
                              <span className="text-xs text-ink-600">{unit.label}</span>
                            </span>
                          );
                        })}
                      </div>
                    </div>

                    <span className="w-28 shrink-0 text-right tabular-nums text-ink-900">
                      {money(lineTotals(line).money)}
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
                {/* Rendered per line rather than in a modal: the alternative
                    belongs next to the medicine it is standing in for. */}
                {substitutesFor !== null && orgId != null && orgId > 0 && (
                  <li className="border-t border-line bg-surface-50 px-3 py-3">
                    <Substitutes
                      productId={substitutesFor}
                      organizationId={orgId}
                      productName={lines.find((l) => l.product === substitutesFor)?.label}
                      onPick={(option) => {
                        // Put it in the search box rather than adding it
                        // silently: substituting is a decision, and the
                        // cashier should see what they are about to ring up.
                        setCode(option.product_name);
                        setSubstitutesFor(null);
                        focusScan();
                      }}
                    />
                  </li>
                )}
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
              {/* When a scheme is paying part of it, the counter collects the
                  patient's share only — the rest is claimed, not taken. */}
              {covered && (
                <>
                  <div className="flex justify-between text-ink-500">
                    <dt>Scheme pays</dt>
                    <dd className="tabular-nums">−{money(Number(quote?.insurer_pays ?? 0))}</dd>
                  </div>
                  <div className="flex justify-between border-t border-line pt-2 text-lg font-semibold text-brand-700">
                    <dt>Patient pays</dt>
                    <dd className="tabular-nums">{money(due)}</dd>
                  </div>
                </>
              )}
            </dl>
          </div>

          {/* Screened before dispensing, not after. The catalogue has carried
              interactions, duplicate therapy and contraindications all along
              and nothing ever asked it. */}
          <SafetyCheck products={lines.map((l) => l.product)} onResult={setScreening} />

          {screening?.requires_override && (
            <div className="rounded-lg border border-danger-200 bg-danger-50 p-3">
              <label
                htmlFor="dur-override"
                className="mb-1 block text-xs font-semibold text-danger-900"
              >
                Why is this being dispensed anyway?
              </label>
              <input
                id="dur-override"
                className="field-control w-full"
                placeholder="Prescriber contacted, INR monitoring arranged…"
                value={overrideNote}
                onChange={(e) => setOverrideNote(e.target.value)}
              />
              <p className="mt-1 text-[11px] text-danger-800">
                The sale is held until this is filled in. It is kept with the sale.
              </p>
            </div>
          )}

          <CounterCover
            lines={lines.map((l) => ({
              product: l.product,
              quantity: lineTotals(l).dispensed,
              unit_price: baseUnitPrice(l),
            }))}
            quote={quote}
            onQuote={(q, member) => {
              setQuote(q);
              setMemberNumber(member);
            }}
          />

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
                <dd className="tabular-nums">{money(outstanding > 0 ? outstanding : change)}</dd>
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
              disabled={lines.length === 0 || outstanding > 0 || blocked}
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
