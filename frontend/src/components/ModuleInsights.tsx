/* -------------------------------------------------------------------------- */
/* The figures on a module home.                                               */
/*                                                                             */
/* Module homes used to end in a grid of cards that were really the menu again, */
/* one click deeper. The menu already lists the screens; what a home should say */
/* is how this part of the business is doing. This renders that: counts, a      */
/* trend where time matters, donuts for composition, bars for ranking.          */
/*                                                                             */
/* Every figure comes from /api/workspace/module-insights/, which aggregates    */
/* real rows under the same permission gate as the work queue — so nobody is    */
/* shown a chart about work they cannot see, and an empty module says it is     */
/* empty rather than drawing a convincing placeholder.                          */
/* -------------------------------------------------------------------------- */

import { BarChart, ChartFrame, Donut, LineTrend, VizRoot } from "./Charts";
import { StatTile } from "./AppHome";
import { useModuleInsights } from "../lib/moduleinsights";

const money = (n: number) =>
  `RWF ${Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
const count = (n: number) => Number(n).toLocaleString();

/** A day label like "2026-08-09" shown as "9 Aug". */
function shortDay(iso: string) {
  const d = new Date(`${iso}T00:00:00`);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

function Skeleton() {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            className="h-20 animate-pulse rounded-lg border border-line bg-surface-100"
          />
        ))}
      </div>
      <div className="h-64 animate-pulse rounded-lg border border-line bg-surface-100" />
    </div>
  );
}

export function ModuleInsights({
  module,
  /** What the trend line is measuring. Only retail ships one today. */
  trendTitle = "Last 14 days",
  trendSubtitle,
}: {
  module: string;
  trendTitle?: string;
  trendSubtitle?: string;
}) {
  const { insights, loading } = useModuleInsights(module);
  const { tiles, donuts, bars, trend, trend_series: series } = insights;

  if (loading) return <Skeleton />;

  // A pie of one slice says "100% of the only thing there is", which is not a
  // finding. Those are dropped rather than drawn as a full ring.
  const shown = donuts.filter((d) => d.slices.length >= 2);

  const hasAnything = tiles.length > 0 || shown.length > 0 || bars.length > 0 || trend.length > 0;

  if (!hasAnything) {
    return (
      <div className="rounded-lg border border-line bg-surface-0 px-4 py-6 text-center text-sm text-ink-500">
        Nothing has been recorded here yet. The figures appear as soon as there is work to measure.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {tiles.length > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {tiles.map((t) => (
            <StatTile
              key={t.label}
              label={t.label}
              value={t.money ? money(t.value) : count(t.value)}
              hint={t.hint}
            />
          ))}
        </div>
      )}

      <VizRoot>
        <div className="space-y-3">
          {trend.length > 0 && (
            <ChartFrame title={trendTitle} subtitle={trendSubtitle}>
              <LineTrend
                points={trend.map((p) => ({ label: shortDay(p.label), values: p.values }))}
                seriesNames={series.length > 0 ? series : [trendTitle]}
                valueFormat={money}
              />
            </ChartFrame>
          )}

          {/* Two composition charts sit side by side on a wide screen and stack on
              a narrow one — a donut squeezed into a third of the width stops being
              readable well before the labels collide. */}
          {shown.length > 0 && (
            <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
              {shown.map((d) => (
                <ChartFrame key={d.title} title={d.title} subtitle={d.subtitle}>
                  <Donut
                    slices={d.slices}
                    valueFormat={d.money ? money : count}
                    centreLabel={d.money ? "total" : "in total"}
                    centreValue={
                      d.sums === false
                        ? undefined
                        : d.money
                          ? money(d.slices.reduce((s, x) => s + x.value, 0))
                          : count(d.slices.reduce((s, x) => s + x.value, 0))
                    }
                  />
                </ChartFrame>
              ))}
            </div>
          )}

          {bars
            .filter((b) => b.data.length > 0)
            .map((b) => (
              <ChartFrame key={b.title} title={b.title} subtitle={b.subtitle}>
                <BarChart data={b.data} valueFormat={b.money ? money : count} />
              </ChartFrame>
            ))}
        </div>
      </VizRoot>
    </div>
  );
}
