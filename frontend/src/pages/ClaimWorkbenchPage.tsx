/* -------------------------------------------------------------------------- */
/* One insurance claim — and, when it fails, what to do about it.              */
/*                                                                             */
/* A rejected claim is money the pharmacy has already spent: the medicine left  */
/* the shelf, the patient went home, and the insurer has now declined to pay.   */
/* The rejection reason is the most actionable field in the system and it was   */
/* being rendered as a bare enum — NO_PRIOR_AUTH, sitting in a table cell.      */
/*                                                                             */
/* Every reason has a different remedy and a different chance of recovery, and  */
/* the difference matters: a missing prior authorisation is usually recoverable */
/* by getting it and resubmitting, while a late submission usually is not. A    */
/* clerk working a rejection queue needs to know which pile a claim is in before */
/* spending an afternoon on it.                                                 */
/* -------------------------------------------------------------------------- */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, RotateCcw, Send, Shield } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { Empty, ErrorNote } from "../components/RecordKit";
import { StatusChip } from "../components/Status";
import { Button, Spinner } from "../components/ui";
import {
  Fieldset,
  Icon,
  LineArea,
  ReadOnly,
  Row,
  Workbench,
  WorkbenchGrid,
  WorkbenchHeader,
  WorkbenchPanel,
  WorkbenchTabs,
} from "../components/Workbench";
import { api } from "../lib/api";
import { money, shortDate } from "../lib/format";
import type { Claim } from "../lib/insurance";

/** What a rejection means in practice, and whether it is worth chasing.
 *
 * `recoverable` is the judgement a clerk otherwise has to carry in their head.
 * It is deliberately conservative: LATE_SUBMISSION and DUPLICATE are marked
 * unrecoverable because in both cases the money is almost always gone, and
 * telling someone to try anyway wastes the afternoon this screen exists to save.
 */
const REJECTION: Record<string, { meaning: string; remedy: string; recoverable: boolean }> = {
  NOT_ELIGIBLE: {
    meaning: "The member was not covered on the date the medicine was dispensed.",
    remedy:
      "Check the policy's start and end dates against the service date. If the card had lapsed, this is a patient debt, not an insurer one.",
    recoverable: false,
  },
  NOT_COVERED: {
    meaning: "The product is not on this scheme's formulary.",
    remedy:
      "Check whether a covered substitute exists. If one does, the fix is at the counter next time; for this claim the balance falls to the patient.",
    recoverable: false,
  },
  NO_PRIOR_AUTH: {
    meaning: "The scheme required authorisation before dispensing and none was recorded.",
    remedy:
      "Request retrospective authorisation from the scheme and resubmit with the reference. Most schemes allow this within a limited window.",
    recoverable: true,
  },
  LATE_SUBMISSION: {
    meaning: "The claim arrived after the scheme's submission window closed.",
    remedy:
      "Rarely recoverable. Worth raising with the scheme only if the delay was theirs. The lesson is in the submission queue, not this claim.",
    recoverable: false,
  },
  DUPLICATE: {
    meaning: "A claim for this service has already been submitted.",
    remedy:
      "Find the original — it may already have been paid. If it was rejected for a different reason, work that one instead of this.",
    recoverable: false,
  },
  PRICE_EXCEEDED: {
    meaning: "The unit price is above the ceiling this scheme will reimburse.",
    remedy:
      "Reprice to the scheme's ceiling and resubmit. The difference is either absorbed or billed to the patient, depending on the scheme's rules.",
    recoverable: true,
  },
  QUANTITY_EXCEEDED: {
    meaning: "The quantity is above what the scheme allows for this product.",
    remedy:
      "Resubmit at the allowed quantity. The excess is a patient charge unless the prescriber can justify it to the scheme.",
    recoverable: true,
  },
  OTHER: {
    meaning: "The scheme gave a reason outside the standard codes.",
    remedy: "Read the notes below — the detail is there rather than in the code.",
    recoverable: true,
  },
};

export function ClaimWorkbenchPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();

  const claimQuery = useQuery({
    queryKey: ["claim", id],
    enabled: Boolean(id),
    queryFn: () => api<Claim>(`/api/insurance/claims/${id}/`),
  });

  const act = useMutation({
    mutationFn: (verb: "submit" | "reverse_claim") =>
      api<Claim>(`/api/insurance/claims/${id}/${verb}/`, { method: "POST" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["claim", id] });
      void qc.invalidateQueries({ queryKey: ["claims"] });
    },
  });

  if (claimQuery.isLoading) return <Spinner />;
  const claim = claimQuery.data;
  if (!claim) return <Empty message="That claim no longer exists." />;

  const lines = claim.lines ?? [];
  const rejected = claim.status === "REJECTED";
  const advice = rejected ? REJECTION[claim.rejection_reason] : undefined;
  const shortfall = Number(claim.shortfall ?? 0);

  return (
    <div className="flex h-full flex-col">
      <div className="mb-2">
        <Link
          to="/insurance/claims"
          className="inline-flex items-center gap-1.5 text-form text-ink-600 hover:text-ink-900"
        >
          <Icon as={ArrowLeft} size="sm" /> Claims
        </Link>
      </div>

      <Workbench>
        <WorkbenchHeader
          icon={Shield}
          title={claim.claim_number || `Claim #${claim.id}`}
          subtitle={`${claim.member_name} · ${claim.scheme_name} · against sale ${claim.sale_number}`}
          status={<StatusChip status={claim.status} />}
          facts={[
            { label: "Service date", value: shortDate(claim.service_date) },
            { label: "Patient paid", value: money(Number(claim.patient_paid)) },
            { label: "Outstanding", value: money(Number(claim.outstanding)) },
            { label: "Claimed", value: money(Number(claim.claimed_amount)), emphasis: true },
          ]}
          actions={
            claim.status === "DRAFT" ? (
              <Button onClick={() => act.mutate("submit")} disabled={act.isPending}>
                <Icon as={Send} size="sm" />
                {act.isPending ? "Submitting…" : "Submit to scheme"}
              </Button>
            ) : claim.status === "PAID" || claim.status === "PART_PAID" ? (
              <Button
                variant="secondary"
                onClick={() => act.mutate("reverse_claim")}
                disabled={act.isPending}
              >
                <Icon as={RotateCcw} size="sm" /> Reverse
              </Button>
            ) : undefined
          }
        />

        {/* The reason is the point of the screen when a claim has failed, so it
            goes above the tabs rather than inside one. */}
        {rejected && advice && (
          <div
            className={`border-b px-4 py-3 ${
              advice.recoverable
                ? "border-warning-200 bg-warning-50"
                : "border-danger-200 bg-danger-50"
            }`}
          >
            <div
              className={`text-form ${advice.recoverable ? "text-warning-900" : "text-danger-900"}`}
            >
              <span className="font-semibold">
                {advice.recoverable ? "Rejected — worth resubmitting." : "Rejected — likely final."}
              </span>{" "}
              {advice.meaning}
              <div className="mt-1">{advice.remedy}</div>
              {claim.notes && <div className="mt-1 italic">Scheme note: {claim.notes}</div>}
            </div>
          </div>
        )}

        <div className="min-h-0 flex-1 overflow-y-auto">
          <WorkbenchTabs
            tabs={[
              { id: "overview", label: "Overview" },
              { id: "money", label: "What is owed" },
            ]}
          >
            <WorkbenchPanel id="overview">
              <WorkbenchGrid cols={2}>
                <Fieldset title="Member" hint="Who was dispensed to, under whose cover">
                  <Row label="Member">
                    <ReadOnly>{claim.member_name}</ReadOnly>
                  </Row>
                  <Row label="Member number">
                    <ReadOnly>
                      <span className="font-mono">{claim.member_number || "—"}</span>
                    </ReadOnly>
                  </Row>
                  <Row label="Scheme">
                    <ReadOnly>{claim.scheme_name}</ReadOnly>
                  </Row>
                  <Row label="Service date">
                    <ReadOnly>{shortDate(claim.service_date)}</ReadOnly>
                  </Row>
                </Fieldset>

                <Fieldset title="Claim" hint="What was submitted, and when">
                  <Row label="Against sale">
                    <ReadOnly>
                      <span className="font-mono">{claim.sale_number}</span>
                    </ReadOnly>
                  </Row>
                  <Row label="Prior authorisation">
                    <ReadOnly>{claim.prior_auth_reference || "none recorded"}</ReadOnly>
                  </Row>
                  <Row label="Submitted">
                    <ReadOnly>
                      {claim.submitted_at ? shortDate(claim.submitted_at) : "not yet submitted"}
                    </ReadOnly>
                  </Row>
                  <Row label="Raised">
                    <ReadOnly>{shortDate(claim.created_at)}</ReadOnly>
                  </Row>
                </Fieldset>
              </WorkbenchGrid>
            </WorkbenchPanel>

            <WorkbenchPanel id="money">
              <WorkbenchGrid cols={2}>
                <Fieldset title="Position" hint="Who has paid what">
                  <Row label="Claimed from scheme">
                    <ReadOnly>{money(Number(claim.claimed_amount))}</ReadOnly>
                  </Row>
                  <Row label="Paid by scheme">
                    <ReadOnly>{money(Number(claim.paid_amount))}</ReadOnly>
                  </Row>
                  <Row label="Still outstanding">
                    <span
                      className={`text-form font-semibold tabular-nums ${
                        Number(claim.outstanding) > 0 ? "text-warning-700" : "text-success-700"
                      }`}
                    >
                      {money(Number(claim.outstanding))}
                    </span>
                  </Row>
                  <Row label="Paid by patient">
                    <ReadOnly>{money(Number(claim.patient_paid))}</ReadOnly>
                  </Row>
                </Fieldset>

                <Fieldset
                  title="Shortfall"
                  hint="Claimed but never going to be paid — the pharmacy absorbs this"
                >
                  {shortfall > 0 ? (
                    <>
                      <div className="text-2xl font-semibold tabular-nums text-danger-700">
                        {money(shortfall)}
                      </div>
                      <p className="mt-1 text-form text-ink-600">
                        The scheme settled below what was claimed. This is a real loss on the
                        dispense, not a timing difference, and it is worth knowing which scheme and
                        which products it keeps happening on.
                      </p>
                    </>
                  ) : (
                    <p className="text-form text-ink-600">
                      Nothing written off — the scheme settled in full, or has not settled yet.
                    </p>
                  )}
                </Fieldset>
              </WorkbenchGrid>
            </WorkbenchPanel>
          </WorkbenchTabs>

          <LineArea title="Items claimed" count={lines.length}>
            <table className="data-grid">
              <thead>
                <tr>
                  <th>Medicine</th>
                  <th className="text-right">Qty</th>
                  <th className="text-right">Unit price</th>
                  <th className="text-right">Gross</th>
                  <th className="text-right">Co-pay</th>
                  <th className="text-right">Patient pays</th>
                  <th className="text-right">Insurer pays</th>
                </tr>
              </thead>
              <tbody>
                {lines.map((line) => (
                  <tr key={line.id}>
                    <td className="text-ink-900">
                      {line.product_name}
                      {line.note && (
                        <span className="ml-2 text-micro text-ink-500">{line.note}</span>
                      )}
                    </td>
                    <td className="text-right tabular-nums">{line.quantity}</td>
                    <td className="text-right tabular-nums text-ink-700">
                      {money(Number(line.unit_price))}
                    </td>
                    <td className="text-right tabular-nums text-ink-700">
                      {money(Number(line.gross_amount))}
                    </td>
                    <td className="text-right tabular-nums text-ink-600">
                      {Number(line.copay_pct_applied)}%
                    </td>
                    <td className="text-right tabular-nums text-ink-700">
                      {money(Number(line.patient_amount))}
                    </td>
                    <td className="text-right font-medium tabular-nums text-ink-900">
                      {money(Number(line.insurer_amount))}
                    </td>
                  </tr>
                ))}
                {lines.length === 0 && (
                  <tr>
                    <td colSpan={7} className="py-6 text-center text-ink-500">
                      No items on this claim.
                    </td>
                  </tr>
                )}
              </tbody>
              {lines.length > 0 && (
                <tfoot>
                  <tr>
                    <td colSpan={5}>{lines.length} item(s)</td>
                    <td className="text-right tabular-nums">{money(Number(claim.patient_paid))}</td>
                    <td className="text-right text-base tabular-nums">
                      {money(Number(claim.claimed_amount))}
                    </td>
                  </tr>
                </tfoot>
              )}
            </table>
          </LineArea>
        </div>
      </Workbench>

      <ErrorNote error={act.error} />
    </div>
  );
}
