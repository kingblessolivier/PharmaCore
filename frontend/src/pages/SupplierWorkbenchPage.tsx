/* -------------------------------------------------------------------------- */
/* One supplier — and, before anything else, whether you may buy from them.    */
/*                                                                             */
/* `can_order` and `qualification_issues` were both already on the payload and  */
/* neither was shown until you were four clicks into a drawer. They answer the  */
/* only question that matters before a buyer starts work: an expired FDA import */
/* licence or a blacklisted standing means the purchase order will be refused,  */
/* and finding that out after building it wastes the afternoon.                 */
/*                                                                             */
/* The four facets already existed as tab components inside a 28rem drawer —    */
/* licences, price agreements, a scorecard and trade terms, in a panel that     */
/* could show one at a time. They are unchanged here; they simply have room.    */
/* -------------------------------------------------------------------------- */

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Ban, CheckCircle2, Handshake, TriangleAlert } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { Empty } from "../components/RecordKit";
import { Badge, Spinner } from "../components/ui";
import {
  Icon,
  Workbench,
  WorkbenchHeader,
  WorkbenchPanel,
  WorkbenchTabs,
} from "../components/Workbench";
import { api } from "../lib/api";
import type { SupplierProfile } from "../lib/procurement";
import { LicencesTab, PerformanceTab, PriceAgreementsTab, TermsTab } from "./SupplierMasterPage";

const STANDING_TONE: Record<string, string> = {
  PREFERRED: "success",
  APPROVED: "success",
  PROBATION: "warning",
  SUSPENDED: "danger",
  BLACKLISTED: "danger",
};

export function SupplierWorkbenchPage() {
  const { id } = useParams<{ id: string }>();

  const profileQuery = useQuery({
    queryKey: ["supplier-profile", id],
    enabled: Boolean(id),
    queryFn: () => api<SupplierProfile>(`/api/procurement/supplier-profiles/${id}/`),
  });

  if (profileQuery.isLoading) return <Spinner />;
  const profile = profileQuery.data;
  if (!profile) return <Empty message="That supplier no longer exists." />;

  const issues = profile.qualification_issues ?? [];
  /* `is_expired` is the model's own reading of the date, not a second opinion
     computed here — the two drifting apart is exactly how a supplier ends up
     orderable on one screen and not on another. */
  const expiredLicences = (profile.licences ?? []).filter((l) => l.is_expired);

  return (
    <div className="flex h-[calc(100vh-5.5rem)] flex-col">
      <div className="mb-2">
        <Link
          to="/procurement/suppliers"
          className="inline-flex items-center gap-1.5 text-form text-ink-600 hover:text-ink-900"
        >
          <Icon as={ArrowLeft} size="sm" /> Supplier qualification
        </Link>
      </div>

      <Workbench>
        <WorkbenchHeader
          icon={Handshake}
          title={profile.trading_name || profile.supplier_name}
          subtitle={[profile.city, profile.country].filter(Boolean).join(", ") || profile.kind}
          status={
            <span className="flex items-center gap-1.5">
              <Badge tone={STANDING_TONE[profile.standing] ?? "neutral"}>
                {profile.standing_display || profile.standing}
              </Badge>
              {profile.can_order ? (
                <span className="inline-flex items-center gap-1 text-form text-success-700">
                  <Icon as={CheckCircle2} size="sm" /> can receive orders
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-form font-semibold text-danger-700">
                  <Icon as={Ban} size="sm" /> cannot receive orders
                </span>
              )}
            </span>
          }
          facts={[
            { label: "Lead time", value: `${profile.supplier_lead_time_days} d` },
            { label: "Payment terms", value: `${profile.payment_terms_days} d` },
            { label: "Licences", value: (profile.licences ?? []).length },
            { label: "Overall score", value: `${Number(profile.overall_score)}%`, emphasis: true },
          ]}
        />

        {/* The reason a purchase order would be refused, before anyone builds
            one. This was reachable only by opening the licences tab and reading
            the dates. */}
        {!profile.can_order && (
          <div className="border-b border-danger-200 bg-danger-50 px-4 py-3">
            <div className="flex items-start gap-2 text-form text-danger-900">
              <Icon as={TriangleAlert} size="sm" className="mt-0.5 text-danger-600" />
              <div>
                <span className="font-semibold">
                  No purchase order can be raised against this supplier.
                </span>
                {issues.length > 0 ? (
                  <ul className="mt-1 list-inside list-disc">
                    {issues.map((issue) => (
                      <li key={issue}>{issue}</li>
                    ))}
                  </ul>
                ) : (
                  <> Their standing is {profile.standing_display || profile.standing}.</>
                )}
                {profile.standing_reason && (
                  <div className="mt-1 italic">{profile.standing_reason}</div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Still orderable, but something is about to stop that. */}
        {profile.can_order && expiredLicences.length > 0 && (
          <div className="border-b border-warning-200 bg-warning-50 px-4 py-2.5">
            <div className="flex items-start gap-2 text-form text-warning-900">
              <Icon as={TriangleAlert} size="sm" className="mt-0.5 text-warning-700" />
              <div>
                <span className="font-semibold">
                  {expiredLicences.length} licence{expiredLicences.length > 1 ? "s have" : " has"}{" "}
                  expired.
                </span>{" "}
                Buying against an expired FDA licence is the pharmacy's exposure, not the
                supplier's.
              </div>
            </div>
          </div>
        )}

        <div className="min-h-0 flex-1 overflow-y-auto">
          <WorkbenchTabs
            tabs={[
              { id: "terms", label: "Identity & terms" },
              {
                id: "licences",
                label: "Licences",
                badge: expiredLicences.length || undefined,
              },
              { id: "agreements", label: "Price agreements" },
              { id: "performance", label: "Performance" },
            ]}
          >
            <WorkbenchPanel id="terms">
              <TermsTab profile={profile} />
            </WorkbenchPanel>
            <WorkbenchPanel id="licences">
              <LicencesTab profile={profile} />
            </WorkbenchPanel>
            <WorkbenchPanel id="agreements">
              <PriceAgreementsTab profile={profile} />
            </WorkbenchPanel>
            <WorkbenchPanel id="performance">
              <PerformanceTab profile={profile} />
            </WorkbenchPanel>
          </WorkbenchTabs>
        </div>
      </Workbench>
    </div>
  );
}
