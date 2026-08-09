import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Building2, TrendingDown, TrendingUp } from "lucide-react";
import { useState } from "react";
import {
  BarChart,
  ChartFrame,
  Donut,
  EmptyChart,
  Meter,
  VizRoot,
  Waterfall,
  type BarDatum,
} from "../components/Charts";
import { DataGrid } from "../components/DataGrid";
import { Section } from "../components/RecordKit";
import { Badge, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import type { BranchComparison, BranchRow, PharmacyCockpit } from "../lib/finance";
import { amount, money, num, pct } from "../lib/format";

function monthBounds() {
  const now = new Date();
  return {
    start: new Date(now.getFullYear(), now.getMonth(), 1).toISOString().slice(0, 10),
    end: new Date(now.getFullYear(), now.getMonth() + 1, 0).toISOString().slice(0, 10),
  };
}

const PRESETS: [string, () => { start: string; end: string }][] = [
  ["This month", monthBounds],
  [
    "Last month",
    () => {
      const n = new Date();
      return {
        start: new Date(n.getFullYear(), n.getMonth() - 1, 1).toISOString().slice(0, 10),
        end: new Date(n.getFullYear(), n.getMonth(), 0).toISOString().slice(0, 10),
      };
    },
  ],
  [
    "Year to date",
    () => ({
      start: new Date(new Date().getFullYear(), 0, 1).toISOString().slice(0, 10),
      end: new Date().toISOString().slice(0, 10),
    }),
  ],
];

/* -------------------------------------------------------------------------- */

function Kpi({
  label,
  value,
  hint,
  deltaPct,
  invertDelta = false,
}: {
  label: string;
  value: string;
  hint?: string;
  deltaPct?: number | null;
  invertDelta?: boolean;
}) {
  const has = deltaPct !== undefined && deltaPct !== null;
  const up = (deltaPct ?? 0) >= 0;
  const good = invertDelta ? !up : up;
  const Arrow = up ? TrendingUp : TrendingDown;
  return (
    <div className="rounded-lg border border-line bg-surface-0 px-4 py-3">
      <div className="text-[11px] font-medium text-ink-500">{label}</div>
      <div className="mt-0.5 text-2xl font-semibold tabular-nums text-ink-900">{value}</div>
      {has && (
        <div
          className={`mt-0.5 flex items-center gap-1 text-xs font-medium ${
            good ? "text-green-700" : "text-red-700"
          }`}
        >
          <Arrow className="h-3 w-3" aria-hidden />
          <span className="tabular-nums">
            {up ? "+" : ""}
            {(deltaPct ?? 0).toFixed(1)}%
          </span>
          <span className="font-normal text-ink-500">vs previous period</span>
        </div>
      )}
      {hint && <div className="text-xs text-ink-500">{hint}</div>}
    </div>
  );
}

/* -------------------------------------------------------------------------- */

export function FinanceCockpitPage() {
  const [range, setRange] = useState(monthBounds);
  const [preset, setPreset] = useState("This month");
  const qs = `start=${range.start}&end=${range.end}`;

  const cockpit = useQuery({
    queryKey: ["pharmacy-cockpit", range.start, range.end],
    queryFn: () => api<PharmacyCockpit>(`/api/finance/reports/pharmacy-cockpit/?${qs}`),
  });
  const branches = useQuery({
    queryKey: ["branch-comparison", range.start, range.end],
    queryFn: () => api<BranchComparison>(`/api/finance/reports/branch-comparison/?${qs}`),
  });

  const c = cockpit.data;
  const p = c?.performance;
  const bs = c?.balance_sheet;
  const wc = c?.working_capital;
  const ex = c?.expiry_exposure;
  const be = c?.break_even;
  const rt = c?.returns;

  // Where revenue ends up: cost of sales, operating cost, and what is left.
  // The donut folds anything past five slices into "Other" itself.
  const cogsAndOpex = p
    ? [
        { label: "Cost of sales", value: num(p.cogs) },
        { label: "Operating expenses", value: num(p.operating_expenses) },
      ]
    : [];

  const channelBars: BarDatum[] = (c?.margin_by_channel.rows ?? []).map((r) => ({
    label: r.channel,
    value: num(r.gross_margin_pct ?? 0),
    note: `${money(r.revenue)} revenue · ${money(r.gross_margin ?? 0)} margin · ${r.units ?? 0} units`,
  }));

  const expiryBars: BarDatum[] = (ex?.bands ?? [])
    .filter((b) => num(b.cost_value) > 0)
    .map((b) => ({
      label: b.label,
      value: num(b.cost_value),
      note: `${b.quantity} units · provision ${money(b.provision)} at ${pct(num(b.provision_rate) * 100, 0)}`,
      tone:
        b.band === "expired"
          ? ("critical" as const)
          : b.band === "0_30"
            ? ("serious" as const)
            : b.band === "31_60"
              ? ("warning" as const)
              : undefined,
    }));

  const branchBars: BarDatum[] = (branches.data?.rows ?? []).map((b) => ({
    label: b.organization,
    value: num(b.revenue),
    note: `${pct(num(b.gross_margin_pct))} gross margin · net ${money(b.net_profit)}`,
  }));

  return (
    <VizRoot>
      <PageHeader
        title="Finance cockpit"
        action={
          <div className="flex gap-1 rounded-md border border-line bg-surface-0 p-0.5">
            {PRESETS.map(([label, fn]) => (
              <button
                key={label}
                onClick={() => {
                  setPreset(label);
                  setRange(fn());
                }}
                className={`rounded px-2.5 py-1 text-xs font-medium ${
                  preset === label
                    ? "bg-brand-50 text-brand-700"
                    : "text-ink-600 hover:bg-surface-100"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        }
      />

      {cockpit.isLoading && <EmptyChart message="Loading the ledger…" />}

      {c && p && bs && wc && ex && be && rt && (
        <div className="flex flex-col gap-5">
          {/* Headline KPIs */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <Kpi label="Revenue" value={money(p.revenue)} deltaPct={p.delta_pct.revenue} />
            <Kpi
              label="Gross margin"
              value={pct(p.gross_margin_pct)}
              deltaPct={p.delta_pct.gross_profit}
              hint={money(p.gross_profit)}
            />
            <Kpi label="Net profit" value={money(p.net_profit)} deltaPct={p.delta_pct.net_profit} />
            <Kpi
              label="EBITDA"
              value={money(p.ebitda)}
              hint="before interest, tax & depreciation"
            />
            <Kpi
              label="Cash cycle"
              value={wc.computable ? `${num(wc.cash_conversion_cycle_days).toFixed(0)} d` : "—"}
              hint={wc.computable ? "DIO + DSO − DPO" : "not enough trading to measure"}
              invertDelta
            />
            <Kpi
              label="Cash on hand"
              value={money(p.cash_on_hand)}
              hint={`${money(p.inventory_value)} in stock`}
            />
          </div>

          {/* The one thing that most often kills a pharmacy. */}
          {num(ex.at_risk_value) > 0 && (
            <div className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <div>
                <strong>{money(ex.at_risk_value)}</strong> of stock ({pct(ex.at_risk_pct)} of the
                shelf) expires within six months. IAS 2 carries inventory at the lower of cost and
                net realisable value, so a provision of{" "}
                <strong>{money(ex.suggested_provision)}</strong> is implied today — discount,
                transfer between branches or return it while it still has value.
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <ChartFrame title="Where the money goes">
              <Donut
                slices={[
                  ...cogsAndOpex,
                  {
                    label: "Depreciation",
                    value:
                      num(p.ebitda) - num(p.net_profit) > 0
                        ? num(c.performance.ebitda) - num(p.net_profit)
                        : 0,
                  },
                  { label: "Net profit", value: Math.max(0, num(p.net_profit)) },
                ].filter((s) => s.value > 0)}
                centreLabel="revenue"
                centreValue={money(p.revenue).replace("RWF ", "")}
                valueFormat={(n) => amount(n)}
              />
            </ChartFrame>

            <ChartFrame title="Cash conversion cycle">
              {wc.computable ? (
                <Waterfall
                  steps={[
                    { label: "Stock held", value: num(wc.dio_days) },
                    { label: "Customers owe", value: num(wc.dso_days) },
                    { label: "Suppliers fund", value: -num(wc.dpo_days) },
                    { label: "Cycle", value: num(wc.cash_conversion_cycle_days), isTotal: true },
                  ]}
                />
              ) : (
                <EmptyChart message="Not enough trading in this period to measure the cycle." />
              )}
              <p className="mt-2 text-xs text-ink-600">{wc.interpretation}</p>
            </ChartFrame>

            <ChartFrame title="Gross margin by channel">
              {channelBars.length ? (
                <BarChart data={channelBars} valueFormat={(n) => `${n.toFixed(1)}%`} />
              ) : (
                <EmptyChart message="No costed sales in this period." />
              )}
            </ChartFrame>

            <ChartFrame title="Expiry exposure">
              {expiryBars.length ? (
                <BarChart data={expiryBars} valueFormat={(n) => amount(n)} />
              ) : (
                <EmptyChart message="Nothing expiring within six months." />
              )}
            </ChartFrame>
          </div>

          {/* Returns + liquidity + break-even */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <Section title="Return on capital" hint="Annualised, so a month compares to a year.">
              <div className="flex flex-col gap-3 rounded-lg border border-line p-4">
                {[
                  ["Return on equity", rt.roe_pct, "the owner's own return"],
                  ["Return on assets", rt.roa_pct, "how hard every asset works"],
                  ["Return on capital employed", rt.roce_pct, "before financing distorts it"],
                ].map(([label, value, hint]) => (
                  <div key={String(label)} className="flex items-baseline justify-between">
                    <div>
                      <div className="text-sm text-ink-700">{label}</div>
                      <div className="text-[11px] text-ink-500">{hint}</div>
                    </div>
                    <div className="tabular-nums text-lg font-semibold text-ink-900">
                      {value === null ? "—" : pct(value as string)}
                    </div>
                  </div>
                ))}
                <div className="border-t border-line pt-3">
                  <Meter
                    value={num(rt.gmroi)}
                    target={1}
                    label="GMROI — margin per franc of stock"
                    caption={rt.gmroi_verdict ?? undefined}
                    format={(n) => n.toFixed(2)}
                  />
                </div>
              </div>
            </Section>

            <Section title="Liquidity" hint="Quick ratio excludes stock — the honest read.">
              <div className="flex flex-col gap-4 rounded-lg border border-line p-4">
                <Meter
                  value={num(bs.current_ratio ?? 0)}
                  target={2}
                  label="Current ratio"
                  caption="Target 2.0 — current assets over current liabilities."
                  format={(n) => n.toFixed(2)}
                />
                <Meter
                  value={num(bs.quick_ratio ?? 0)}
                  target={1}
                  label="Quick ratio (acid test)"
                  caption="Target 1.0 — can the business pay suppliers without selling stock?"
                  format={(n) => n.toFixed(2)}
                />
                <div className="flex items-baseline justify-between border-t border-line pt-3">
                  <span className="text-sm text-ink-700">Working capital</span>
                  <span className="tabular-nums font-semibold text-ink-900">
                    {money(bs.working_capital)}
                  </span>
                </div>
              </div>
            </Section>

            <Section
              title="Break-even"
              hint="Fixed costs treated as fixed, stock cost as variable."
            >
              <div className="flex flex-col gap-3 rounded-lg border border-line p-4">
                <div className="flex items-baseline justify-between">
                  <span className="text-sm text-ink-700">Revenue needed</span>
                  <span className="tabular-nums font-semibold text-ink-900">
                    {be.break_even_revenue ? money(be.break_even_revenue) : "—"}
                  </span>
                </div>
                <div className="flex items-baseline justify-between">
                  <span className="text-sm text-ink-700">Per trading day</span>
                  <span className="tabular-nums text-ink-900">
                    {be.break_even_revenue_per_day ? money(be.break_even_revenue_per_day) : "—"}
                  </span>
                </div>
                <div className="flex items-baseline justify-between">
                  <span className="text-sm text-ink-700">Fixed costs</span>
                  <span className="tabular-nums text-ink-900">{money(be.fixed_costs)}</span>
                </div>
                <div className="border-t border-line pt-3">
                  {be.margin_of_safety_pct === null ? (
                    <Badge tone="neutral">No contribution margin to model</Badge>
                  ) : be.is_above_break_even ? (
                    <Badge tone="success">{pct(be.margin_of_safety_pct)} margin of safety</Badge>
                  ) : (
                    <Badge tone="danger">Below break-even for this period</Badge>
                  )}
                </div>
              </div>
            </Section>
          </div>

          {/* Retail vs wholesale — the two businesses under one roof. */}
          {c.retail_vs_wholesale.rows.some((r) => num(r.revenue) > 0) && (
            <ChartFrame
              title="Retail vs wholesale"
              legend={[
                { label: "Retail (counter)", color: "var(--viz-s1)" },
                { label: "Wholesale (B2B)", color: "var(--viz-s2)" },
              ]}
            >
              <div
                className="flex h-6 overflow-hidden rounded-md"
                role="img"
                aria-label="Revenue mix"
              >
                {c.retail_vs_wholesale.rows.map((r, i) => (
                  <div
                    key={r.channel}
                    style={{
                      width: `${Math.max(0, num(r.share_pct ?? 0))}%`,
                      background: `var(--viz-s${i + 1})`,
                      marginRight: i === 0 ? 2 : 0,
                    }}
                    title={`${r.channel}: ${money(r.revenue)}`}
                  />
                ))}
              </div>
              <ul className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
                {c.retail_vs_wholesale.rows.map((r) => (
                  <li
                    key={r.channel}
                    className="flex items-baseline justify-between rounded-md border border-line px-3 py-2 text-sm"
                  >
                    <span className="text-ink-700">{r.channel}</span>
                    <span className="tabular-nums">
                      <span className="font-semibold text-ink-900">{money(r.revenue)}</span>
                      <span className="ml-2 text-xs text-ink-500">
                        {pct(r.share_pct ?? 0)}
                        {r.gross_margin_pct !== undefined && ` · ${pct(r.gross_margin_pct)} margin`}
                      </span>
                    </span>
                  </li>
                ))}
              </ul>
            </ChartFrame>
          )}
        </div>
      )}

      {/* HQ: every branch side by side. */}
      {(branches.data?.rows.length ?? 0) > 1 && (
        <div className="mt-6 flex flex-col gap-4">
          <ChartFrame
            title="Revenue by branch"
            action={
              <span className="text-xs text-ink-500">
                Group net {money(branches.data!.group_net_profit)}
              </span>
            }
          >
            <BarChart data={branchBars} valueFormat={(n) => amount(n)} />
          </ChartFrame>

          <Section title="Branch comparison" hint="Which branch is quietly carrying dead stock.">
            <DataGrid<BranchRow>
              rows={branches.data!.rows}
              getRowId={(b) => b.organization_id}
              storageKey="finance-branches"
              exportName="branch-comparison"
              searchPlaceholder="Search branches…"
              emptyMessage="No branches visible."
              initialDensity="compact"
              columns={[
                {
                  key: "organization",
                  header: "Branch",
                  render: (b) => (
                    <div className="flex items-center gap-1.5">
                      <Building2 className="h-3.5 w-3.5 text-ink-400" />
                      <span className="font-medium text-ink-900">{b.organization}</span>
                      <Badge tone="neutral">{b.type}</Badge>
                    </div>
                  ),
                },
                {
                  key: "revenue",
                  header: "Revenue",
                  align: "right",
                  numeric: true,
                  value: (b) => num(b.revenue),
                  render: (b) => money(b.revenue),
                },
                {
                  key: "revenue_share_pct",
                  header: "Share",
                  align: "right",
                  numeric: true,
                  value: (b) => num(b.revenue_share_pct),
                  render: (b) => pct(b.revenue_share_pct),
                },
                {
                  key: "gross_margin_pct",
                  header: "Gross margin",
                  align: "right",
                  numeric: true,
                  value: (b) => num(b.gross_margin_pct),
                  render: (b) => pct(b.gross_margin_pct),
                },
                {
                  key: "net_profit",
                  header: "Net profit",
                  align: "right",
                  numeric: true,
                  value: (b) => num(b.net_profit),
                  render: (b) => (
                    <span className={num(b.net_profit) < 0 ? "text-red-700" : ""}>
                      {money(b.net_profit)}
                    </span>
                  ),
                },
                {
                  key: "inventory_value",
                  header: "Stock",
                  align: "right",
                  numeric: true,
                  value: (b) => num(b.inventory_value),
                  render: (b) => money(b.inventory_value),
                },
                {
                  key: "expiry_at_risk_pct",
                  header: "Expiry risk",
                  align: "right",
                  numeric: true,
                  value: (b) => num(b.expiry_at_risk_pct),
                  render: (b) => {
                    const v = num(b.expiry_at_risk_pct);
                    return v === 0 ? (
                      <span className="text-ink-400">—</span>
                    ) : (
                      <Badge tone={v > 10 ? "danger" : v > 5 ? "warning" : "neutral"}>
                        {pct(v)}
                      </Badge>
                    );
                  },
                },
                {
                  key: "cash_conversion_cycle_days",
                  header: "Cash cycle",
                  align: "right",
                  numeric: true,
                  value: (b) => num(b.cash_conversion_cycle_days),
                  render: (b) =>
                    b.cash_conversion_cycle_days === null ? (
                      <span className="text-ink-400">—</span>
                    ) : (
                      `${num(b.cash_conversion_cycle_days).toFixed(0)} d`
                    ),
                },
                {
                  key: "quick_ratio",
                  header: "Quick ratio",
                  align: "right",
                  numeric: true,
                  value: (b) => num(b.quick_ratio ?? 0),
                  render: (b) => {
                    const v = num(b.quick_ratio ?? 0);
                    return b.quick_ratio === null ? (
                      <span className="text-ink-400">—</span>
                    ) : (
                      <Badge tone={v >= 1 ? "success" : v >= 0.7 ? "warning" : "danger"}>
                        {v.toFixed(2)}
                      </Badge>
                    );
                  },
                },
              ]}
            />
          </Section>
        </div>
      )}
    </VizRoot>
  );
}
