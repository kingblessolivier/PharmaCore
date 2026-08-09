/* -------------------------------------------------------------------------- */
/* Inbound quality control — the decision that turns quarantined goods into    */
/* stock a pharmacist may dispense.                                            */
/*                                                                             */
/* Two things this screen must convey that a plain pass/fail pair did not:      */
/* how long stock has been held (quarantined medicine is capital that cannot   */
/* be sold and is quietly running down its shelf life), and that a rejection    */
/* needs a stated reason — the API refuses a blank one, because that reason is  */
/* the whole audit trail.                                                       */
/* -------------------------------------------------------------------------- */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Check, ShieldCheck, X } from "lucide-react";
import { useState } from "react";
import { DataGrid, type Column } from "../components/DataGrid";
import { BatchPaperwork } from "../components/BatchPaperwork";
import { Drawer, ErrorNote, Facts, Field, Section, Textarea } from "../components/RecordKit";
import { Badge, Button, PageHeader } from "../components/ui";
import { shortDate } from "../lib/format";
import { quarantineQueue, rejectBatch, releaseBatch, type QuarantineRow } from "../lib/inventory";
import { useDefaultOrg } from "../lib/recordData";

type Decision = { row: QuarantineRow; kind: "release" | "reject" };

export function QualityControlPage() {
  const { orgId } = useDefaultOrg();
  const qc = useQueryClient();
  const [decision, setDecision] = useState<Decision | null>(null);
  const [reason, setReason] = useState("");

  const queue = useQuery({
    queryKey: ["quarantine-queue", orgId],
    enabled: orgId != null,
    queryFn: () => quarantineQueue(orgId as number),
  });

  const decide = useMutation({
    mutationFn: (d: Decision) =>
      d.kind === "release" ? releaseBatch(d.row.check, reason) : rejectBatch(d.row.check, reason),
    onSuccess: () => {
      setDecision(null);
      setReason("");
      void qc.invalidateQueries({ queryKey: ["quarantine-queue"] });
      void qc.invalidateQueries({ queryKey: ["quality-checks"] });
    },
  });

  const rows = queue.data ?? [];
  const held = rows.reduce((s, r) => s + r.quantity, 0);
  const expiringHeld = rows.filter((r) => r.days_to_expiry <= 90);
  const stale = rows.filter((r) => r.waiting_days >= 3);

  const columns: Column<QuarantineRow>[] = [
    {
      key: "product_name",
      header: "Medicine",
      value: (r) => r.product_name,
      render: (r) => <span className="font-medium text-ink-900">{r.product_name}</span>,
    },
    {
      key: "batch_number",
      header: "Batch",
      value: (r) => r.batch_number,
      render: (r) => <span className="font-mono text-xs text-ink-700">{r.batch_number}</span>,
    },
    {
      key: "quantity",
      header: "Units held",
      align: "right",
      numeric: true,
      value: (r) => r.quantity,
      render: (r) => <span className="tabular-nums">{r.quantity.toLocaleString()}</span>,
    },
    {
      key: "waiting_days",
      header: "Waiting",
      align: "right",
      numeric: true,
      value: (r) => r.waiting_days,
      render: (r) =>
        r.waiting_days >= 3 ? (
          <Badge tone="warning">{r.waiting_days}d</Badge>
        ) : (
          <span className="tabular-nums text-ink-600">
            {r.waiting_days === 0 ? "today" : `${r.waiting_days}d`}
          </span>
        ),
    },
    {
      key: "days_to_expiry",
      header: "Expires",
      value: (r) => r.expiry_date,
      render: (r) => (
        <span className={r.days_to_expiry <= 90 ? "text-warning-700" : "text-ink-600"}>
          {shortDate(r.expiry_date)}
          <span className="ml-1 text-xs text-ink-500">({r.days_to_expiry}d)</span>
        </span>
      ),
    },
    {
      key: "checks",
      header: "On arrival",
      sortable: false,
      value: (r) => `${r.visual_integrity_ok}-${r.temp_indicator_ok}`,
      render: (r) => (
        <div className="flex gap-2 text-xs">
          <span className={r.visual_integrity_ok ? "text-success-700" : "text-danger-700"}>
            {r.visual_integrity_ok ? "seal ok" : "seal failed"}
          </span>
          <span className={r.temp_indicator_ok ? "text-success-700" : "text-danger-700"}>
            {r.temp_indicator_ok ? "temp ok" : "temp breached"}
          </span>
        </div>
      ),
    },
    { key: "raised_by", header: "Received by", value: (r) => r.raised_by },
    {
      key: "actions",
      header: "",
      align: "right",
      fixed: true,
      sortable: false,
      render: (r) => (
        <div className="flex justify-end gap-1.5">
          <Button
            variant="secondary"
            onClick={(e) => {
              e.stopPropagation();
              setReason("");
              setDecision({ row: r, kind: "release" });
            }}
          >
            <Check className="h-3.5 w-3.5" /> Release
          </Button>
          <Button
            variant="ghost"
            onClick={(e) => {
              e.stopPropagation();
              setReason("");
              setDecision({ row: r, kind: "reject" });
            }}
          >
            <X className="h-3.5 w-3.5" /> Reject
          </Button>
        </div>
      ),
    },
  ];

  const isReject = decision?.kind === "reject";

  return (
    <div className="space-y-4">
      <PageHeader title="Quality control" />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Tile label="Awaiting a decision" value={rows.length} />
        <Tile label="Units held" value={held.toLocaleString()} hint="cannot be sold or dispensed" />
        <Tile
          label="Waiting 3+ days"
          value={stale.length}
          tone={stale.length ? "warning" : undefined}
        />
        <Tile
          label="Expiring within 90 days"
          value={expiringHeld.length}
          tone={expiringHeld.length ? "danger" : undefined}
          hint={expiringHeld.length ? "will expire while held" : "none at risk"}
        />
      </div>

      {expiringHeld.length > 0 && (
        <div className="flex items-start gap-2 rounded-lg border border-danger-200 bg-danger-50 p-3">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-danger-600" />
          <div className="text-sm text-danger-900">
            <span className="font-semibold">
              {expiringHeld.length} batch(es) will expire while still in quarantine.
            </span>{" "}
            Stock that expires waiting for a decision is the worst outcome available: paid for,
            never sold, and destroyed at your cost.
          </div>
        </div>
      )}

      <DataGrid
        rows={rows}
        columns={columns}
        getRowId={(r) => r.check}
        loading={queue.isLoading}
        storageKey="quarantine-queue"
        exportName="quarantine-queue"
        searchPlaceholder="Search by medicine or batch…"
        emptyMessage="Nothing is waiting on a quality decision."
      />

      {decision && (
        <Drawer
          title={isReject ? "Reject this batch" : "Release into saleable stock"}
          subtitle={`${decision.row.product_name} · ${decision.row.batch_number}`}
          badge={
            isReject ? <Badge tone="danger">Reject</Badge> : <Badge tone="success">Release</Badge>
          }
          onClose={() => setDecision(null)}
          footer={
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setDecision(null)}>
                Cancel
              </Button>
              <Button
                onClick={() => decide.mutate(decision)}
                disabled={decide.isPending || (isReject && !reason.trim())}
              >
                {decide.isPending ? "Saving…" : isReject ? "Reject and hold" : "Release to stock"}
              </Button>
            </div>
          }
        >
          {/* Releasing a lot is the moment its paperwork has to exist — a
              Certificate of Analysis is issued for this batch, and a
              manufacturer's GMP certificate does not answer for it. */}
          {decision.row.batch != null && (
            <div className="mb-4">
              <BatchPaperwork batchId={decision.row.batch} />
            </div>
          )}

          <Section title="What you are deciding on">
            <Facts
              rows={[
                ["Medicine", decision.row.product_name],
                ["Batch", decision.row.batch_number],
                ["Units", decision.row.quantity.toLocaleString()],
                ["Expiry", shortDate(decision.row.expiry_date)],
                ["Held for", `${decision.row.waiting_days} day(s)`],
                ["Received by", decision.row.raised_by],
              ]}
            />
            {(!decision.row.visual_integrity_ok || !decision.row.temp_indicator_ok) && (
              <p className="mt-2 text-sm text-danger-700">
                This delivery failed an arrival check
                {!decision.row.visual_integrity_ok && " (packaging integrity)"}
                {!decision.row.temp_indicator_ok && " (temperature indicator)"}. Releasing it anyway
                needs a reason on record.
              </p>
            )}
          </Section>

          <Section
            title={isReject ? "Reason for rejection" : "Release note"}
            hint={
              isReject
                ? "Required. This is the audit trail — it is the only record of why the stock was refused."
                : "Optional, but the place to record what you verified (certificate of analysis, seal, cold-chain indicator)."
            }
          >
            <Field label={isReject ? "Why is this batch being rejected?" : "Notes"}>
              <Textarea
                autoFocus
                rows={3}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder={
                  isReject
                    ? "Seal broken on 3 cartons; temperature indicator triggered"
                    : "COA checked against batch; seals intact"
                }
              />
            </Field>
          </Section>

          {!isReject && (
            <Section title="What happens">
              <p className="flex items-start gap-2 text-sm text-ink-600">
                <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-success-600" />
                <span>
                  {decision.row.quantity.toLocaleString()} unit(s) become saleable immediately and
                  enter the FEFO pool, so they can be picked, transferred and dispensed.
                </span>
              </p>
            </Section>
          )}

          {decide.isError && <ErrorNote error={decide.error} />}
        </Drawer>
      )}
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
    tone === "danger"
      ? "text-danger-700"
      : tone === "warning"
        ? "text-warning-700"
        : "text-ink-900";
  return (
    <div className="rounded-lg border border-line bg-surface-0 p-3">
      <div className="text-xs text-ink-500">{label}</div>
      <div className={`mt-0.5 text-xl font-semibold tabular-nums ${colour}`}>{value}</div>
      {hint && <div className="mt-0.5 text-xs text-ink-500">{hint}</div>}
    </div>
  );
}
