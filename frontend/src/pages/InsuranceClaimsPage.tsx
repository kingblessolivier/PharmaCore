/* -------------------------------------------------------------------------- */
/* Claims — ranked by how long is left to submit them.                        */
/*                                                                             */
/* A claim that misses its scheme's window is not late, it is unrecoverable:    */
/* the medicine has gone and nobody will pay for it. So the queue sorts by      */
/* days remaining rather than by date raised, and the rows that have already    */
/* run out are called out rather than left to be noticed.                       */
/* -------------------------------------------------------------------------- */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Ban, Check, Send } from "lucide-react";
import { useState } from "react";
import { DataGrid, type Column } from "../components/DataGrid";
import {
  Drawer,
  ErrorNote,
  Facts,
  Field,
  Grid,
  Input,
  Section,
  Select,
  Textarea,
} from "../components/RecordKit";
import { Badge, Button, PageHeader } from "../components/ui";
import { money, shortDate } from "../lib/format";
import {
  adjudicateClaim,
  claimQueue,
  reverseClaim,
  submitClaim,
  type ClaimQueueRow,
} from "../lib/insurance";
import { useDefaultOrg } from "../lib/recordData";

type Action = { row: ClaimQueueRow; kind: "adjudicate" | "reverse" };

const REJECTION_REASONS = [
  ["NOT_ELIGIBLE", "Member not eligible on the date of service"],
  ["NOT_COVERED", "Product not on the scheme formulary"],
  ["NO_PRIOR_AUTH", "Prior authorisation missing"],
  ["LATE_SUBMISSION", "Submitted outside the claim window"],
  ["DUPLICATE", "Duplicate of a claim already submitted"],
  ["PRICE_EXCEEDED", "Above the scheme's price ceiling"],
  ["QUANTITY_EXCEEDED", "Above the scheme's quantity limit"],
  ["OTHER", "Other"],
] as const;

export function InsuranceClaimsPage() {
  const { orgId } = useDefaultOrg();
  const qc = useQueryClient();
  const [action, setAction] = useState<Action | null>(null);
  const [accepted, setAccepted] = useState(true);
  const [paid, setPaid] = useState("");
  const [reason, setReason] = useState("");
  const [notes, setNotes] = useState("");

  const queue = useQuery({
    queryKey: ["claim-queue", orgId],
    enabled: orgId != null,
    queryFn: () => claimQueue(orgId as number),
  });

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["claim-queue"] });
    void qc.invalidateQueries({ queryKey: ["insurance-overview"] });
  };

  const send = useMutation({
    mutationFn: (id: number) => submitClaim(id),
    onSuccess: invalidate,
  });

  const decide = useMutation({
    mutationFn: (a: Action) =>
      a.kind === "reverse"
        ? reverseClaim(a.row.claim, reason)
        : adjudicateClaim(a.row.claim, {
            accepted,
            paid_amount: accepted && paid ? paid : undefined,
            reason: accepted ? "" : reason,
            notes,
          }),
    onSuccess: () => {
      setAction(null);
      setReason("");
      setNotes("");
      setPaid("");
      invalidate();
    },
  });

  const rows = queue.data ?? [];
  const missed = rows.filter((r) => r.days_left < 0);
  const closing = rows.filter((r) => r.days_left >= 0 && r.days_left <= 7);
  const owed = rows.reduce((s, r) => s + Number(r.outstanding), 0);

  const columns: Column<ClaimQueueRow>[] = [
    {
      key: "claim_number",
      header: "Claim",
      value: (r) => r.claim_number,
      render: (r) => <span className="font-medium text-ink-900">{r.claim_number}</span>,
    },
    { key: "scheme_name", header: "Scheme", value: (r) => r.scheme_name },
    { key: "member_name", header: "Member", value: (r) => r.member_name },
    { key: "sale_number", header: "Sale", value: (r) => r.sale_number },
    {
      key: "service_date",
      header: "Dispensed",
      value: (r) => r.service_date,
      render: (r) => shortDate(r.service_date),
    },
    {
      key: "claimed",
      header: "Claimed",
      align: "right",
      numeric: true,
      value: (r) => Number(r.claimed),
      render: (r) => money(r.claimed),
    },
    {
      key: "outstanding",
      header: "Outstanding",
      align: "right",
      numeric: true,
      value: (r) => Number(r.outstanding),
      render: (r) =>
        Number(r.outstanding) > 0 ? (
          <span className="tabular-nums">{money(r.outstanding)}</span>
        ) : (
          <span className="text-ink-400">—</span>
        ),
    },
    {
      key: "days_left",
      header: "Window",
      align: "right",
      numeric: true,
      value: (r) => r.days_left,
      render: (r) => {
        if (r.days_left < 0) return <Badge tone="danger">closed</Badge>;
        if (r.days_left <= 7) return <Badge tone="warning">{r.days_left}d left</Badge>;
        return <span className="tabular-nums text-ink-600">{r.days_left}d</span>;
      },
    },
    {
      key: "status",
      header: "Status",
      value: (r) => r.status,
      render: (r) => (
        <Badge
          tone={
            r.status === "REJECTED"
              ? "danger"
              : r.status === "SUBMITTED"
                ? "brand"
                : r.status === "PART_PAID"
                  ? "warning"
                  : "neutral"
          }
        >
          {r.status}
        </Badge>
      ),
    },
    {
      key: "actions",
      header: "",
      align: "right",
      fixed: true,
      sortable: false,
      render: (r) => (
        <div className="flex justify-end gap-1.5">
          {r.status === "DRAFT" && (
            <Button
              variant="secondary"
              onClick={(e) => {
                e.stopPropagation();
                send.mutate(r.claim);
              }}
              disabled={send.isPending}
            >
              <Send className="h-3.5 w-3.5" /> Submit
            </Button>
          )}
          {(r.status === "SUBMITTED" || r.status === "PART_PAID") && (
            <Button
              variant="secondary"
              onClick={(e) => {
                e.stopPropagation();
                setAccepted(true);
                setPaid(r.outstanding);
                setReason("");
                setAction({ row: r, kind: "adjudicate" });
              }}
            >
              <Check className="h-3.5 w-3.5" /> Adjudicate
            </Button>
          )}
          {r.status !== "REVERSED" && r.status !== "PAID" && (
            <Button
              variant="ghost"
              onClick={(e) => {
                e.stopPropagation();
                setReason("");
                setAction({ row: r, kind: "reverse" });
              }}
            >
              <Ban className="h-3.5 w-3.5" /> Reverse
            </Button>
          )}
        </div>
      ),
    },
  ];

  const isReverse = action?.kind === "reverse";

  return (
    <div className="space-y-4">
      <PageHeader title="Claims" />
      <p className="-mt-2 max-w-3xl text-sm text-ink-500">
        Sorted by how long is left to submit. A claim past its scheme's window is not late — it is
        unrecoverable, so the deadline is the number that matters here.
      </p>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Tile label="In the queue" value={rows.length} />
        <Tile label="Owed by insurers" value={money(owed)} />
        <Tile
          label="Closing within 7 days"
          value={closing.length}
          tone={closing.length ? "warning" : undefined}
        />
        <Tile
          label="Window already closed"
          value={missed.length}
          tone={missed.length ? "danger" : undefined}
          hint={missed.length ? "cannot be recovered" : "nothing missed"}
        />
      </div>

      {missed.length > 0 && (
        <div className="flex items-start gap-2 rounded-lg border border-danger-200 bg-danger-50 p-3">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-danger-600" />
          <div className="text-sm text-danger-900">
            <span className="font-semibold">
              {missed.length} claim{missed.length === 1 ? "" : "s"} missed the submission window.
            </span>{" "}
            The medicine has gone and the scheme will refuse them as late. Reverse them so they stop
            counting as money you expect.
          </div>
        </div>
      )}

      <DataGrid
        rows={rows}
        columns={columns}
        getRowId={(r) => r.claim}
        loading={queue.isLoading}
        storageKey="insurance-claims"
        exportName="claims"
        searchPlaceholder="Search by claim, scheme, member or sale…"
        emptyMessage="No claims need attention."
      />

      {action && (
        <Drawer
          title={isReverse ? "Reverse this claim" : `Adjudicate ${action.row.claim_number}`}
          subtitle={`${action.row.member_name} · ${action.row.scheme_name}`}
          onClose={() => setAction(null)}
          footer={
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setAction(null)}>
                Cancel
              </Button>
              <Button
                onClick={() => decide.mutate(action)}
                disabled={
                  decide.isPending || ((isReverse || !accepted) && !reason.trim())
                }
              >
                {decide.isPending
                  ? "Saving…"
                  : isReverse
                    ? "Reverse claim"
                    : accepted
                      ? "Record settlement"
                      : "Record rejection"}
              </Button>
            </div>
          }
        >
          <Section title="The claim">
            <Facts
              rows={[
                ["Claim", action.row.claim_number],
                ["Member", action.row.member_name],
                ["Scheme", action.row.scheme_name],
                ["Dispensed", shortDate(action.row.service_date)],
                ["Claimed", money(action.row.claimed)],
                ["Outstanding", money(action.row.outstanding)],
              ]}
            />
          </Section>

          {isReverse ? (
            <Section
              title="Why is this being reversed?"
              hint="The claim is kept, not deleted — a vanished claim leaves the insurer's records and yours disagreeing."
            >
              <Field label="Reason">
                <Textarea
                  autoFocus
                  rows={3}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Script was never collected"
                />
              </Field>
            </Section>
          ) : (
            <>
              <Section title="What did the insurer decide?">
                <Grid cols={2}>
                  <Field label="Outcome">
                    <Select
                      value={accepted ? "accepted" : "rejected"}
                      onChange={(e) => setAccepted(e.target.value === "accepted")}
                    >
                      <option value="accepted">Accepted</option>
                      <option value="rejected">Rejected</option>
                    </Select>
                  </Field>
                  {accepted ? (
                    <Field label="Amount settled">
                      <Input
                        type="number"
                        step="0.01"
                        value={paid}
                        onChange={(e) => setPaid(e.target.value)}
                      />
                    </Field>
                  ) : (
                    <Field label="Reason code">
                      <Select value={reason} onChange={(e) => setReason(e.target.value)}>
                        <option value="">Select a reason…</option>
                        {REJECTION_REASONS.map(([value, label]) => (
                          <option key={value} value={value}>
                            {label}
                          </option>
                        ))}
                      </Select>
                    </Field>
                  )}
                </Grid>
                {accepted && Number(paid) < Number(action.row.claimed) && (
                  <p className="mt-2 text-sm text-warning-700">
                    Short by {money(Number(action.row.claimed) - Number(paid))}. The claim stays
                    part-paid so the shortfall can be chased rather than quietly written off.
                  </p>
                )}
                {!accepted && (
                  <p className="mt-2 text-xs text-ink-500">
                    A reason code is required — without one the claim cannot be worked or
                    resubmitted, and the rejected pile becomes invisible.
                  </p>
                )}
              </Section>

              <Section title="Notes">
                <Field label="Anything to record">
                  <Textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
                </Field>
              </Section>
            </>
          )}

          {decide.isError && <ErrorNote error={decide.error} />}
        </Drawer>
      )}

      {send.isError && <ErrorNote error={send.error} />}
    </div>
  );
}

function Tile({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string | number;
  hint?: string;
  tone?: "danger" | "warning";
}) {
  const colour =
    tone === "danger" ? "text-danger-700" : tone === "warning" ? "text-warning-700" : "text-ink-900";
  return (
    <div className="rounded-lg border border-line bg-surface-0 p-3">
      <div className="text-xs text-ink-500">{label}</div>
      <div className={`mt-0.5 text-xl font-semibold tabular-nums ${colour}`}>{value}</div>
      {hint && <div className="mt-0.5 text-xs text-ink-500">{hint}</div>}
    </div>
  );
}
