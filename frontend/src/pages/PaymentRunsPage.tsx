import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Banknote, Check, Download, Lock, Plus, Send } from "lucide-react";
import { useState } from "react";
import { DataGrid, type Column } from "../components/DataGrid";
import { Button, Card, PageHeader, SelectField, TextField } from "../components/ui";
import { Drawer } from "../components/RecordKit";
import { api, ApiError, downloadFile } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { Paginated, PaymentRun, SupplierBill } from "../lib/types";
import { StatusChip } from "../components/Status";

const money = (n: string | number) =>
  Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 });

/** What the operator can do next, given where the run has got to. */
const NEXT_STEP: Record<string, string> = {
  DRAFT: "Send for approval",
  AWAITING_APPROVAL: "Waiting on approver(s) — see the Approvals inbox",
  APPROVED: "Download the file, then mark disbursed",
  DISBURSED: "Reconcile against the bank statement, then lock",
  LOCKED: "Closed",
  CANCELLED: "Abandoned",
};

function NewRunModal({ onClose, orgId }: { onClose: () => void; orgId: number }) {
  const qc = useQueryClient();
  const [method, setMethod] = useState("BANK_TRANSFER");
  const [scheduledFor, setScheduledFor] = useState("");
  const [selected, setSelected] = useState<number[]>([]);
  const [error, setError] = useState<string | null>(null);

  const billsQ = useQuery({
    queryKey: ["supplier-bills", "unpaid", orgId],
    queryFn: () =>
      api<Paginated<SupplierBill>>(
        `/api/finance/supplier-bills/?organization=${orgId}&page_size=200`,
      ),
    enabled: orgId > 0,
  });

  const unpaid = (billsQ.data?.results ?? []).filter((b) => b.status !== "PAID");
  const total = unpaid
    .filter((b) => selected.includes(b.id))
    .reduce((sum, b) => sum + Number(b.amount_due), 0);

  const create = useMutation({
    mutationFn: () =>
      api<PaymentRun>("/api/finance/payment-runs/", {
        method: "POST",
        body: JSON.stringify({
          organization: orgId,
          bills: selected,
          method,
          scheduled_for: scheduledFor || null,
        }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["payment-runs"] });
      onClose();
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not open this run."),
  });

  function toggle(id: number) {
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  }

  return (
    <Drawer title="New payment run" onClose={onClose} width="max-w-4xl">
      <div className="flex flex-col gap-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <SelectField label="Channel" value={method} onChange={(e) => setMethod(e.target.value)}>
            <option value="BANK_TRANSFER">Bank transfer</option>
            <option value="MOBILE_MONEY">Mobile money (MoMo)</option>
            <option value="CHEQUE">Cheque</option>
          </SelectField>
          <TextField
            label="Scheduled for"
            type="date"
            value={scheduledFor}
            onChange={(e) => setScheduledFor(e.target.value)}
          />
        </div>

        <div>
          <div className="mb-2 flex items-center justify-between">
            <p className="text-xs font-medium text-ink-500">
              Bills to settle
            </p>
            <button
              type="button"
              className="text-xs font-semibold text-brand-700 hover:underline"
              onClick={() =>
                setSelected(selected.length === unpaid.length ? [] : unpaid.map((b) => b.id))
              }
            >
              {selected.length === unpaid.length ? "Clear all" : "Select all"}
            </button>
          </div>
          <div className="max-h-80 overflow-y-auto rounded-md border border-line">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-surface-100">
                <tr className="text-left text-xs text-ink-500">
                  <th className="w-10 px-3 py-2"></th>
                  <th className="px-3 py-2">Supplier</th>
                  <th className="px-3 py-2">Bill</th>
                  <th className="px-3 py-2">Due</th>
                  <th className="px-3 py-2 text-right">Outstanding</th>
                </tr>
              </thead>
              <tbody>
                {unpaid.map((b) => (
                  <tr
                    key={b.id}
                    className="cursor-pointer border-t border-line/60 hover:bg-surface-100"
                    onClick={() => toggle(b.id)}
                  >
                    <td className="px-3 py-2">
                      <input
                        type="checkbox"
                        checked={selected.includes(b.id)}
                        onChange={() => toggle(b.id)}
                        onClick={(e) => e.stopPropagation()}
                        className="rounded border-line"
                      />
                    </td>
                    <td className="px-3 py-2 font-medium">{b.supplier_name}</td>
                    <td className="px-3 py-2">{b.bill_number || `#${b.id}`}</td>
                    <td className="px-3 py-2">{b.due_date ?? "—"}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{money(b.amount_due)}</td>
                  </tr>
                ))}
                {unpaid.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-3 py-6 text-center text-ink-500">
                      Nothing outstanding — every supplier bill is settled.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="flex items-center justify-between rounded-md bg-surface-100 px-3 py-2">
          <span className="text-sm text-ink-700">
            {selected.length} bill{selected.length === 1 ? "" : "s"} selected
          </span>
          <span className="text-lg font-semibold tabular-nums">RWF {money(total)}</span>
        </div>
        {total > 5_000_000 && (
          <p className="rounded-md bg-amber-50 p-2 text-sm text-amber-800">
            Above the dual-approval threshold — this run will need two separate sign-offs.
          </p>
        )}
        {error && <p className="rounded-md bg-red-50 p-2 text-sm text-red-700">{error}</p>}

        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={() => create.mutate()}
            disabled={selected.length === 0 || create.isPending}
          >
            {create.isPending ? "Opening…" : "Open run"}
          </Button>
        </div>
      </div>
    </Drawer>
  );
}

function RunDetail({ run, onClose }: { run: PaymentRun; onClose: () => void }) {
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const act = useMutation({
    mutationFn: (action: string) =>
      api<PaymentRun>(`/api/finance/payment-runs/${run.id}/${action}/`, { method: "POST" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["payment-runs"] });
      onClose();
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "That step failed."),
  });

  return (
    <Drawer title={run.run_number} onClose={onClose} width="max-w-4xl">
      <div className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div>
            <p className="text-xs text-ink-500">Status</p>
            <StatusChip status={run.status} />
          </div>
          <div>
            <p className="text-xs text-ink-500">Total</p>
            <p className="font-semibold tabular-nums">RWF {money(run.total_amount)}</p>
          </div>
          <div>
            <p className="text-xs text-ink-500">Channel</p>
            <p>{run.method.replace("_", " ").toLowerCase()}</p>
          </div>
          <div>
            <p className="text-xs text-ink-500">Approvals</p>
            <p className="tabular-nums">
              {run.approvals_received} of {run.approvals_required}
            </p>
          </div>
        </div>

        <p className="rounded-md bg-surface-100 px-3 py-2 text-sm text-ink-700">
          {NEXT_STEP[run.status]}
        </p>

        <div className="overflow-x-auto rounded-md border border-line">
          <table className="w-full text-sm">
            <thead className="bg-surface-100">
              <tr className="text-left text-xs text-ink-500">
                <th className="px-3 py-2">Supplier</th>
                <th className="px-3 py-2">Bill</th>
                <th className="px-3 py-2">Payee account</th>
                <th className="px-3 py-2 text-right">Amount</th>
                <th className="px-3 py-2">Settled</th>
              </tr>
            </thead>
            <tbody>
              {run.lines.map((line) => (
                <tr key={line.id} className="border-t border-line/60">
                  <td className="px-3 py-2 font-medium">{line.supplier_name}</td>
                  <td className="px-3 py-2">{line.bill_number || `#${line.bill}`}</td>
                  <td className="px-3 py-2 text-ink-500">{line.payee_account || "—"}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{money(line.amount)}</td>
                  <td className="px-3 py-2">
                    {line.paid ? <Check className="h-4 w-4 text-green-600" /> : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {error && <p className="rounded-md bg-red-50 p-2 text-sm text-red-700">{error}</p>}

        <div className="flex flex-wrap justify-end gap-2">
          {run.status === "DRAFT" && (
            <>
              <Button variant="secondary" onClick={() => act.mutate("cancel")}>
                Cancel run
              </Button>
              <Button onClick={() => act.mutate("submit")} disabled={act.isPending}>
                <Send className="h-4 w-4" /> Send for approval
              </Button>
            </>
          )}
          {run.has_disbursement_file && (
            <Button
              variant="secondary"
              onClick={() =>
                void downloadFile(
                  `/api/finance/payment-runs/${run.id}/disbursement-file/`,
                  run.disbursement_filename,
                )
              }
            >
              <Download className="h-4 w-4" /> Download file
            </Button>
          )}
          {run.status === "APPROVED" && (
            <Button onClick={() => act.mutate("disburse")} disabled={act.isPending}>
              <Banknote className="h-4 w-4" /> Mark disbursed
            </Button>
          )}
          {run.status === "DISBURSED" && (
            <Button onClick={() => act.mutate("lock")} disabled={act.isPending}>
              <Lock className="h-4 w-4" /> Lock run
            </Button>
          )}
        </div>
      </div>
    </Drawer>
  );
}

export function PaymentRunsPage() {
  const { user } = useAuth();
  const orgId = user?.organization ?? 0;
  const [creating, setCreating] = useState(false);
  const [open, setOpen] = useState<PaymentRun | null>(null);

  const runsQ = useQuery({
    queryKey: ["payment-runs", orgId],
    queryFn: () =>
      api<Paginated<PaymentRun>>(`/api/finance/payment-runs/?organization=${orgId}&page_size=100`),
    enabled: orgId > 0,
  });

  const columns: Column<PaymentRun>[] = [
    { key: "run_number", header: "Run", value: (r) => r.run_number },
    { key: "created_at", header: "Opened", value: (r) => r.created_at.slice(0, 10) },
    {
      key: "method",
      header: "Channel",
      value: (r) => r.method,
      render: (r) => r.method.replace("_", " ").toLowerCase(),
    },
    {
      key: "line_count",
      header: "Bills",
      numeric: true,
      align: "right",
      value: (r) => r.line_count,
    },
    {
      key: "total_amount",
      header: "Total",
      numeric: true,
      align: "right",
      value: (r) => Number(r.total_amount),
      render: (r) => <span className="font-semibold">{money(r.total_amount)}</span>,
    },
    {
      key: "approvals",
      header: "Approvals",
      align: "center",
      value: (r) => `${r.approvals_received}/${r.approvals_required}`,
    },
    {
      key: "status",
      header: "Status",
      value: (r) => r.status,
      render: (r) => <StatusChip status={r.status} />,
    },
  ];

  return (
    <div>
      <PageHeader
        title="Payment runs"
        action={
          orgId > 0 && (
            <Button onClick={() => setCreating(true)}>
              <Plus className="h-4 w-4" /> New run
            </Button>
          )
        }
      />
      <Card className="mb-4 p-4 text-sm text-ink-700">
        A run gathers unpaid supplier bills into one approved batch, emits the file the bank or MoMo
        aggregator expects, and only posts the payments once the money has actually moved. Each row
        in the file carries an idempotency key, so an upload that gets repeated still settles once.
      </Card>
      <DataGrid
        rows={runsQ.data?.results ?? []}
        columns={columns}
        getRowId={(r) => r.id}
        loading={runsQ.isLoading}
        storageKey="payment-runs"
        exportName="payment-runs"
        searchPlaceholder="Search by run number…"
        emptyMessage="No payment runs yet."
        onRowClick={(r) => setOpen(r)}
      />
      {creating && <NewRunModal orgId={orgId} onClose={() => setCreating(false)} />}
      {open && <RunDetail run={open} onClose={() => setOpen(null)} />}
    </div>
  );
}
