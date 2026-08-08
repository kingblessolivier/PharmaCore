/* -------------------------------------------------------------------------- */
/* The home screen: what needs doing, then how the business is going.          */
/*                                                                             */
/* This was eight flat tiles of today's numbers. Three things were missing and  */
/* each defeated the purpose: no time dimension (so "sales today" could not be  */
/* judged), no per-branch split (a group owner with four pharmacies got one     */
/* summed number), and no margin — which for a pharmacy is the number that      */
/* decides whether the business works, because revenue is largely set by what   */
/* the insurer reimburses.                                                      */
/*                                                                             */
/* Work comes first and numbers second, deliberately. Most people signing in    */
/* have a job to finish, not a report to read; the bosses who want the report   */
/* have an empty work queue and see the charts immediately.                     */
/* -------------------------------------------------------------------------- */

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowRight, Clock, ShieldCheck, Users } from "lucide-react";
import { Link } from "react-router-dom";
import { BarChart, ChartFrame, LineTrend, VizRoot } from "../components/Charts";
import { Badge, Card, PageHeader, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { money, shortDate } from "../lib/format";
import type { DashboardSummary, MyWork, WorkItem } from "../lib/types";

function Tile({
  label,
  value,
  hint,
  tone,
  to,
}: {
  label: string;
  value: string | number;
  hint?: string;
  tone?: "danger" | "warning" | "good";
  to?: string;
}) {
  const colour =
    tone === "danger"
      ? "text-danger-700"
      : tone === "warning"
        ? "text-warning-700"
        : tone === "good"
          ? "text-success-700"
          : "text-ink-900";
  const inner = (
    <Card className="h-full p-4 transition-colors hover:border-brand-300">
      <div className="text-xs text-ink-500">{label}</div>
      <div className={`mt-1 text-2xl font-semibold tabular-nums ${colour}`}>{value}</div>
      {hint && <div className="mt-0.5 text-xs text-ink-500">{hint}</div>}
    </Card>
  );
  return to ? <Link to={to}>{inner}</Link> : inner;
}

function WorkRow({ item, action }: { item: WorkItem; action?: string }) {
  return (
    <li className="flex items-start justify-between gap-3 border-b border-line py-2.5 last:border-0">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-ink-900">{item.label}</span>
          {item.sla_breached && <Badge tone="danger">overdue</Badge>}
        </div>
        <div className="mt-0.5 text-xs text-ink-500">
          {item.requested_by} · {item.organization_name}
          {item.amount != null && <> · {money(item.amount)}</>}
        </div>
        {item.reason && <div className="mt-0.5 truncate text-xs text-ink-600">{item.reason}</div>}
        {item.why && (
          <div className="mt-1 text-xs text-warning-700">
            {item.why}
            {item.escalate_to && item.escalate_to.length > 0 && (
              <> Goes to {item.escalate_to.join(" or ")}.</>
            )}
          </div>
        )}
        {item.with && item.with.length > 0 && (
          <div className="mt-1 text-xs text-ink-500">With {item.with.join(" or ")}.</div>
        )}
      </div>
      {action && (
        <Link
          to="/approvals"
          className="shrink-0 whitespace-nowrap text-xs font-medium text-brand-700 hover:underline"
        >
          {action} <ArrowRight className="inline h-3 w-3" />
        </Link>
      )}
    </li>
  );
}

function WorkPanel({ work }: { work: MyWork }) {
  const { waiting_on_me, needs_escalation, raised_by_me, my_team, next_steps } = work;
  const nothing =
    waiting_on_me.length === 0 &&
    needs_escalation.length === 0 &&
    raised_by_me.length === 0 &&
    next_steps.length === 0 &&
    my_team.breaching.length === 0;

  if (nothing) return null;

  return (
    <div className="grid gap-3 lg:grid-cols-2">
      {(waiting_on_me.length > 0 || next_steps.length > 0) && (
        <Card className="p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-ink-900">
            <ShieldCheck className="h-4 w-4 text-brand-600" /> Waiting on you
          </div>
          {next_steps.length > 0 && (
            <ul className="mt-2 space-y-1.5">
              {next_steps.map((step) => (
                <li key={step.to}>
                  <Link
                    to={step.to}
                    className={`flex items-center justify-between rounded-md border px-3 py-2 text-sm hover:bg-surface-100 ${
                      step.tone === "danger"
                        ? "border-danger-200 bg-danger-50 text-danger-900"
                        : "border-line text-ink-800"
                    }`}
                  >
                    {step.label}
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </li>
              ))}
            </ul>
          )}
          {waiting_on_me.length > 0 && (
            <ul className="mt-2">
              {waiting_on_me.slice(0, 6).map((item) => (
                <WorkRow key={item.id} item={item} action="Decide" />
              ))}
            </ul>
          )}
        </Card>
      )}

      {needs_escalation.length > 0 && (
        <Card className="p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-ink-900">
            <Clock className="h-4 w-4 text-warning-600" /> Not yours to decide
          </div>
          <p className="mt-1 text-xs text-ink-500">
            Visible to you, above your authority. Named here so they do not sit in a shared
            queue while everyone assumes someone else is handling them.
          </p>
          <ul className="mt-2">
            {needs_escalation.slice(0, 5).map((item) => (
              <WorkRow key={item.id} item={item} />
            ))}
          </ul>
        </Card>
      )}

      {my_team.size > 0 && (
        <Card className="p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-ink-900">
            <Users className="h-4 w-4 text-brand-600" /> Your team ({my_team.size})
          </div>
          {my_team.breaching.length > 0 && (
            <div className="mt-2 flex items-start gap-2 rounded-md border border-danger-200 bg-danger-50 p-2.5 text-xs text-danger-900">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>
                {my_team.breaching.length} request
                {my_team.breaching.length > 1 ? "s" : ""} from your team has passed its
                agreed response time.
              </span>
            </div>
          )}
          {my_team.open_requests.length > 0 ? (
            <ul className="mt-2">
              {my_team.open_requests.slice(0, 5).map((item) => (
                <WorkRow key={item.id} item={item} />
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-ink-500">Nothing outstanding from your team.</p>
          )}
        </Card>
      )}

      {raised_by_me.length > 0 && (
        <Card className="p-4">
          <div className="text-sm font-semibold text-ink-900">Raised by you</div>
          <ul className="mt-2">
            {raised_by_me.slice(0, 5).map((item) => (
              <WorkRow key={item.id} item={item} />
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}

const BAND_LABELS: Record<string, string> = {
  expired: "Already expired",
  within_30: "Within 30 days",
  within_60: "31–60 days",
  within_90: "61–90 days",
};

export function DashboardPage() {
  const { user } = useAuth();
  const summary = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api<DashboardSummary>("/api/dashboard/"),
  });
  const work = useQuery({
    queryKey: ["my-work"],
    queryFn: () => api<MyWork>("/api/workspace/my-work/"),
  });

  if (summary.isLoading) return <Spinner />;
  const d = summary.data;
  if (!d) return null;

  const branches = d.by_branch ?? [];
  const trend = (d.trend ?? []).map((point) => ({
    label: shortDate(point.date),
    values: [point.revenue],
  }));
  const bands = (d.expiry_exposure?.bands ?? []).filter((b) => b.value > 0);

  // Yesterday is the honest comparison, and it is stated as an amount rather
  // than a percentage: a jump from RWF 2,000 to RWF 6,000 is "+200%" and means
  // nothing on a quiet day.
  const yesterday = d.compared?.yesterday ?? 0;
  const diff = (d.today?.revenue ?? 0) - yesterday;

  return (
    <div className="space-y-5">
      <div>
        <PageHeader title={`Good day${user?.first_name ? `, ${user.first_name}` : ""}`} />
        <p className="-mt-2 text-sm text-ink-500">
          {d.org_count > 1
            ? `${d.org_count} organizations · today, with the last 14 days for context`
            : "Today, with the last 14 days for context"}
        </p>
      </div>

      {work.data && <WorkPanel work={work.data} />}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Tile
          label="Revenue today"
          value={money(d.today?.revenue ?? 0)}
          hint={
            yesterday > 0
              ? `${diff >= 0 ? "+" : ""}${money(diff)} against yesterday`
              : "no trading yesterday"
          }
          tone={diff >= 0 ? "good" : "warning"}
        />
        <Tile
          label="Gross margin today"
          value={money(d.today?.margin ?? 0)}
          hint={`${d.today?.margin_pct ?? 0}% of revenue`}
          tone={(d.today?.margin_pct ?? 0) < 15 ? "warning" : "good"}
        />
        <Tile
          label="Owed to us"
          value={money(d.receivable_due)}
          to="/finance/aging"
          hint="customer invoices outstanding"
        />
        <Tile
          label="Stock at risk"
          value={money(d.expiry_exposure?.total_at_risk ?? 0)}
          to="/catalog/expiry"
          hint="expiring within 90 days"
          tone={(d.expiry_exposure?.total_at_risk ?? 0) > 0 ? "warning" : undefined}
        />
      </div>

      <VizRoot>
        <div className="grid gap-3 lg:grid-cols-2">
          <ChartFrame
            title="Revenue, last 14 days"
            subtitle="A single day's takings cannot be judged on its own."
          >
            <LineTrend points={trend} seriesNames={["Revenue"]} valueFormat={money} />
          </ChartFrame>

          {branches.length > 1 ? (
            <ChartFrame
              title="Today by branch"
              subtitle="Which pharmacy earned it — the question a group total cannot answer."
            >
              <BarChart
                data={branches.map((b) => ({
                  label: b.name,
                  value: b.revenue,
                  secondary: `${b.margin_pct}% margin · ${b.sales} sales`,
                }))}
                valueFormat={money}
              />
            </ChartFrame>
          ) : (
            <ChartFrame
              title="Stock at risk by expiry band"
              subtitle="Banded because the action differs: sell through, move, or write off."
            >
              <BarChart
                data={bands.map((b) => ({
                  label: BAND_LABELS[b.band] ?? b.band,
                  value: b.value,
                  secondary: `${b.units.toLocaleString()} units`,
                }))}
                valueFormat={money}
                ordinalRamp
              />
            </ChartFrame>
          )}
        </div>
      </VizRoot>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Tile
          label="Low stock lines"
          value={d.low_stock.count}
          to="/catalog/low-stock"
          tone={d.low_stock.count > 0 ? "warning" : undefined}
        />
        <Tile
          label="Expired on the shelf"
          value={d.expired.count}
          hint={`${d.expired.units.toLocaleString()} units`}
          to="/catalog/expiry"
          tone={d.expired.count > 0 ? "danger" : undefined}
        />
        <Tile label="Units in transit" value={d.in_transit_units.toLocaleString()} to="/distribution/in-transit" />
        <Tile
          label="Licences expiring"
          value={d.licences_expiring}
          hint="within 60 days"
          tone={d.licences_expiring > 0 ? "warning" : undefined}
        />
      </div>

      {d.low_stock.items.length > 0 && (
        <Card className="p-4">
          <div className="text-sm font-semibold text-ink-900">Running low</div>
          <ul className="mt-2 divide-y divide-line">
            {d.low_stock.items.map((item, i) => (
              <li key={i} className="flex items-center justify-between py-2 text-sm">
                <span className="text-ink-800">
                  {item.product}
                  {d.org_count > 1 && <span className="text-ink-500"> · {item.organization}</span>}
                </span>
                <span className="tabular-nums text-ink-600">
                  {item.on_hand} left · min {item.min}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
