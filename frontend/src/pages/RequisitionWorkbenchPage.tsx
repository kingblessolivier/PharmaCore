/* -------------------------------------------------------------------------- */
/* One requisition — and whether anything actually came of it.                 */
/*                                                                             */
/* A requisition's failure mode is not rejection. Rejection is visible and      */
/* someone is told. The failure that costs a pharmacy stock is a requisition    */
/* that was APPROVED and then quietly never ordered: the status reads           */
/* "Approved", everyone assumes it is handled, and six weeks later the shelf is */
/* empty and nobody can say where it stopped.                                   */
/*                                                                             */
/* `quantity_outstanding` has always been on the line and was never shown. It   */
/* is the difference between what was approved and what has been put on a       */
/* purchase order, and it is the only number on this document that tells you    */
/* whether the requisition did its job. So it is the one the screen is built    */
/* around.                                                                      */
/* -------------------------------------------------------------------------- */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ArrowLeft, ClipboardList, Send, ShieldCheck } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { Empty, ErrorNote } from "../components/RecordKit";
import { StatusChip } from "../components/Status";
import { Badge, Button, Spinner } from "../components/ui";
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
import type { PurchaseRequisition } from "../lib/procurement";

const PRIORITY_TONE: Record<string, string> = {
  LOW: "neutral",
  NORMAL: "neutral",
  HIGH: "warning",
  URGENT: "danger",
};

/** How long an approved-but-unordered line has been sitting. */
function daysSince(date: string | null): number | null {
  if (!date) return null;
  return Math.floor((Date.now() - new Date(date).getTime()) / 86_400_000);
}

export function RequisitionWorkbenchPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();

  const reqQuery = useQuery({
    queryKey: ["requisition", id],
    enabled: Boolean(id),
    queryFn: () => api<PurchaseRequisition>(`/api/procurement/requisitions/${id}/`),
  });

  const submit = useMutation({
    mutationFn: () =>
      api<{ approval_id: number; message: string }>(`/api/procurement/requisitions/${id}/submit/`, {
        method: "POST",
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["requisition", id] });
      void qc.invalidateQueries({ queryKey: ["requisitions"] });
    },
  });

  if (reqQuery.isLoading) return <Spinner />;
  const req = reqQuery.data;
  if (!req) return <Empty message="That requisition no longer exists." />;

  const lines = req.lines ?? [];
  const outstanding = lines.filter((l) => (l.quantity_outstanding ?? 0) > 0);
  const trimmed = lines.filter(
    (l) => l.quantity_approved !== undefined && l.quantity_approved < l.quantity,
  );
  /* Only meaningful once approved — before that, "not yet ordered" is simply
     where a requisition is supposed to be. */
  const stalled = req.status === "APPROVED" && outstanding.length > 0;
  const waitingDays = daysSince(req.approved_at);

  return (
    <div className="flex h-full flex-col">
      <div className="mb-2">
        <Link
          to="/procurement/requisitions"
          className="inline-flex items-center gap-1.5 text-form text-ink-600 hover:text-ink-900"
        >
          <Icon as={ArrowLeft} size="sm" /> Requisitions
        </Link>
      </div>

      <Workbench>
        <WorkbenchHeader
          icon={ClipboardList}
          title={req.requisition_number || `Requisition #${req.id}`}
          subtitle={`Raised by ${req.requested_by_name ?? "—"} · ${req.organization_name}`}
          status={
            <span className="flex items-center gap-1.5">
              <StatusChip status={req.status} />
              {req.priority !== "NORMAL" && (
                <Badge tone={PRIORITY_TONE[req.priority]}>{req.priority.toLowerCase()}</Badge>
              )}
            </span>
          }
          facts={[
            { label: "Raised", value: shortDate(req.created_at) },
            { label: "Needed by", value: req.needed_by ? shortDate(req.needed_by) : "—" },
            { label: "Lines", value: lines.length },
            { label: "Estimated", value: money(Number(req.estimated_total)), emphasis: true },
          ]}
          actions={
            req.status === "DRAFT" ? (
              <Button onClick={() => submit.mutate()} disabled={submit.isPending}>
                <Icon as={Send} size="sm" />
                {submit.isPending ? "Sending…" : "Submit for approval"}
              </Button>
            ) : undefined
          }
        />

        {/* The failure this document actually has. Approved and never ordered
            reads as "handled" on every list in the system. */}
        {stalled && (
          <div className="border-b border-warning-200 bg-warning-50 px-4 py-2.5">
            <div className="flex items-start gap-2 text-form text-warning-900">
              <Icon as={AlertTriangle} size="sm" className="mt-0.5 text-warning-700" />
              <div>
                <span className="font-semibold">
                  Approved, but {outstanding.length} line
                  {outstanding.length > 1 ? "s have" : " has"} not been ordered.
                </span>{" "}
                {waitingDays !== null && waitingDays > 0 && (
                  <>
                    Approved {waitingDays} day{waitingDays > 1 ? "s" : ""} ago.{" "}
                  </>
                )}
                Nothing reaches the shelf until a purchase order is raised against it.
              </div>
            </div>
          </div>
        )}

        {req.status === "SUBMITTED" && (
          <div className="border-b border-info-200 bg-info-50 px-4 py-2.5">
            <div className="flex items-start gap-2 text-form text-info-700">
              <Icon as={ShieldCheck} size="sm" className="mt-0.5" />
              <div>
                Waiting in the approvals inbox. It cannot be approved by whoever raised it —{" "}
                <Link to="/approvals" className="font-semibold underline">
                  open approvals
                </Link>
                .
              </div>
            </div>
          </div>
        )}

        <div className="min-h-0 flex-1 overflow-y-auto">
          <WorkbenchTabs
            tabs={[
              { id: "overview", label: "Overview" },
              {
                id: "outcome",
                label: "Outcome",
                badge: outstanding.length + trimmed.length || undefined,
              },
            ]}
          >
            <WorkbenchPanel id="overview">
              <WorkbenchGrid cols={2}>
                <Fieldset title="Request" hint="What is being asked for, and why">
                  <Row label="Raised by">
                    <ReadOnly>{req.requested_by_name ?? "—"}</ReadOnly>
                  </Row>
                  <Row label="For">
                    <ReadOnly>{req.organization_name}</ReadOnly>
                  </Row>
                  <Row label="Priority">
                    <Badge tone={PRIORITY_TONE[req.priority]}>{req.priority.toLowerCase()}</Badge>
                  </Row>
                  <Row label="Needed by">
                    <ReadOnly>
                      {req.needed_by ? shortDate(req.needed_by) : "no date given"}
                    </ReadOnly>
                  </Row>
                  <Row label="Preferred supplier">
                    <ReadOnly>{req.preferred_supplier_name ?? "none named"}</ReadOnly>
                  </Row>
                </Fieldset>

                <Fieldset title="Justification" hint="Why this is being bought">
                  <p className="text-form text-ink-800">
                    {req.justification || "No justification was given."}
                  </p>
                </Fieldset>
              </WorkbenchGrid>
            </WorkbenchPanel>

            <WorkbenchPanel id="outcome">
              <WorkbenchGrid cols={2}>
                <Fieldset title="Decision" hint="Who decided, when, and what they said">
                  <Row label="Decided by">
                    <ReadOnly>{req.approved_by_name ?? "not yet decided"}</ReadOnly>
                  </Row>
                  <Row label="Decided on">
                    <ReadOnly>{req.approved_at ? shortDate(req.approved_at) : "—"}</ReadOnly>
                  </Row>
                  <Row label="Note">
                    <ReadOnly>{req.decision_note || "—"}</ReadOnly>
                  </Row>
                </Fieldset>

                <Fieldset
                  title="Still to order"
                  hint="Approved quantity that no purchase order covers yet"
                >
                  {outstanding.length === 0 ? (
                    <p className="text-form text-ink-600">
                      {req.status === "APPROVED"
                        ? "Every approved line has been put on an order."
                        : "Nothing outstanding — this has not been approved yet."}
                    </p>
                  ) : (
                    <ul className="divide-y divide-line">
                      {outstanding.map((line) => (
                        <li
                          key={line.id ?? line.product}
                          className="flex items-center justify-between py-1.5 text-form"
                        >
                          <span className="text-ink-900">{line.product_name}</span>
                          <span className="font-semibold tabular-nums text-warning-700">
                            {line.quantity_outstanding} outstanding
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </Fieldset>
              </WorkbenchGrid>
            </WorkbenchPanel>
          </WorkbenchTabs>

          <LineArea title="Lines" count={lines.length}>
            <table className="data-grid">
              <thead>
                <tr>
                  <th>Medicine</th>
                  <th className="text-right">Requested</th>
                  <th className="text-right">Approved</th>
                  <th className="text-right">Ordered</th>
                  <th className="text-right">Outstanding</th>
                  <th className="text-right">Est. unit cost</th>
                  <th className="text-right">Est. total</th>
                </tr>
              </thead>
              <tbody>
                {lines.map((line) => {
                  /* Approved for less than was asked is a decision somebody made
                   and nobody was told about — it is worth marking in the row. */
                  const cut =
                    line.quantity_approved !== undefined && line.quantity_approved < line.quantity;
                  const notOrdered = (line.quantity_outstanding ?? 0) > 0;
                  return (
                    <tr key={line.id ?? line.product}>
                      <td className="text-ink-900">
                        {line.product_name}
                        {line.notes && (
                          <span className="ml-2 text-micro text-ink-500">{line.notes}</span>
                        )}
                      </td>
                      <td className="text-right tabular-nums">{line.quantity}</td>
                      <td
                        className={`text-right tabular-nums ${
                          cut ? "font-semibold text-warning-700" : "text-ink-700"
                        }`}
                        title={cut ? "Approved for less than was requested" : ""}
                      >
                        {line.quantity_approved ?? "—"}
                      </td>
                      <td className="text-right tabular-nums text-ink-700">
                        {line.quantity_ordered ?? "—"}
                      </td>
                      <td
                        className={`text-right tabular-nums ${
                          notOrdered ? "font-semibold text-warning-700" : "text-ink-500"
                        }`}
                      >
                        {line.quantity_outstanding || "—"}
                      </td>
                      <td className="text-right tabular-nums text-ink-700">
                        {money(Number(line.estimated_unit_cost))}
                      </td>
                      <td className="text-right font-medium tabular-nums text-ink-900">
                        {money(Number(line.estimated_total ?? 0))}
                      </td>
                    </tr>
                  );
                })}
                {lines.length === 0 && (
                  <tr>
                    <td colSpan={7} className="py-6 text-center text-ink-500">
                      Nothing requested on this document.
                    </td>
                  </tr>
                )}
              </tbody>
              {lines.length > 0 && (
                <tfoot>
                  <tr>
                    <td colSpan={6} className="text-right">
                      Estimated total
                    </td>
                    <td className="text-right text-base tabular-nums">
                      {money(Number(req.estimated_total))}
                    </td>
                  </tr>
                </tfoot>
              )}
            </table>
          </LineArea>
        </div>
      </Workbench>

      <ErrorNote error={submit.error} />
    </div>
  );
}
