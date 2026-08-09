import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, BookOpen } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Badge, Card, PageHeader, Spinner } from "../components/ui";
import { api } from "../lib/api";
import type { Paginated, StatutoryRate } from "../lib/types";

/** The versioned PAYE / RSSB / CBHI rate table the payroll engine reads from.
 * Rates here are data, never hard-coded — a new Finance Law becomes a new
 * row with `effective_from` set. See docs/18-rwanda-integrations-and-statutory.md
 * §3 for the brackets. */
const TYPE_BLURB: Record<string, string> = {
  PAYE_BRACKET: "Progressive PAYE — Law 027/2022 brackets (0 / 10 / 20 / 30 %).",
  PENSION_EMPLOYEE: "RSSB pension — employee share.",
  PENSION_EMPLOYER: "RSSB pension — employer share.",
  MATERNITY_EMPLOYEE: "Maternity leave contribution — employee share (0.6 % of net).",
  MATERNITY_EMPLOYER: "Maternity leave contribution — employer share.",
  CBHI: "Community-based health insurance — 0.5 % of net (Law 66/2018).",
  OCCUPATIONAL_HAZARD: "Occupational hazards contribution — employer.",
};

export function StatutoryRatesPage() {
  const navigate = useNavigate();

  const ratesQ = useQuery({
    queryKey: ["statutory-rates"],
    queryFn: () => api<Paginated<StatutoryRate>>("/api/hr/statutory-rates/?page_size=200"),
  });

  const grouped: Record<string, StatutoryRate[]> = {};
  (ratesQ.data?.results ?? []).forEach((r) => {
    (grouped[r.rate_type] ??= []).push(r);
  });

  const order = [
    "PAYE_BRACKET",
    "PENSION_EMPLOYEE",
    "PENSION_EMPLOYER",
    "MATERNITY_EMPLOYEE",
    "MATERNITY_EMPLOYER",
    "CBHI",
    "OCCUPATIONAL_HAZARD",
  ];

  return (
    <div>
      <button
        onClick={() => navigate("/people")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> People Home
      </button>

      <PageHeader title="Statutory rates (PAYE / RSSB / CBHI)" />

      {ratesQ.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {ratesQ.data && (
        <div className="flex flex-col gap-4">
          {order.map((key) => {
            const rows = grouped[key] ?? [];
            if (rows.length === 0) return null;
            return (
              <Card key={key}>
                <div className="mb-2 flex items-center gap-2">
                  <BookOpen className="h-4 w-4 text-ink-500" />
                  <h2 className="text-sm font-semibold text-ink-900">{key.replace(/_/g, " ")}</h2>
                  <Badge tone="neutral">
                    {rows.length} row{rows.length === 1 ? "" : "s"}
                  </Badge>
                </div>
                <p className="mb-3 text-xs text-ink-500">{TYPE_BLURB[key] ?? ""}</p>
                <div className="overflow-hidden rounded-md border border-line">
                  <table className="w-full text-sm">
                    <thead className="border-b border-line bg-surface-50 text-left text-xs text-ink-500">
                      <tr>
                        <th className="px-3 py-2">Band min (RWF)</th>
                        <th className="px-3 py-2">Band max (RWF)</th>
                        <th className="px-3 py-2 text-right">Rate</th>
                        <th className="px-3 py-2">Effective from</th>
                        <th className="px-3 py-2">Effective to</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((r) => (
                        <tr key={r.id} className="border-b border-line last:border-0">
                          <td className="px-3 py-2 font-mono tabular-nums">
                            {Number(r.band_min).toLocaleString()}
                          </td>
                          <td className="px-3 py-2 font-mono tabular-nums">
                            {r.band_max ? Number(r.band_max).toLocaleString() : "∞ (open-ended)"}
                          </td>
                          <td className="px-3 py-2 text-right font-mono font-semibold tabular-nums">
                            {Number(r.rate_pct).toFixed(3)} %
                          </td>
                          <td className="px-3 py-2">{r.effective_from}</td>
                          <td className="px-3 py-2 text-ink-700">
                            {r.effective_to ?? <span className="text-ink-400">current</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            );
          })}
          {Object.keys(grouped).length === 0 && (
            <Card>
              <p className="py-6 text-center text-sm text-ink-500">
                No statutory rates configured yet — payroll cannot compute deductions until at least
                the PAYE bracket and the RSSB pension rows are present.
              </p>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
