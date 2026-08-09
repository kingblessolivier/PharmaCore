/* -------------------------------------------------------------------------- */
/* Four questions an owner asks, that the ledger could already answer.         */
/*                                                                            */
/* break-even, working-capital, expiry-exposure and fx-exposure were all       */
/* computed, interpreted in plain words by the backend, and unreachable. The   */
/* expiry one is the sharpest: it works out a suggested provision against      */
/* stock that will not sell in time, and nobody could see it — so the loss     */
/* arrived as a write-off with no warning.                                     */
/*                                                                            */
/* Each endpoint returns `computable` and an `interpretation`. Both are        */
/* honoured here rather than papered over: a figure the ledger cannot support  */
/* is shown as "not enough trading to say", not as a confident zero.           */
/* -------------------------------------------------------------------------- */

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CalendarClock, Coins, Info, Landmark, TrendingUp } from "lucide-react";
import { PageHeader } from "../components/ui";
import { BarChart, ChartFrame, VizRoot } from "../components/Charts";
import { api } from "../lib/api";
import { money } from "../lib/format";
import { useDefaultOrg } from "../lib/recordData";

interface BreakEven {
  start: string;
  end: string;
  revenue: string;
  fixed_costs: string;
  contribution_margin_pct: string;
  break_even_revenue: string | null;
  break_even_revenue_per_day: string | null;
  margin_of_safety_pct: string | null;
  is_above_break_even: boolean;
}

interface WorkingCapital {
  days: number;
  inventory_value: string;
  receivable: string;
  payable: string;
  dio_days: number | null;
  dso_days: number | null;
  dpo_days: number | null;
  cash_conversion_cycle_days: number | null;
  working_capital_funding_need: string;
  computable: boolean;
  interpretation: string;
}

interface ExpiryBand {
  band: string;
  label: string;
  quantity: number;
  cost_value: string;
  provision_rate: string;
  provision: string;
}

interface ExpiryExposure {
  as_of: string;
  stock_value: string;
  at_risk_value: string;
  at_risk_pct: string;
  suggested_provision: string;
  bands: ExpiryBand[];
}

interface FxExposure {
  net_unrealised: string;
  by_currency: Record<string, string>;
  computable: boolean;
  interpretation: string;
}

function Tile({
  icon: Icon,
  label,
  value,
  hint,
  tone,
}: {
  icon: typeof Coins;
  label: string;
  value: string;
  hint?: string;
  tone?: "danger" | "warning" | "good";
}) {
  const colour =
    tone === "danger"
      ? "text-danger-700"
      : tone === "warning"
        ? "text-warning-700"
        : tone === "good"
          ? "text-success-700"
          : "text-ink-900";
  const chip =
    tone === "danger"
      ? "bg-danger-50 text-danger-700"
      : tone === "warning"
        ? "bg-warning-50 text-warning-700"
        : tone === "good"
          ? "bg-success-50 text-success-700"
          : "bg-surface-100 text-ink-600";
  return (
    <div className="rounded-lg border border-line bg-surface-0 p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-xs text-ink-500">{label}</div>
          <div className={`mt-1 text-2xl font-semibold tabular-nums ${colour}`}>{value}</div>
        </div>
        <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${chip}`}>
          <Icon className="h-4 w-4" aria-hidden />
        </span>
      </div>
      {hint && <div className="mt-0.5 text-xs text-ink-500">{hint}</div>}
    </div>
  );
}

/** The backend says when it cannot compute something. Saying so is more use
 *  than a confident zero the reader would act on. */
function NotComputable({ reason }: { reason: string }) {
  return (
    <div className="flex items-start gap-2 rounded-lg border border-line bg-surface-0 px-4 py-3 text-sm text-ink-600">
      <Info className="mt-0.5 h-4 w-4 shrink-0 text-ink-400" aria-hidden />
      {reason}
    </div>
  );
}

export function FinanceRiskPage() {
  const { orgId } = useDefaultOrg();
  const on = orgId != null && orgId > 0;
  const qs = `?organization=${orgId}`;

  const breakEven = useQuery({
    queryKey: ["break-even", orgId],
    enabled: on,
    queryFn: () => api<BreakEven>(`/api/finance/reports/break-even/${qs}`),
  });
  const capital = useQuery({
    queryKey: ["working-capital", orgId],
    enabled: on,
    queryFn: () => api<WorkingCapital>(`/api/finance/reports/working-capital/${qs}`),
  });
  const expiry = useQuery({
    queryKey: ["expiry-exposure", orgId],
    enabled: on,
    queryFn: () => api<ExpiryExposure>(`/api/finance/reports/expiry-exposure/${qs}`),
  });
  const fx = useQuery({
    queryKey: ["fx-exposure", orgId],
    enabled: on,
    queryFn: () => api<FxExposure>(`/api/finance/operations/fx-exposure/${qs}`),
  });

  const be = breakEven.data;
  const wc = capital.data;
  const ex = expiry.data;

  return (
    <div className="space-y-5">
      <PageHeader title="Risk & the cash cycle" />

      {/* --- Break-even ------------------------------------------------- */}
      <section>
        <h2 className="mb-2 text-base font-semibold tracking-tight text-ink-900">
          Is the month paying for itself?
        </h2>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Tile
            icon={TrendingUp}
            label="Revenue so far"
            value={money(Number(be?.revenue ?? 0))}
            hint={be ? `${be.start} to ${be.end}` : ""}
          />
          <Tile
            icon={Landmark}
            label="Fixed costs to cover"
            value={money(Number(be?.fixed_costs ?? 0))}
            hint={`${Number(be?.contribution_margin_pct ?? 0)}% contribution margin`}
          />
          <Tile
            icon={Coins}
            label="Break-even revenue"
            value={be?.break_even_revenue ? money(Number(be.break_even_revenue)) : "—"}
            hint={
              be?.break_even_revenue_per_day
                ? `${money(Number(be.break_even_revenue_per_day))} a day`
                : "needs a margin to divide by"
            }
          />
          <Tile
            icon={be?.is_above_break_even ? TrendingUp : AlertTriangle}
            label="Margin of safety"
            value={be?.margin_of_safety_pct ? `${Number(be.margin_of_safety_pct)}%` : "—"}
            tone={be?.is_above_break_even ? "good" : "warning"}
            hint={
              be?.is_above_break_even ? "trading above break-even" : "not yet covering fixed costs"
            }
          />
        </div>
      </section>

      {/* --- Working capital --------------------------------------------- */}
      <section>
        <h2 className="mb-2 text-base font-semibold tracking-tight text-ink-900">
          How long is money tied up?
        </h2>
        {wc && !wc.computable ? (
          <NotComputable reason={wc.interpretation} />
        ) : (
          <>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <Tile
                icon={CalendarClock}
                label="Stock sits for"
                value={wc?.dio_days != null ? `${wc.dio_days} days` : "—"}
                hint={money(Number(wc?.inventory_value ?? 0))}
              />
              <Tile
                icon={CalendarClock}
                label="Customers take"
                value={wc?.dso_days != null ? `${wc.dso_days} days` : "—"}
                hint={money(Number(wc?.receivable ?? 0))}
              />
              <Tile
                icon={CalendarClock}
                label="We take"
                value={wc?.dpo_days != null ? `${wc.dpo_days} days` : "—"}
                hint={money(Number(wc?.payable ?? 0))}
              />
              <Tile
                icon={Coins}
                label="Cash cycle"
                value={
                  wc?.cash_conversion_cycle_days != null
                    ? `${wc.cash_conversion_cycle_days} days`
                    : "—"
                }
                // A longer cycle is money the business has to fund itself.
                tone={(wc?.cash_conversion_cycle_days ?? 0) > 60 ? "warning" : undefined}
                hint={`${money(Number(wc?.working_capital_funding_need ?? 0))} to fund`}
              />
            </div>
            {wc?.interpretation && <p className="mt-2 text-xs text-ink-500">{wc.interpretation}</p>}
          </>
        )}
      </section>

      {/* --- Expiry ------------------------------------------------------- */}
      <section>
        <h2 className="mb-2 text-base font-semibold tracking-tight text-ink-900">
          What will not sell in time?
        </h2>
        <div className="mb-3 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Tile icon={Coins} label="Stock at cost" value={money(Number(ex?.stock_value ?? 0))} />
          <Tile
            icon={AlertTriangle}
            label="At risk"
            value={money(Number(ex?.at_risk_value ?? 0))}
            tone={Number(ex?.at_risk_pct ?? 0) > 20 ? "danger" : "warning"}
            hint={`${Number(ex?.at_risk_pct ?? 0)}% of stock`}
          />
          <Tile
            icon={Landmark}
            label="Suggested provision"
            value={money(Number(ex?.suggested_provision ?? 0))}
            hint="what to set aside against it"
            tone="warning"
          />
        </div>
        <VizRoot>
          <ChartFrame
            title="Stock at risk, by how long it has left"
            subtitle="Banded because the action differs: sell it through, move it, or write it off."
          >
            <BarChart
              data={(ex?.bands ?? [])
                .filter((b) => Number(b.cost_value) > 0)
                .map((b) => ({
                  label: b.label,
                  value: Number(b.cost_value),
                  note: `${b.quantity.toLocaleString()} units · ${Math.round(
                    Number(b.provision_rate) * 100,
                  )}% provision`,
                }))}
              valueFormat={money}
              ordinalRamp
            />
          </ChartFrame>
        </VizRoot>
      </section>

      {/* --- FX ----------------------------------------------------------- */}
      <section>
        <h2 className="mb-2 text-base font-semibold tracking-tight text-ink-900">
          Foreign currency held
        </h2>
        {fx.data && Object.keys(fx.data.by_currency).length === 0 ? (
          <NotComputable reason={fx.data.interpretation} />
        ) : (
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Tile
              icon={Coins}
              label="Unrealised gain / loss"
              value={money(Number(fx.data?.net_unrealised ?? 0))}
              tone={Number(fx.data?.net_unrealised ?? 0) < 0 ? "danger" : "good"}
              hint="if everything settled at today's rate"
            />
            {Object.entries(fx.data?.by_currency ?? {}).map(([code, amount]) => (
              <Tile key={code} icon={Landmark} label={code} value={money(Number(amount))} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
