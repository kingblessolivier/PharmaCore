import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Banknote, FileCheck2, Sparkles } from "lucide-react";
import { useState } from "react";
import { DataGrid } from "../components/DataGrid";
import {
  Drawer,
  Empty,
  ErrorNote,
  Facts,
  Field,
  Grid,
  Input,
  Section,
  Select,
  StatusBadge,
} from "../components/RecordKit";
import { Badge, Button, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { amount, money, num } from "../lib/format";
import { FILING_KINDS, type StatutoryFiling } from "../lib/people";
import { useDefaultOrg } from "../lib/recordData";
import type { Paginated } from "../lib/types";

function lastMonth() {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth() - 1, 1);
  const end = new Date(now.getFullYear(), now.getMonth(), 0);
  return { start: start.toISOString().slice(0, 10), end: end.toISOString().slice(0, 10) };
}

/* -------------------------------------------------------------------------- */

function GenerateDrawer({ orgId, onClose }: { orgId: number | null; onClose: () => void }) {
  const qc = useQueryClient();
  const bounds = lastMonth();
  const [kind, setKind] = useState("PAYE_MONTHLY");
  const [start, setStart] = useState(bounds.start);
  const [end, setEnd] = useState(bounds.end);

  const generate = useMutation({
    mutationFn: () =>
      api<StatutoryFiling>("/api/hr/filings/generate/", {
        method: "POST",
        body: JSON.stringify({
          organization: orgId,
          kind,
          period_start: start,
          period_end: end,
        }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["filings"] });
      onClose();
    },
  });

  return (
    <Drawer
      title="Generate a statutory return"
      onClose={onClose}
      width="max-w-xl"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={generate.isPending} onClick={() => generate.mutate()}>
            <Sparkles className="h-3.5 w-3.5" />
            {generate.isPending ? "Generating…" : "Generate"}
          </Button>
        </>
      }
    >
      <ErrorNote error={generate.error} />
      <Section title="Return">
        <div className="grid grid-cols-1 gap-3">
          <Field label="Filing">
            <Select value={kind} onChange={(e) => setKind(e.target.value)}>
              {FILING_KINDS.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </Select>
          </Field>
        </div>
        <div className="mt-3">
          <Grid cols={2}>
            <Field label="Period from">
              <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
            </Field>
            <Field label="Period to">
              <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
            </Field>
          </Grid>
        </div>
        <p className="mt-3 text-xs text-ink-500">
          PAYE, RSSB and CBHI are due on the 15th of the following month; the annual PIT summary on
          31 March. A return that does not tie to its sub-ledger balance can be generated, but not
          filed.
        </p>
      </Section>
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

export function StatutoryFilingsPage() {
  const qc = useQueryClient();
  const { orgId } = useDefaultOrg();
  const [kind, setKind] = useState("");
  const [generating, setGenerating] = useState(false);
  const [open, setOpen] = useState<StatutoryFiling | null>(null);
  const [reference, setReference] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["filings", kind],
    queryFn: () =>
      api<Paginated<StatutoryFiling>>(
        `/api/hr/filings/?page_size=200${kind ? `&kind=${kind}` : ""}`,
      ),
  });

  const act = useMutation({
    mutationFn: ({ id, verb, body }: { id: number; verb: string; body?: object }) =>
      api(`/api/hr/filings/${id}/${verb}/`, {
        method: "POST",
        body: JSON.stringify(body ?? {}),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["filings"] });
      setReference("");
    },
  });

  const rows = data?.results ?? [];
  const current = open ? (rows.find((f) => f.id === open.id) ?? open) : null;
  const lines = current?.payload?.lines ?? [];

  return (
    <div>
      <PageHeader
        title="Statutory filings"
        action={
          <Button disabled={!orgId} onClick={() => setGenerating(true)}>
            <Sparkles className="h-4 w-4" /> Generate return
          </Button>
        }
      />

      <DataGrid<StatutoryFiling>
        rows={rows}
        loading={isLoading}
        getRowId={(f) => f.id}
        storageKey="statutory-filings"
        exportName="statutory-filings"
        searchPlaceholder="Search by reference, kind, period…"
        emptyMessage="No returns generated yet."
        onRowClick={(f) => setOpen(f)}
        toolbar={
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value)}
            className="rounded-md border border-line bg-surface-0 px-2.5 py-1.5 text-xs font-medium text-ink-700"
            aria-label="Filter by filing kind"
          >
            <option value="">All filings</option>
            {FILING_KINDS.map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        }
        columns={[
          {
            key: "kind_display",
            header: "Filing",
            render: (f) => (
              <div>
                <div className="font-medium text-ink-900">{f.kind_display}</div>
                <div className="font-mono text-xs text-ink-500">{f.reference || `#${f.id}`}</div>
              </div>
            ),
          },
          {
            key: "period",
            header: "Period",
            value: (f) => f.period_start,
            render: (f) => `${f.period_start} → ${f.period_end}`,
          },
          {
            key: "due_date",
            header: "Due",
            value: (f) => f.due_date,
            render: (f) =>
              f.is_overdue ? <Badge tone="danger">{f.due_date}</Badge> : <span>{f.due_date}</span>,
          },
          {
            key: "employee_count",
            header: "Staff",
            align: "right",
            numeric: true,
            value: (f) => f.employee_count,
          },
          {
            key: "amount_due",
            header: "Amount due",
            align: "right",
            numeric: true,
            value: (f) => num(f.amount_due),
            render: (f) => <span className="font-semibold">{money(f.amount_due)}</span>,
          },
          {
            key: "ties_to_ledger",
            header: "Ledger",
            value: (f) => (f.ties_to_ledger ? "Ties" : "Mismatch"),
            render: (f) =>
              f.ties_to_ledger ? (
                <Badge tone="success">Ties</Badge>
              ) : (
                <Badge tone="danger">Mismatch</Badge>
              ),
          },
          {
            key: "status",
            header: "Status",
            value: (f) => f.status,
            render: (f) => <StatusBadge status={f.status} label={f.status_display} />,
          },
        ]}
      />

      {generating && <GenerateDrawer orgId={orgId} onClose={() => setGenerating(false)} />}

      {current && (
        <Drawer
          title={`${current.kind_display} · ${current.period_start} – ${current.period_end}`}
          badge={<StatusBadge status={current.status} label={current.status_display} />}
          subtitle={`${current.reference || `#${current.id}`} · due ${current.due_date}`}
          onClose={() => setOpen(null)}
          width="max-w-5xl"
          footer={
            <>
              {current.status === "FILED" && (
                <Button
                  variant="secondary"
                  disabled={act.isPending}
                  onClick={() => act.mutate({ id: current.id, verb: "mark-paid" })}
                >
                  <Banknote className="h-3.5 w-3.5" /> Record payment
                </Button>
              )}
              {["GENERATED", "DRAFT"].includes(current.status) && (
                <Button
                  disabled={act.isPending || !current.ties_to_ledger}
                  onClick={() =>
                    act.mutate({
                      id: current.id,
                      verb: "mark-filed",
                      body: { authority_reference: reference },
                    })
                  }
                >
                  <FileCheck2 className="h-3.5 w-3.5" /> Mark filed
                </Button>
              )}
              <Button variant="secondary" onClick={() => setOpen(null)}>
                Close
              </Button>
            </>
          }
        >
          <ErrorNote error={act.error} />

          {!current.ties_to_ledger && (
            <div className="mb-4 flex items-start gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>
                The return says <strong>{money(current.amount_due)}</strong> but the GL sub-ledger
                holds <strong>{money(current.gl_balance_at_generation)}</strong>. Reconcile the
                difference before filing — the return cannot be marked filed while they disagree.
              </span>
            </div>
          )}

          <Section title="Return">
            <Facts
              rows={[
                ["Employees", current.employee_count],
                ["Gross total", money(current.gross_total)],
                ["Employee contribution", money(current.employee_contribution)],
                ["Employer contribution", money(current.employer_contribution)],
                ["Amount due", money(current.amount_due)],
                ["GL sub-ledger", money(current.gl_balance_at_generation)],
                [
                  "Sub-ledger accounts",
                  (current.payload?.sub_ledger_accounts ?? []).join(", ") || "—",
                ],
                ["Authority reference", current.authority_reference || "—"],
                ["Filed on", current.filed_on ?? "—"],
              ]}
            />
            {["GENERATED", "DRAFT"].includes(current.status) && (
              <div className="mt-3 max-w-sm">
                <Field label="Authority reference" hint="RRA / RSSB acknowledgement number.">
                  <Input value={reference} onChange={(e) => setReference(e.target.value)} />
                </Field>
              </div>
            )}
          </Section>

          <Section title="Return lines" hint="Exactly what will be uploaded.">
            {lines.length === 0 ? (
              <Empty message="No payroll records in this period." />
            ) : (
              <div className="max-h-80 overflow-auto rounded-lg border border-line">
                <table className="w-full min-w-[760px] text-sm">
                  <thead className="sticky top-0 border-b border-line bg-surface-50 text-left text-[11px] text-ink-500">
                    <tr>
                      <th className="px-2.5 py-2">Employee</th>
                      <th className="px-2.5 py-2">RSSB no.</th>
                      <th className="px-2.5 py-2">TIN</th>
                      <th className="px-2.5 py-2 text-right">Gross</th>
                      <th className="px-2.5 py-2 text-right">PAYE</th>
                      <th className="px-2.5 py-2 text-right">Pension EE</th>
                      <th className="px-2.5 py-2 text-right">Pension ER</th>
                      <th className="px-2.5 py-2 text-right">CBHI</th>
                      <th className="px-2.5 py-2 text-right">Net</th>
                    </tr>
                  </thead>
                  <tbody>
                    {lines.map((l, i) => (
                      <tr key={i} className="border-b border-line last:border-0">
                        <td className="px-2.5 py-1.5">
                          <div>{l.employee_name}</div>
                          <div className="font-mono text-xs text-ink-500">{l.employee_number}</div>
                        </td>
                        <td className="px-2.5 py-1.5 font-mono text-xs">{l.rssb_number || "—"}</td>
                        <td className="px-2.5 py-1.5 font-mono text-xs">{l.tin || "—"}</td>
                        <td className="px-2.5 py-1.5 text-right tabular-nums">{amount(l.gross)}</td>
                        <td className="px-2.5 py-1.5 text-right tabular-nums">{amount(l.paye)}</td>
                        <td className="px-2.5 py-1.5 text-right tabular-nums">
                          {amount(l.pension_employee)}
                        </td>
                        <td className="px-2.5 py-1.5 text-right tabular-nums">
                          {amount(l.pension_employer)}
                        </td>
                        <td className="px-2.5 py-1.5 text-right tabular-nums">{amount(l.cbhi)}</td>
                        <td className="px-2.5 py-1.5 text-right font-medium tabular-nums">
                          {amount(l.net_pay)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Section>
        </Drawer>
      )}
    </div>
  );
}
