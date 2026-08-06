import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Play, Plus, Send } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Button, Modal, PageHeader, Spinner, TextField } from "../components/ui";
import { api, ApiError, downloadFile } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { Paginated, PayrollRun } from "../lib/types";

const money = (n: string | number) => Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 });

const STATUS_TONE: Record<string, string> = {
  DRAFT: "text-ink-500 bg-surface-100",
  PENDING_APPROVAL: "text-amber-700 bg-amber-50",
  APPROVED: "text-green-700 bg-green-50",
  PAID: "text-brand-700 bg-brand-50",
};

function NewRunModal({ onClose, orgId }: { onClose: () => void; orgId: number }) {
  const qc = useQueryClient();
  const today = new Date();
  const firstOfMonth = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().slice(0, 10);
  const lastOfMonth = new Date(today.getFullYear(), today.getMonth() + 1, 0).toISOString().slice(0, 10);
  const [periodStart, setPeriodStart] = useState(firstOfMonth);
  const [periodEnd, setPeriodEnd] = useState(lastOfMonth);
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () =>
      api<PayrollRun>("/api/hr/payroll-runs/", {
        method: "POST",
        body: JSON.stringify({ organization: orgId, period_start: periodStart, period_end: periodEnd }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["payroll-runs"] });
      onClose();
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not build this payroll run."),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    create.mutate();
  }

  return (
    <Modal title="Run payroll" onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <p className="text-sm text-ink-500">
          Computes gross→net for every active/probationary employee using the current statutory
          rates (PAYE, RSSB pension, maternity, CBHI).
        </p>
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Period start" type="date" value={periodStart} onChange={(e) => setPeriodStart(e.target.value)} required />
          <TextField label="Period end" type="date" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)} required />
        </div>
        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? "Computing…" : "Compute run"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function RunDetail({ run }: { run: PayrollRun }) {
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const submit = useMutation({
    mutationFn: () => api<PayrollRun>(`/api/hr/payroll-runs/${run.id}/submit/`, { method: "POST" }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["payroll-runs"] }),
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not submit this run."),
  });
  const markPaid = useMutation({
    mutationFn: () => api<PayrollRun>(`/api/hr/payroll-runs/${run.id}/mark-paid/`, { method: "POST" }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["payroll-runs"] }),
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not mark this run paid."),
  });

  return (
    <div className="rounded-lg border border-line bg-surface-0">
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <div>
          <span className="text-sm font-semibold text-ink-900">
            {run.period_start} – {run.period_end}
          </span>
          <span className={`ml-2 inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${STATUS_TONE[run.status]}`}>
            {run.status.replace("_", " ")}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="font-mono text-sm font-semibold">RWF {money(run.total_net_pay)} net</span>
          {run.status === "DRAFT" && (
            <Button onClick={() => submit.mutate()} disabled={submit.isPending}>
              <Send className="h-4 w-4" /> Submit for approval
            </Button>
          )}
          {run.status === "APPROVED" && (
            <Button onClick={() => markPaid.mutate()} disabled={markPaid.isPending}>
              <Play className="h-4 w-4" /> Mark paid
            </Button>
          )}
        </div>
      </div>
      {error && <p className="px-4 pt-2 text-sm text-danger">{error}</p>}
      {run.status === "PENDING_APPROVAL" && (
        <p className="px-4 py-2 text-xs text-ink-500">
          Waiting on another approver in the <strong>Approvals inbox</strong> — you cannot approve your
          own payroll run.
        </p>
      )}
      <table className="w-full text-sm">
        <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-500">
          <tr>
            <th className="px-4 py-2">Employee</th>
            <th className="px-4 py-2 text-right">Gross</th>
            <th className="px-4 py-2 text-right">PAYE</th>
            <th className="px-4 py-2 text-right">RSSB</th>
            <th className="px-4 py-2 text-right">CBHI</th>
            <th className="px-4 py-2 text-right">Net pay</th>
            <th className="px-4 py-2 text-right">Payslip</th>
          </tr>
        </thead>
        <tbody>
          {run.records.map((r) => (
            <tr key={r.id} className="border-b border-line last:border-0">
              <td className="px-4 py-2">
                {r.employee_name} <span className="text-xs text-ink-500">({r.employee_number})</span>
              </td>
              <td className="px-4 py-2 text-right font-mono">{money(r.gross)}</td>
              <td className="px-4 py-2 text-right font-mono">{money(r.paye)}</td>
              <td className="px-4 py-2 text-right font-mono">
                {money(Number(r.pension_employee) + Number(r.maternity_employee))}
              </td>
              <td className="px-4 py-2 text-right font-mono">{money(r.cbhi)}</td>
              <td className="px-4 py-2 text-right font-mono font-semibold">{money(r.net_pay)}</td>
              <td className="px-4 py-2 text-right">
                {r.payslip_document_id ? (
                  <button
                    onClick={() =>
                      void downloadFile(
                        `/api/documents/${r.payslip_document_id}/download/`,
                        `payslip-${r.employee_number}.pdf`,
                      )
                    }
                    className="inline-flex items-center gap-1 text-brand-700 hover:underline"
                  >
                    <Download className="h-3.5 w-3.5" /> PDF
                  </button>
                ) : (
                  <span className="text-ink-400">—</span>
                )}
              </td>
            </tr>
          ))}
          {run.records.length === 0 && (
            <tr>
              <td colSpan={7} className="px-4 py-6 text-center text-ink-500">
                No employees on this run.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export function PayrollPage() {
  const { user } = useAuth();
  const [adding, setAdding] = useState(false);
  const orgId = user?.organization ?? 0;

  const runsQ = useQuery({
    queryKey: ["payroll-runs", orgId],
    queryFn: () => api<Paginated<PayrollRun>>(`/api/hr/payroll-runs/?organization=${orgId}`),
    enabled: orgId > 0,
  });

  return (
    <div>
      <PageHeader
        title="Payroll"
        action={
          orgId > 0 && (
            <Button onClick={() => setAdding(true)}>
              <Plus className="h-4 w-4" /> Run payroll
            </Button>
          )
        }
      />
      <p className="mb-4 text-sm text-ink-500">
        Gross→net for every employee, computed from the current statutory rates. A run is never
        self-approved — it posts to the Finance ledger and generates payslips once decided.
      </p>

      {runsQ.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      <div className="flex flex-col gap-4">
        {runsQ.data?.results.map((run) => <RunDetail key={run.id} run={run} />)}
        {runsQ.data && runsQ.data.results.length === 0 && (
          <div className="rounded-lg border border-dashed border-line py-10 text-center text-sm text-ink-500">
            No payroll runs yet.
          </div>
        )}
      </div>

      {adding && <NewRunModal onClose={() => setAdding(false)} orgId={orgId} />}
    </div>
  );
}
