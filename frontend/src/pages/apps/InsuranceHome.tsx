/* -------------------------------------------------------------------------- */
/* Insurance overview — what is owed, and what is about to stop being owed.    */
/*                                                                             */
/* The number that costs money here is not the total outstanding; it is how     */
/* many claims are close to their scheme's submission window. Past it the       */
/* medicine has gone and nobody will pay for it, so that count leads.           */
/* -------------------------------------------------------------------------- */

import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  Building2,
  CheckCircle2,
  FileText,
  Receipt,
  Shield,
  Users,
} from "lucide-react";
import { Link } from "react-router-dom";
import {
  AppHeader,
  QuickAction,
  QuickActions,
  SectionCard,
  SectionGrid,
  StatTile,
  WorkQueue,
} from "../../components/AppHome";
import { useModuleWork } from "../../lib/modulework";
import { money } from "../../lib/format";
import { insuranceOverview } from "../../lib/insurance";
import { useDefaultOrg } from "../../lib/recordData";

export function InsuranceHome() {
  const work = useModuleWork("insurance");
  const { orgId } = useDefaultOrg();

  const overview = useQuery({
    queryKey: ["insurance-overview", orgId],
    enabled: orgId != null,
    queryFn: () => insuranceOverview(orgId as number),
  });

  const claims = overview.data?.claims;
  const recon = overview.data?.reconciliation;
  const exposure = overview.data?.exposure ?? [];

  return (
    <div className="flex flex-col gap-6">
      <AppHeader
        icon={Shield}
        hue="#7C3AED"
        title="Insurance"
        subtitle="Who pays for a medicine when the patient does not pay all of it — eligibility at the counter, claims after it, and what the insurers actually settled."
      />

      <WorkQueue items={work.items} loading={work.loading} />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Link to="/insurance/claims">
          <StatTile
            label="Owed by insurers"
            value={money(claims?.outstanding ?? 0)}
            hint="claimed and not yet settled"
          />
        </Link>
        <Link to="/insurance/claims">
          <StatTile
            label="Window closing"
            value={claims?.closing_within_7_days ?? 0}
            hint="within 7 days"
          />
        </Link>
        <Link to="/insurance/claims">
          <StatTile
            label="Window missed"
            value={claims?.window_missed ?? 0}
            hint={claims?.window_missed ? "unrecoverable" : "nothing missed"}
          />
        </Link>
        <Link to="/insurance/claims">
          <StatTile
            label="Rejected"
            value={claims?.rejected ?? 0}
            hint="need reworking or writing off"
          />
        </Link>
      </div>

      {claims && recon && (
        <div className="rounded-lg border border-line bg-surface-0">
          <div className="border-b border-line px-4 py-3">
            <div className="text-sm font-semibold text-ink-900">Needs your attention</div>
            <div className="text-xs text-ink-500">
              Claims stop being recoverable quietly — these are the ones with a deadline.
            </div>
          </div>
          <ul className="divide-y divide-line px-4">
            <Row
              ok={claims.window_missed === 0}
              label={
                claims.window_missed === 0
                  ? "No claim has missed its window"
                  : `${claims.window_missed} claim(s) past their submission window`
              }
              detail={
                claims.window_missed === 0
                  ? "Everything dispensed is still claimable."
                  : "The scheme will refuse these as late. Reverse them so they stop counting as expected income."
              }
              to="/insurance/claims"
            />
            <Row
              ok={claims.closing_within_7_days === 0}
              label={
                claims.closing_within_7_days === 0
                  ? "Nothing closing this week"
                  : `${claims.closing_within_7_days} claim(s) close within 7 days`
              }
              detail={
                claims.closing_within_7_days === 0
                  ? "No deadline is imminent."
                  : "Submit them before the window shuts — after that the money is gone."
              }
              to="/insurance/claims"
            />
            <Row
              ok={claims.drafts === 0}
              label={
                claims.drafts === 0
                  ? "No unsent drafts"
                  : `${claims.drafts} claim(s) built but never sent`
              }
              detail={
                claims.drafts === 0
                  ? "Every claim raised has been submitted."
                  : "A draft claims nothing — the insurer has not seen it."
              }
              to="/insurance/claims"
            />
            <Row
              ok={recon.short_paid_claims === 0}
              label={
                recon.short_paid_claims === 0
                  ? "No short payments outstanding"
                  : `${money(recon.short_paid_total)} short-paid across ${recon.short_paid_claims} claim(s)`
              }
              detail={
                recon.short_paid_claims === 0
                  ? "Insurers have settled in full where they accepted."
                  : "Accepted but under-paid. A short-pay nobody chases becomes a write-off that never got a decision."
              }
              to="/insurance/remittances"
            />
          </ul>
        </div>
      )}

      {exposure.length > 0 && (
        <div className="rounded-lg border border-line bg-surface-0">
          <div className="border-b border-line px-4 py-3 text-sm font-semibold text-ink-900">
            Owed by each payer, aged
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-line bg-surface-100 text-left text-xs uppercase tracking-wide text-ink-500">
                <tr>
                  <th className="px-4 py-2">Scheme</th>
                  <th className="px-3 py-2">Settlement</th>
                  <th className="px-3 py-2 text-right">Current</th>
                  <th className="px-3 py-2 text-right">31–60</th>
                  <th className="px-3 py-2 text-right">61–90</th>
                  <th className="px-3 py-2 text-right">90+</th>
                  <th className="px-4 py-2 text-right">Outstanding</th>
                </tr>
              </thead>
              <tbody>
                {exposure.map((e) => (
                  <tr key={e.scheme} className="border-b border-line last:border-0">
                    <td className="px-4 py-2 text-ink-900">{e.scheme_name}</td>
                    <td className="px-3 py-2 text-xs text-ink-500">
                      {e.settlement === "CAPITATION" ? "Capitation" : "Fee for service"}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">{money(e.current)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{money(e.d30)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{money(e.d60)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-danger-700">
                      {money(Number(e.d90) + Number(e.over90))}
                    </td>
                    <td className="px-4 py-2 text-right font-medium tabular-nums">
                      {money(e.outstanding)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <QuickActions>
        <QuickAction to="/insurance/claims" icon={FileText} label="Work the claims queue" primary />
        <QuickAction to="/insurance/schemes" icon={Building2} label="Schemes & formulary" />
        <QuickAction to="/insurance/remittances" icon={Receipt} label="Reconcile a remittance" />
      </QuickActions>

      <div>
        <h2 className="mb-3 text-base font-semibold tracking-tight text-ink-900">
          Everything in insurance
        </h2>
        <SectionGrid>
          <SectionCard
            icon={FileText}
            title="Claims"
            description="Build, submit, adjudicate and reverse — ranked by how long is left to claim."
            to="/insurance/claims"
            meta={claims?.submitted}
          />
          <SectionCard
            icon={Building2}
            title="Schemes & formulary"
            description="Who pays, at what co-payment, and which medicines they actually cover."
            to="/insurance/schemes"
          />
          <SectionCard
            icon={Users}
            title="Member policies"
            description="Cards presented at the counter, their validity and their own co-payment rate."
            to="/insurance/members"
          />
          <SectionCard
            icon={Receipt}
            title="Remittances"
            description="What each insurer says it paid, matched against what was claimed."
            to="/insurance/remittances"
            meta={recon?.advices_awaiting}
          />
        </SectionGrid>
      </div>
    </div>
  );
}

function Row({
  ok,
  label,
  detail,
  to,
}: {
  ok: boolean;
  label: string;
  detail: string;
  to: string;
}) {
  return (
    <li className="flex items-start gap-2.5 py-2">
      <span className="mt-0.5">
        {ok ? (
          <CheckCircle2 className="h-4 w-4 text-success-600" />
        ) : (
          <AlertTriangle className="h-4 w-4 text-warning-600" />
        )}
      </span>
      <div className="min-w-0 flex-1">
        <div className="text-sm text-ink-900">{label}</div>
        <div className="text-xs text-ink-500">{detail}</div>
      </div>
      {!ok && (
        <Link to={to} className="shrink-0 text-xs text-brand-600 hover:underline">
          Open
        </Link>
      )}
    </li>
  );
}
