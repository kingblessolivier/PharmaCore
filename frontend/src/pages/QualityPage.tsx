/* -------------------------------------------------------------------------- */
/* Quality: what went wrong, why, and what was done about it.                 */
/*                                                                            */
/* Complaints, deviations and adverse events are one list because the         */
/* questions people ask cut across them — what is open on this batch, what is */
/* overdue, what have we told the regulator. Three separate screens would     */
/* make each of those a manual union.                                         */
/*                                                                            */
/* The screen leads with the workload rather than the list, because the first */
/* question a quality officer has on a Monday is not "what exists" but "what  */
/* is late".                                                                  */
/* -------------------------------------------------------------------------- */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardList,
  FlaskConical,
  Plus,
  ShieldAlert,
} from "lucide-react";
import { Badge, Button, Card, PageHeader, SelectField, TextArea, TextField } from "../components/ui";
import { DataGrid } from "../components/DataGrid";
import { Drawer, ErrorNote, Field, Grid, Section } from "../components/RecordKit";
import { api, ApiError } from "../lib/api";
import { dateTime, shortDate } from "../lib/format";
import { useDefaultOrg } from "../lib/recordData";
import type { Paginated } from "../lib/types";

interface CapaAction {
  id: number;
  kind: string;
  kind_display: string;
  status: string;
  status_display: string;
  description: string;
  owner_name: string;
  due_date: string | null;
  is_overdue: boolean;
  completion_note: string;
  effectiveness_note: string;
  verified_by_name: string;
}

interface QualityCase {
  id: number;
  case_number: string;
  kind: string;
  kind_display: string;
  source: string;
  severity: string;
  severity_display: string;
  status: string;
  status_display: string;
  title: string;
  description: string;
  product_name: string;
  batch_label: string;
  owner_name: string;
  due_date: string | null;
  investigation: string;
  root_cause: string;
  is_reportable: boolean;
  reported_to_regulator_at: string | null;
  regulator_reference: string;
  outstanding_actions: number;
  actions: CapaAction[];
  closure_note: string;
  created_at: string;
}

interface Workload {
  open_cases: number;
  by_kind: Record<string, number>;
  critical: number;
  overdue_cases: number;
  open_actions: number;
  overdue_actions: number;
  awaiting_regulator_report: number;
}

/** Severity in words and weight, never colour alone. */
function SeverityChip({ value }: { value: string }) {
  const tone = value === "CRITICAL" ? "danger" : value === "MAJOR" ? "warning" : "neutral";
  return <Badge tone={tone}>{value === "CRITICAL" ? "Critical" : value === "MAJOR" ? "Major" : "Minor"}</Badge>;
}

function Tile({
  label,
  value,
  hint,
  urgent,
}: {
  label: string;
  value: number;
  hint?: string;
  urgent?: boolean;
}) {
  return (
    <Card className="p-4">
      <div className="text-[12px] text-ink-500">{label}</div>
      <div
        className={`mt-1 text-[24px] font-semibold tabular-nums ${
          urgent && value > 0 ? "text-danger-700" : "text-ink-900"
        }`}
      >
        {value.toLocaleString()}
      </div>
      {hint && <div className="mt-0.5 text-[11px] text-ink-500">{hint}</div>}
    </Card>
  );
}

export function QualityPage() {
  const { orgId } = useDefaultOrg();
  const qc = useQueryClient();
  const [kind, setKind] = useState("");
  const [openOnly, setOpenOnly] = useState(true);
  const [open, setOpen] = useState<QualityCase | null>(null);
  const [raising, setRaising] = useState(false);

  const params = new URLSearchParams();
  if (kind) params.set("kind", kind);
  if (openOnly) params.set("open", "true");
  const qs = params.toString();

  const cases = useQuery({
    queryKey: ["quality-cases", qs],
    queryFn: () => api<Paginated<QualityCase>>(`/api/quality/cases/${qs ? `?${qs}` : ""}`),
  });
  const workload = useQuery({
    queryKey: ["quality-workload", orgId],
    enabled: orgId != null,
    queryFn: () => api<Workload>(`/api/quality/cases/workload/?organization=${orgId ?? 0}`),
  });

  const rows = cases.data?.results ?? [];
  const w = workload.data;

  /* The case in the drawer, taken from the freshly fetched list so an action
     added inside it is visible without closing and reopening. */
  const current = open ? (rows.find((r) => r.id === open.id) ?? open) : null;
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["quality-cases"] });
    void qc.invalidateQueries({ queryKey: ["quality-workload"] });
  };

  return (
    <div>
      <PageHeader
        title="Quality"
        subtitle="Complaints, deviations and adverse events — and the actions that closed them."
        action={
          <Button onClick={() => setRaising(true)}>
            <Plus size={16} strokeWidth={1.8} /> Raise a case
          </Button>
        }
      />

      {w && (
        <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <Tile label="Open cases" value={w.open_cases} />
          <Tile label="Critical" value={w.critical} urgent hint="Patient safety or licence" />
          <Tile label="Open actions" value={w.open_actions} />
          <Tile label="Overdue actions" value={w.overdue_actions} urgent hint="Past their due date" />
          <Tile
            label="To report"
            value={w.awaiting_regulator_report}
            urgent
            hint="Reportable, not yet sent"
          />
        </div>
      )}

      <div className="mb-3 flex flex-wrap items-end gap-3">
        <div className="w-56">
          <SelectField label="Kind" value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="">All kinds</option>
            <option value="COMPLAINT">Complaints</option>
            <option value="DEVIATION">Deviations</option>
            <option value="ADVERSE_EVENT">Adverse events</option>
          </SelectField>
        </div>
        <label className="flex h-9 items-center gap-2 text-[13px] text-ink-700">
          <input
            type="checkbox"
            checked={openOnly}
            onChange={(e) => setOpenOnly(e.target.checked)}
            className="h-4 w-4 rounded border-chrome-600"
          />
          Open only
        </label>
      </div>

      <DataGrid<QualityCase>
        rows={rows}
        getRowId={(r) => r.id}
        loading={cases.isLoading}
        storageKey="quality-cases"
        exportName="quality-cases"
        searchPlaceholder="Search by case number, title, product or batch…"
        emptyMessage="No quality cases. That is either very good news or nobody is reporting."
        onRowClick={(r) => setOpen(r)}
        columns={[
          {
            key: "case_number",
            header: "Case",
            value: (r) => r.case_number,
            render: (r) => <span className="font-mono text-[12px]">{r.case_number}</span>,
          },
          { key: "kind_display", header: "Kind", value: (r) => r.kind_display },
          { key: "title", header: "What happened", value: (r) => r.title },
          {
            key: "severity",
            header: "Severity",
            value: (r) => r.severity,
            render: (r) => <SeverityChip value={r.severity} />,
          },
          { key: "status_display", header: "Status", value: (r) => r.status_display },
          {
            key: "outstanding_actions",
            header: "Open actions",
            numeric: true,
            align: "right",
            value: (r) => r.outstanding_actions,
          },
          {
            key: "product_name",
            header: "Product",
            defaultHidden: true,
            value: (r) => r.product_name || "—",
          },
          {
            key: "batch_label",
            header: "Batch",
            defaultHidden: true,
            value: (r) => r.batch_label || "—",
          },
          {
            key: "is_reportable",
            header: "Regulator",
            value: (r) =>
              r.reported_to_regulator_at ? "Reported" : r.is_reportable ? "To report" : "—",
            render: (r) =>
              r.reported_to_regulator_at ? (
                <span className="inline-flex items-center gap-1 text-[12px] text-success-700">
                  <CheckCircle2 size={13} strokeWidth={1.8} /> {r.regulator_reference}
                </span>
              ) : r.is_reportable ? (
                <span className="inline-flex items-center gap-1 text-[12px] font-medium text-warning-700">
                  <ShieldAlert size={13} strokeWidth={1.8} /> To report
                </span>
              ) : (
                <span className="text-ink-400">—</span>
              ),
          },
          {
            key: "created_at",
            header: "Raised",
            value: (r) => r.created_at,
            render: (r) => shortDate(r.created_at),
          },
        ]}
      />

      {current && <CaseDrawer item={current} onClose={() => setOpen(null)} onChanged={refresh} />}
      {raising && (
        <RaiseDrawer
          orgId={orgId}
          onClose={() => setRaising(false)}
          onCreated={() => {
            setRaising(false);
            refresh();
          }}
        />
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */

function RaiseDrawer({
  orgId,
  onClose,
  onCreated,
}: {
  orgId: number | null;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [kind, setKind] = useState("COMPLAINT");
  const [severity, setSeverity] = useState("MINOR");
  const [source, setSource] = useState("PATIENT");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [batchNumber, setBatchNumber] = useState("");
  const [reaction, setReaction] = useState("");

  const create = useMutation({
    mutationFn: () =>
      api("/api/quality/cases/", {
        method: "POST",
        body: JSON.stringify({
          organization: orgId,
          kind,
          severity,
          source,
          title,
          description,
          batch_number: batchNumber,
          // Only an adverse event carries clinical detail; sending it on a
          // complaint is refused by the server, deliberately.
          ...(kind === "ADVERSE_EVENT" ? { adverse_event: { reaction } } : {}),
        }),
      }),
    onSuccess: onCreated,
  });

  return (
    <Drawer
      title="Raise a quality case"
      subtitle="Anyone can report. Deciding one needs quality authority."
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={() => create.mutate()}
            disabled={create.isPending || !title.trim() || !description.trim()}
          >
            {create.isPending ? "Raising…" : "Raise case"}
          </Button>
        </>
      }
    >
      <Section title="What kind of case">
        <Grid>
          <Field label="Kind">
            <SelectField value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="COMPLAINT">Complaint — somebody reported a problem</option>
              <option value="DEVIATION">Deviation — we departed from procedure</option>
              <option value="ADVERSE_EVENT">Adverse event — a patient was harmed</option>
            </SelectField>
          </Field>
          <Field
            label="Severity"
            hint="Critical means patient safety or the licence is at risk. Keep the word for that."
          >
            <SelectField value={severity} onChange={(e) => setSeverity(e.target.value)}>
              <option value="MINOR">Minor</option>
              <option value="MAJOR">Major</option>
              <option value="CRITICAL">Critical</option>
            </SelectField>
          </Field>
          <Field label="Where it came from">
            <SelectField value={source} onChange={(e) => setSource(e.target.value)}>
              <option value="PATIENT">Patient or customer</option>
              <option value="PHARMACY">Pharmacy or customer organisation</option>
              <option value="INTERNAL">Staff</option>
              <option value="SUPPLIER">Supplier</option>
              <option value="INSPECTION">Inspection or audit</option>
              <option value="EXCURSION">Temperature excursion</option>
            </SelectField>
          </Field>
          <Field label="Batch number" hint="Even one we never held — a patient's pack still has a lot.">
            <TextField value={batchNumber} onChange={(e) => setBatchNumber(e.target.value)} />
          </Field>
        </Grid>
      </Section>

      <Section title="What happened">
        <TextField
          label="Title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Short enough to find later"
        />
        <div className="mt-2">
          <TextArea
            label="Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={4}
            placeholder="What was seen, when, and by whom."
          />
        </div>
        {kind === "ADVERSE_EVENT" && (
          <div className="mt-2">
            <TextArea
              label="Reaction"
              value={reaction}
              onChange={(e) => setReaction(e.target.value)}
              rows={3}
              placeholder="In the reporter's own words."
            />
          </div>
        )}
      </Section>

      {create.isError && <ErrorNote error={create.error} />}
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

function CaseDrawer({
  item,
  onClose,
  onChanged,
}: {
  item: QualityCase;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [investigation, setInvestigation] = useState(item.investigation);
  const [rootCause, setRootCause] = useState(item.root_cause);
  const [actionText, setActionText] = useState("");
  const [actionKind, setActionKind] = useState("CORRECTIVE");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  const call = (path: string, body: Record<string, unknown>) =>
    api(path, { method: "POST", body: JSON.stringify(body) });

  const run = useMutation({
    mutationFn: ({ path, body }: { path: string; body: Record<string, unknown> }) =>
      call(path, body),
    onSuccess: () => {
      setError(null);
      onChanged();
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "That did not go through."),
  });

  const hasPreventive = item.actions.some((a) => a.kind === "PREVENTIVE");
  const needsPreventive =
    (item.severity === "CRITICAL" || item.severity === "MAJOR") && !hasPreventive;

  return (
    <Drawer
      title={item.case_number}
      subtitle={item.title}
      badge={<SeverityChip value={item.severity} />}
      onClose={onClose}
      width="max-w-4xl"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
          <Button
            onClick={() =>
              run.mutate({ path: `/api/quality/cases/${item.id}/close/`, body: { note } })
            }
            disabled={run.isPending || item.status === "CLOSED"}
          >
            {item.status === "CLOSED" ? "Closed" : "Close case"}
          </Button>
        </>
      }
    >
      <Section title="What happened">
        <p className="whitespace-pre-wrap text-[13px] text-ink-800">{item.description}</p>
        <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1 text-[12px]">
          {[
            ["Status", item.status_display],
            ["Kind", item.kind_display],
            ["Product", item.product_name || "—"],
            ["Batch", item.batch_label || "—"],
            ["Raised", dateTime(item.created_at)],
            ["Owner", item.owner_name || "unassigned"],
          ].map(([k, v]) => (
            <div key={k} className="flex justify-between gap-3">
              <dt className="text-ink-500">{k}</dt>
              <dd className="text-right font-medium text-ink-800">{v}</dd>
            </div>
          ))}
        </dl>
      </Section>

      <Section
        title="Investigation"
        hint="A case cannot be closed without a root cause — that is what an inspector reads first."
      >
        <TextArea
          label="What was found"
          value={investigation}
          onChange={(e) => setInvestigation(e.target.value)}
          rows={3}
        />
        <div className="mt-2">
          <TextArea
            label="Root cause"
            value={rootCause}
            onChange={(e) => setRootCause(e.target.value)}
            rows={2}
            placeholder="Why it was possible — not who did it."
          />
        </div>
        <div className="mt-2 flex justify-end">
          <Button
            variant="secondary"
            onClick={() =>
              run.mutate({
                path: `/api/quality/cases/${item.id}/investigate/`,
                body: { investigation, root_cause: rootCause },
              })
            }
            disabled={run.isPending || !rootCause.trim()}
          >
            Record investigation
          </Button>
        </div>
      </Section>

      <Section title="Actions" hint="Corrective fixes this. Preventive stops the next one.">
        {needsPreventive && (
          <p className="mb-2 flex items-start gap-1.5 text-[12px] text-warning-700">
            <AlertTriangle size={14} strokeWidth={1.8} className="mt-0.5 shrink-0" />
            A {item.severity === "CRITICAL" ? "critical" : "major"} case needs a preventive action
            before it can close. Corrective actions alone fix this occurrence and leave the cause in
            place.
          </p>
        )}

        <ul className="divide-y divide-line rounded-lg border border-chrome-500">
          {item.actions.map((a) => (
            <li key={a.id} className="px-3 py-2">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-[13px] text-ink-900">{a.description}</div>
                  <div className="mt-0.5 flex flex-wrap items-center gap-2 text-[11px] text-ink-500">
                    <span className="inline-flex items-center gap-1">
                      {a.kind === "PREVENTIVE" ? (
                        <FlaskConical size={12} strokeWidth={1.8} />
                      ) : (
                        <ClipboardList size={12} strokeWidth={1.8} />
                      )}
                      {a.kind_display.split(" —")[0]}
                    </span>
                    <span>{a.status_display}</span>
                    {a.owner_name && <span>· {a.owner_name}</span>}
                    {a.due_date && (
                      <span className={a.is_overdue ? "font-semibold text-danger-700" : ""}>
                        · due {shortDate(a.due_date)}
                        {a.is_overdue && " (overdue)"}
                      </span>
                    )}
                  </div>
                  {a.effectiveness_note && (
                    <div className="mt-1 text-[11px] text-ink-600">
                      Verification: {a.effectiveness_note}
                      {a.verified_by_name && ` — ${a.verified_by_name}`}
                    </div>
                  )}
                </div>
                <div className="flex shrink-0 gap-1">
                  {a.status === "OPEN" && (
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() =>
                        run.mutate({ path: `/api/quality/actions/${a.id}/complete/`, body: {} })
                      }
                    >
                      Done
                    </Button>
                  )}
                  {a.status === "DONE" && (
                    <>
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() =>
                          run.mutate({
                            path: `/api/quality/actions/${a.id}/verify/`,
                            body: { effective: true },
                          })
                        }
                      >
                        Effective
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() =>
                          run.mutate({
                            path: `/api/quality/actions/${a.id}/verify/`,
                            body: { effective: false, note: "Did not hold." },
                          })
                        }
                      >
                        Not effective
                      </Button>
                    </>
                  )}
                </div>
              </div>
            </li>
          ))}
          {item.actions.length === 0 && (
            <li className="px-3 py-3 text-[13px] text-ink-500">No actions yet.</li>
          )}
        </ul>

        <div className="mt-2 flex items-end gap-2">
          <div className="w-44">
            <SelectField
              label="Kind"
              value={actionKind}
              onChange={(e) => setActionKind(e.target.value)}
            >
              <option value="IMMEDIATE">Immediate containment</option>
              <option value="CORRECTIVE">Corrective</option>
              <option value="PREVENTIVE">Preventive</option>
            </SelectField>
          </div>
          <div className="flex-1">
            <TextField
              label="What will be done"
              value={actionText}
              onChange={(e) => setActionText(e.target.value)}
            />
          </div>
          <Button
            variant="secondary"
            onClick={() => {
              run.mutate({
                path: `/api/quality/cases/${item.id}/add-action/`,
                body: { description: actionText, kind: actionKind },
              });
              setActionText("");
            }}
            disabled={run.isPending || !actionText.trim()}
          >
            Add
          </Button>
        </div>
      </Section>

      {item.is_reportable && !item.reported_to_regulator_at && (
        <Section
          title="Regulator"
          hint="Record the reference they gave you — “we reported it” is a claim somebody will have to evidence."
        >
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <TextField
                label="Reference"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="e.g. RFDA/PV/2026/0142"
              />
            </div>
            <Button
              variant="secondary"
              onClick={() =>
                run.mutate({
                  path: `/api/quality/cases/${item.id}/report-to-regulator/`,
                  body: { reference: note },
                })
              }
              disabled={run.isPending || !note.trim()}
            >
              Record report
            </Button>
          </div>
        </Section>
      )}

      {error && <p className="mt-2 text-[13px] text-danger-700">{error}</p>}
    </Drawer>
  );
}
