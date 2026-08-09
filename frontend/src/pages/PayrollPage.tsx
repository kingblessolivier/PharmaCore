import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Play, Plus, Send } from "lucide-react";
import { useState } from "react";
import { DataGrid } from "../components/DataGrid";
import {
  Drawer,
  ErrorNote,
  Facts,
  Field,
  Grid,
  Input,
  Section,
  StatusBadge,
} from "../components/RecordKit";
import { Badge, Button, PageHeader } from "../components/ui";
import { api, downloadFile } from "../lib/api";
import { amount, dateTime, money } from "../lib/format";
import { useDefaultOrg } from "../lib/recordData";
import type { Paginated, PayrollRecord, PayrollRun } from "../lib/types";

/* -------------------------------------------------------------------------- */

function NewRunDrawer({ orgId, onClose }: { orgId: number | null; onClose: () => void }) {
  const qc = useQueryClient();
  const today = new Date();
  const [periodStart, setPeriodStart] = useState(
    new Date(today.getFullYear(), today.getMonth(), 1).toISOString().slice(0, 10),
  );
  const [periodEnd, setPeriodEnd] = useState(
    new Date(today.getFullYear(), today.getMonth() + 1, 0).toISOString().slice(0, 10),
  );

  const create = useMutation({
    mutationFn: () =>
      api<PayrollRun>("/api/hr/payroll-runs/", {
        method: "POST",
        body: JSON.stringify({
          organization: orgId,
          period_start: periodStart,
          period_end: periodEnd,
        }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["payroll-runs"] });
      onClose();
    },
  });

  return (
    <Drawer
      title="Run payroll"
      onClose={onClose}
      width="max-w-xl"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={create.isPending} onClick={() => create.mutate()}>
            {create.isPending ? "Computing…" : "Compute run"}
          </Button>
        </>
      }
    >
      <ErrorNote error={create.error} />
      <Section title="Period">
        <Grid cols={2}>
          <Field label="Period start">
            <Input
              type="date"
              value={periodStart}
              onChange={(e) => setPeriodStart(e.target.value)}
            />
          </Field>
          <Field label="Period end">
            <Input type="date" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)} />
          </Field>
        </Grid>
        <p className="mt-3 text-xs text-ink-500">
          PAYE bands, RSSB pension and maternity, CBHI and occupational hazards are read from the
          effective-dated statutory-rate table — never hardcoded — so a re-run of an old period
          reproduces the same payslips.
        </p>
      </Section>
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

function RunDrawer({ run, onClose }: { run: PayrollRun; onClose: () => void }) {
  const qc = useQueryClient();
  const invalidate = () => void qc.invalidateQueries({ queryKey: ["payroll-runs"] });

  const submit = useMutation({
    mutationFn: () => api<PayrollRun>(`/api/hr/payroll-runs/${run.id}/submit/`, { method: "POST" }),
    onSuccess: invalidate,
  });
  const markPaid = useMutation({
    mutationFn: () =>
      api<PayrollRun>(`/api/hr/payroll-runs/${run.id}/mark-paid/`, { method: "POST" }),
    onSuccess: invalidate,
  });

  const totals = run.records.reduce(
    (acc, r) => ({
      gross: acc.gross + Number(r.gross),
      paye: acc.paye + Number(r.paye),
      rssb: acc.rssb + Number(r.pension_employee) + Number(r.maternity_employee),
      cbhi: acc.cbhi + Number(r.cbhi),
      loans: acc.loans + Number(r.loans_advances),
      net: acc.net + Number(r.net_pay),
      employer: acc.employer + Number(r.pension_employer) + Number(r.maternity_employer),
    }),
    { gross: 0, paye: 0, rssb: 0, cbhi: 0, loans: 0, net: 0, employer: 0 },
  );

  return (
    <Drawer
      title={`Payroll ${run.period_start} – ${run.period_end}`}
      badge={<StatusBadge status={run.status} />}
      subtitle={
        <>
          {run.organization_name} · {run.records.length} employee(s) · raised by{" "}
          {run.created_by_name ?? "—"}
          {run.approved_by_name && ` · approved by ${run.approved_by_name}`}
        </>
      }
      onClose={onClose}
      width="max-w-6xl"
      footer={
        <>
          {run.status === "DRAFT" && (
            <Button disabled={submit.isPending} onClick={() => submit.mutate()}>
              <Send className="h-3.5 w-3.5" /> Submit for approval
            </Button>
          )}
          {run.status === "APPROVED" && (
            <Button disabled={markPaid.isPending} onClick={() => markPaid.mutate()}>
              <Play className="h-3.5 w-3.5" /> Mark paid
            </Button>
          )}
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
        </>
      }
    >
      <ErrorNote error={submit.error ?? markPaid.error} />

      {run.status === "PENDING_APPROVAL" && (
        <div className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          Waiting on another approver in the <strong>Approvals inbox</strong> — you cannot approve
          your own payroll run.
        </div>
      )}

      <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          ["Gross", totals.gross],
          ["Deductions", totals.paye + totals.rssb + totals.cbhi + totals.loans],
          ["Net pay", totals.net],
          ["Employer cost", totals.gross + totals.employer],
        ].map(([label, value]) => (
          <div key={String(label)} className="rounded-lg border border-line px-3 py-2">
            <div className="text-[11px] text-ink-500">{label}</div>
            <div className="text-lg font-semibold tabular-nums">{money(value as number)}</div>
          </div>
        ))}
      </div>

      <Section title="Payroll register" hint="Sort, search and export exactly like any other grid.">
        <DataGrid<PayrollRecord>
          rows={run.records}
          getRowId={(r) => r.id}
          storageKey="payroll-register"
          exportName={`payroll-${run.period_start}`}
          searchPlaceholder="Search the register by name or number…"
          emptyMessage="No employees on this run."
          initialDensity="compact"
          columns={[
            {
              key: "employee_name",
              header: "Employee",
              render: (r) => (
                <div>
                  <div className="font-medium text-ink-900">{r.employee_name}</div>
                  <div className="font-mono text-xs text-ink-500">{r.employee_number}</div>
                </div>
              ),
              value: (r) => `${r.employee_name} ${r.employee_number}`,
            },
            {
              key: "gross",
              header: "Gross",
              align: "right",
              numeric: true,
              value: (r) => Number(r.gross),
              render: (r) => amount(r.gross),
            },
            {
              key: "paye",
              header: "PAYE",
              align: "right",
              numeric: true,
              value: (r) => Number(r.paye),
              render: (r) => amount(r.paye),
            },
            {
              key: "rssb",
              header: "RSSB",
              align: "right",
              numeric: true,
              value: (r) => Number(r.pension_employee) + Number(r.maternity_employee),
              render: (r) => amount(Number(r.pension_employee) + Number(r.maternity_employee)),
            },
            {
              key: "cbhi",
              header: "CBHI",
              align: "right",
              numeric: true,
              value: (r) => Number(r.cbhi),
              render: (r) => amount(r.cbhi),
            },
            {
              key: "loans_advances",
              header: "Loans",
              align: "right",
              numeric: true,
              value: (r) => Number(r.loans_advances),
              render: (r) =>
                Number(r.loans_advances) > 0 ? (
                  amount(r.loans_advances)
                ) : (
                  <span className="text-ink-400">—</span>
                ),
            },
            {
              key: "net_pay",
              header: "Net pay",
              align: "right",
              numeric: true,
              value: (r) => Number(r.net_pay),
              render: (r) => <span className="font-semibold">{amount(r.net_pay)}</span>,
            },
            {
              key: "employer_cost",
              header: "Employer cost",
              align: "right",
              numeric: true,
              value: (r) => Number(r.pension_employer) + Number(r.maternity_employer),
              render: (r) => amount(Number(r.pension_employer) + Number(r.maternity_employer)),
            },
            {
              key: "payslip",
              header: "Payslip",
              align: "right",
              fixed: true,
              sortable: false,
              render: (r) =>
                r.payslip_document_id ? (
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
                ),
            },
          ]}
        />
      </Section>

      <Section title="Run detail">
        <Facts
          rows={[
            ["Created", dateTime(run.created_at)],
            ["Created by", run.created_by_name ?? "—"],
            ["Approved", dateTime(run.approved_at)],
            ["Approved by", run.approved_by_name ?? "—"],
            ["Employees", run.records.length],
            ["Total net", money(run.total_net_pay)],
          ]}
        />
      </Section>
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

export function PayrollPage() {
  const { orgId } = useDefaultOrg();
  const [open, setOpen] = useState<PayrollRun | null>(null);
  const [creating, setCreating] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["payroll-runs", orgId],
    queryFn: () =>
      api<Paginated<PayrollRun>>(`/api/hr/payroll-runs/?organization=${orgId}&page_size=200`),
    enabled: Boolean(orgId),
  });

  const rows = data?.results ?? [];
  const current = open ? (rows.find((r) => r.id === open.id) ?? open) : null;

  return (
    <div>
      <PageHeader
        title="Payroll"
        action={
          <Button disabled={!orgId} onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" /> Run payroll
          </Button>
        }
      />

      <DataGrid<PayrollRun>
        rows={rows}
        loading={isLoading}
        getRowId={(r) => r.id}
        storageKey="payroll-runs"
        exportName="payroll-runs"
        searchPlaceholder="Search runs by period or approver…"
        emptyMessage="No payroll runs yet."
        onRowClick={(r) => setOpen(r)}
        columns={[
          {
            key: "period",
            header: "Period",
            value: (r) => r.period_start,
            render: (r) => (
              <div>
                <div className="font-medium text-ink-900">
                  {r.period_start} – {r.period_end}
                </div>
                <div className="text-xs text-ink-500">{r.organization_name}</div>
              </div>
            ),
          },
          {
            key: "status",
            header: "Status",
            value: (r) => r.status,
            render: (r) => <StatusBadge status={r.status} />,
          },
          {
            key: "headcount",
            header: "Employees",
            align: "right",
            numeric: true,
            value: (r) => r.records.length,
          },
          {
            key: "gross",
            header: "Gross",
            align: "right",
            numeric: true,
            value: (r) => r.records.reduce((s, x) => s + Number(x.gross), 0),
            render: (r) => money(r.records.reduce((s, x) => s + Number(x.gross), 0)),
          },
          {
            key: "deductions",
            header: "Deductions",
            align: "right",
            numeric: true,
            value: (r) =>
              r.records.reduce(
                (s, x) =>
                  s +
                  Number(x.paye) +
                  Number(x.pension_employee) +
                  Number(x.maternity_employee) +
                  Number(x.cbhi),
                0,
              ),
            render: (r) =>
              money(
                r.records.reduce(
                  (s, x) =>
                    s +
                    Number(x.paye) +
                    Number(x.pension_employee) +
                    Number(x.maternity_employee) +
                    Number(x.cbhi),
                  0,
                ),
              ),
          },
          {
            key: "total_net_pay",
            header: "Net pay",
            align: "right",
            numeric: true,
            value: (r) => Number(r.total_net_pay),
            render: (r) => <span className="font-semibold">{money(r.total_net_pay)}</span>,
          },
          {
            key: "approved_by_name",
            header: "Approved by",
            value: (r) => r.approved_by_name ?? "—",
            render: (r) =>
              r.approved_by_name ? (
                r.approved_by_name
              ) : r.status === "PENDING_APPROVAL" ? (
                <Badge tone="warning">awaiting</Badge>
              ) : (
                <span className="text-ink-400">—</span>
              ),
          },
        ]}
      />

      {creating && <NewRunDrawer orgId={orgId} onClose={() => setCreating(false)} />}
      {current && <RunDrawer run={current} onClose={() => setOpen(null)} />}
    </div>
  );
}
