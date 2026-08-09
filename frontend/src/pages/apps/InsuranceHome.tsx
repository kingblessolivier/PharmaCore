/* -------------------------------------------------------------------------- */
/* Insurance overview — what is owed, and what is about to stop being owed.    */
/*                                                                             */
/* The number that costs money here is not the total outstanding; it is how     */
/* many claims are close to their scheme's submission window. Past it the       */
/* medicine has gone and nobody will pay for it, so that count leads.           */
/* -------------------------------------------------------------------------- */

import { useQuery } from "@tanstack/react-query";
import { Building2, CalendarX, Clock, FileText, Receipt, Send, Shield } from "lucide-react";
import { Link } from "react-router-dom";
import {
  AppHeader,
  QuickAction,
  QuickActions,
  ReadinessCard,
  ReadinessGrid,
  StatTile,
  WorkQueue,
} from "../../components/AppHome";
import { useModuleWork } from "../../lib/modulework";
import { money } from "../../lib/format";
import { insuranceOverview } from "../../lib/insurance";
import { useDefaultOrg } from "../../lib/recordData";
import { ModuleInsights } from "../../components/ModuleInsights";

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
      <AppHeader icon={Shield} hue="#7C3AED" title="Insurance" />

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
        <ReadinessGrid title="Needs your attention">
          <ReadinessCard
            icon={CalendarX}
            tone={claims.window_missed === 0 ? "ok" : "danger"}
            title={
              claims.window_missed === 0
                ? "No window missed"
                : `${claims.window_missed} past the window`
            }
            detail={
              claims.window_missed === 0 ? "All still claimable." : "The scheme will refuse these."
            }
            to={claims.window_missed === 0 ? undefined : "/insurance/claims"}
          />
          <ReadinessCard
            icon={Clock}
            tone={claims.closing_within_7_days === 0 ? "ok" : "warning"}
            title={
              claims.closing_within_7_days === 0
                ? "Nothing closing"
                : `${claims.closing_within_7_days} close in 7 days`
            }
            detail={
              claims.closing_within_7_days === 0
                ? "No deadline is imminent."
                : "Submit before the window shuts."
            }
            to={claims.closing_within_7_days === 0 ? undefined : "/insurance/claims"}
          />
          <ReadinessCard
            icon={Send}
            tone={claims.drafts === 0 ? "ok" : "warning"}
            title={claims.drafts === 0 ? "No unsent drafts" : `${claims.drafts} never sent`}
            detail={
              claims.drafts === 0 ? "Every claim submitted." : "The insurer has not seen them."
            }
            to={claims.drafts === 0 ? undefined : "/insurance/claims"}
          />
          <ReadinessCard
            icon={Receipt}
            tone={recon.short_paid_claims === 0 ? "ok" : "warning"}
            title={
              recon.short_paid_claims === 0
                ? "Settled in full"
                : `${money(recon.short_paid_total)} short-paid`
            }
            detail={
              recon.short_paid_claims === 0
                ? "Nothing under-paid."
                : `Across ${recon.short_paid_claims} claim(s).`
            }
            to={recon.short_paid_claims === 0 ? undefined : "/insurance/remittances"}
          />
        </ReadinessGrid>
      )}

      {exposure.length > 0 && (
        <div className="rounded-lg border border-line bg-surface-0">
          <div className="border-b border-line px-4 py-3 text-sm font-semibold text-ink-900">
            Owed by each payer, aged
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-line bg-surface-100 text-left text-xs text-ink-500">
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
          How claims are going
        </h2>
        <ModuleInsights module="insurance" />
      </div>
    </div>
  );
}
