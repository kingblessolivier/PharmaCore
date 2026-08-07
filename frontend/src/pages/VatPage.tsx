import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, FileDown, Download, FileBarChart } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useFinanceDocument } from "../lib/financeDocuments";
import { useAuth } from "../lib/auth";
import type { VatReturn } from "../lib/types";
import { Badge, Button, Card, PageHeader, Spinner } from "../components/ui";
import { SectionCard, SectionGrid } from "../components/AppHome";

type PeriodPreset = "this-month" | "last-month" | "this-quarter" | "ytd" | "custom";

function periodFor(preset: PeriodPreset, customStart: string, customEnd: string) {
  const now = new Date();
  const iso = (d: Date) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const today = iso(now);
  const monthStart = iso(new Date(now.getFullYear(), now.getMonth(), 1));
  const lastMonthStart = iso(new Date(now.getFullYear(), now.getMonth() - 1, 1));
  const lastMonthEnd = iso(new Date(now.getFullYear(), now.getMonth(), 0));
  const quarterStart = iso(new Date(now.getFullYear(), Math.floor(now.getMonth() / 3) * 3, 1));
  const ytdStart = iso(new Date(now.getFullYear(), 0, 1));
  switch (preset) {
    case "this-month": return { start: monthStart, end: today };
    case "last-month": return { start: lastMonthStart, end: lastMonthEnd };
    case "this-quarter": return { start: quarterStart, end: today };
    case "ytd": return { start: ytdStart, end: today };
    case "custom": return { start: customStart, end: customEnd };
  }
}

const money = (s: string | number) =>
  Number(s).toLocaleString(undefined, { maximumFractionDigits: 0 });

/** Render the VAT-return report as a downloadable CSV — the format the
 * accountant uploads / types into RRA e-Tax. Column order mirrors the report. */
function exportCsv(v: VatReturn): string {
  const rows = v.csv.map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(",")).join("\n");
  return `VAT return ${v.start} to ${v.end}\n\n${rows}\n`;
}

export function VatPage() {
  const filed = useFinanceDocument("vat-return");
  const navigate = useNavigate();
  const { user } = useAuth();
  const orgId = user?.organization ?? 0;
  const [preset, setPreset] = useState<PeriodPreset>("this-month");
  const [customStart, setCustomStart] = useState("");
  const [customEnd, setCustomEnd] = useState("");
  const period = useMemo(() => periodFor(preset, customStart, customEnd), [preset, customStart, customEnd]);

  const q = useQuery({
    queryKey: ["vat-return", orgId, period.start, period.end],
    queryFn: () =>
      api<VatReturn>(
        `/api/finance/reports/vat-return/?organization=${orgId}&start=${period.start}&end=${period.end}`,
      ),
    enabled: orgId > 0,
  });
  const v = q.data;

  function downloadCsv() {
    if (!v) return;
    const blob = new Blob([exportCsv(v)], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `vat-return-${v.start}-to-${v.end}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="max-w-6xl">
      <button
        onClick={() => navigate("/finance")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> Finance Home
      </button>

      <PageHeader
        title="VAT return (Rwanda)"
        action={
          <Button
            variant="secondary"
            onClick={() => filed.mutate({ start: period.start, end: period.end })}
            disabled={filed.isPending}
          >
            <FileDown className="h-4 w-4" />
            {filed.isPending ? "Preparing…" : "Filed copy (PDF)"}
          </Button>
        }
      />
      <p className="mb-4 text-sm text-ink-500">
        Per-class Output and Input derived from posted journal entries, plus withholding,
        the running carry-forward, and a CSV draft for the RRA e-Tax filing.
        {/* A CSV draft proves nothing after the fact — the filed copy is the record. */}
        {filed.data && (
          <>
            {" "}
            Filed copy issued as <strong>{filed.data.doc_number}</strong>.
          </>
        )}
      </p>

      {/* Period switcher — same UI as FinanceHome. */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium uppercase tracking-wide text-ink-500">Period</span>
        {(["this-month", "last-month", "this-quarter", "ytd", "custom"] as PeriodPreset[]).map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => setPreset(p)}
            className={`rounded-md border px-2.5 py-1 text-xs ${
              preset === p
                ? "border-emerald-700 bg-emerald-700 text-white"
                : "border-line bg-surface-0 text-ink-700 hover:bg-surface-50"
            }`}
          >
            {p === "this-month" ? "This month"
              : p === "last-month" ? "Last month"
              : p === "this-quarter" ? "This quarter"
              : p === "ytd" ? "YTD"
              : "Custom"}
          </button>
        ))}
        {preset === "custom" && (
          <div className="flex items-center gap-2">
            <input
              type="date"
              value={customStart}
              onChange={(e) => setCustomStart(e.target.value)}
              className="rounded-md border border-line bg-surface-0 px-2 py-1 text-xs"
            />
            <span className="text-xs text-ink-500">→</span>
            <input
              type="date"
              value={customEnd}
              onChange={(e) => setCustomEnd(e.target.value)}
              className="rounded-md border border-line bg-surface-0 px-2 py-1 text-xs"
            />
          </div>
        )}
        {v && (
          <button
            type="button"
            onClick={downloadCsv}
            className="ml-auto flex items-center gap-1.5 rounded-md border border-line bg-surface-0 px-3 py-1 text-xs text-ink-700 hover:bg-surface-50"
          >
            <Download className="h-3.5 w-3.5" /> Download CSV draft
          </button>
        )}
      </div>

      {q.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {v && (
        <>
          <Card title="VAT summary">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Tile label="Output (total)" value={`RWF ${money(v.output_total)}`} />
              <Tile label="Input (recoverable)" value={`RWF ${money(v.input_total)}`} />
              <Tile label="Withholding" value={`RWF ${money(v.withholding_total)}`} />
              <Tile
                label="Net payable"
                value={`RWF ${money(v.net_payable)}`}
                tone={Number(v.net_payable) > 0 ? "warn" : "ok"}
              />
            </div>
            <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Tile label="Remitted in period" value={`RWF ${money(v.paid_in_period)}`} />
              <Tile
                label="Due after remittances"
                value={`RWF ${money(v.amount_due_after_payments)}`}
                tone={Number(v.amount_due_after_payments) > 0 ? "warn" : "ok"}
              />
              <Tile label="Carry-forward" value={`RWF ${money(v.running_carry_forward)}`} hint="VAT Output − VAT Input" />
              <Tile label="Period" value={`${v.start} → ${v.end}`} />
            </div>
          </Card>

          <Card title="Per-class breakdown" className="mt-4">
            <table className="w-full text-sm">
              <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-500">
                <tr>
                  <th className="py-2">Section</th>
                  <th className="py-2">Class</th>
                  <th className="py-2 text-right">Output</th>
                  <th className="py-2 text-right">Input</th>
                  <th className="py-2 text-right">Net</th>
                </tr>
              </thead>
              <tbody>
                {(["A", "B", "C", "D"] as const).map((cls) => {
                  const out = Number(v.output_by_class[cls]);
                  const inp = Number(v.input_by_class[cls]);
                  return (
                    <tr key={cls} className="border-b border-line/50">
                      <td className="py-2 text-ink-700">
                        <Badge>{cls === "B" ? "Standard 18%" : cls === "A" ? "Exempt" : cls === "C" ? "Zero-rated" : "Special"}</Badge>
                      </td>
                      <td className="py-2 font-medium text-ink-900">{cls}</td>
                      <td className="py-2 text-right tabular-nums">{money(out)}</td>
                      <td className="py-2 text-right tabular-nums">{money(inp)}</td>
                      <td className="py-2 text-right tabular-nums font-medium">
                        {money(out - inp)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot className="border-t border-line text-sm font-medium text-ink-900">
                <tr>
                  <td className="py-2" colSpan={2}>Total</td>
                  <td className="py-2 text-right tabular-nums">{money(v.output_total)}</td>
                  <td className="py-2 text-right tabular-nums">{money(v.input_total)}</td>
                  <td className="py-2 text-right tabular-nums">{money(v.net_payable)}</td>
                </tr>
              </tfoot>
            </table>
          </Card>

          <SectionGrid className="mt-6">
            <SectionCard
              icon={FileBarChart}
              title="EBM fiscalization audit"
              description="Per-receipt VAT breakdown mirrored from the SDC/OSDC."
              to="/finance/tax-ebm"
            />
            <SectionCard
              icon={FileBarChart}
              title="Tax payments register"
              description="RRA remittances recorded against this org."
              to="/finance/tax/payments"
            />
          </SectionGrid>
        </>
      )}
    </div>
  );
}

function Tile({ label, value, hint, tone }: { label: string; value: string; hint?: string; tone?: "warn" | "ok" }) {
  return (
    <div className={`rounded-lg border p-3 ${
      tone === "warn" ? "border-amber-300 bg-amber-50" : tone === "ok" ? "border-emerald-300 bg-emerald-50" : "border-line bg-surface-0"
    }`}>
      <div className="text-xs font-medium uppercase tracking-wide text-ink-500">{label}</div>
      <div className="mt-1 text-base font-semibold tabular-nums text-ink-900">{value}</div>
      {hint && <div className="mt-1 text-xs text-ink-500">{hint}</div>}
    </div>
  );
}