/* -------------------------------------------------------------------------- */
/* Internal audit.                                                            */
/*                                                                            */
/* Not the audit log — that records what happened. This records somebody      */
/* deliberately going to check whether a part of the business does what it    */
/* says: a branch's stock accuracy, a supplier's paperwork, whether the cold  */
/* chain SOP is actually followed.                                            */
/*                                                                            */
/* A serious finding raises a quality case, so its corrective and preventive  */
/* work runs through the same CAPA lifecycle as everything else. An audit that */
/* closes its own findings on assertion is the usual failure, and the screen  */
/* makes that link visible: every major finding shows the case number it      */
/* raised and whether that case is still open.                                 */
/* -------------------------------------------------------------------------- */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { AlertTriangle, ClipboardCheck, Plus } from "lucide-react";
import { Badge, Button, PageHeader, SelectField, TextArea, TextField } from "../components/ui";
import { DataGrid } from "../components/DataGrid";
import { Drawer, ErrorNote, Field, Grid, Section } from "../components/RecordKit";
import { api, ApiError } from "../lib/api";
import { shortDate } from "../lib/format";
import { useDefaultOrg } from "../lib/recordData";
import type { Paginated } from "../lib/types";

interface Finding {
  id: number;
  severity: string;
  severity_display: string;
  status: string;
  status_display: string;
  observation: string;
  requirement: string;
  management_response: string;
  case_number: string;
  case_status: string;
}

interface Engagement {
  id: number;
  reference: string;
  kind: string;
  kind_display: string;
  status: string;
  status_display: string;
  title: string;
  scope: string;
  subject_name: string;
  lead_auditor_name: string;
  planned_for: string | null;
  completed_at: string | null;
  summary: string;
  open_findings: number;
  findings: Finding[];
}

function SeverityChip({ value }: { value: string }) {
  const tone = value === "CRITICAL" ? "danger" : value === "MAJOR" ? "warning" : "neutral";
  const label = value === "CRITICAL" ? "Critical" : value === "MAJOR" ? "Major" : "Minor";
  return <Badge tone={tone}>{label}</Badge>;
}

export function InternalAuditPage() {
  const { orgId } = useDefaultOrg();
  const qc = useQueryClient();
  const [openOnly, setOpenOnly] = useState(true);
  const [open, setOpen] = useState<Engagement | null>(null);
  const [planning, setPlanning] = useState(false);

  const audits = useQuery({
    queryKey: ["audits", openOnly],
    queryFn: () =>
      api<Paginated<Engagement>>(`/api/quality/audits/${openOnly ? "?open=true" : ""}`),
  });
  const rows = audits.data?.results ?? [];
  const current = open ? (rows.find((r) => r.id === open.id) ?? open) : null;
  const refresh = () => void qc.invalidateQueries({ queryKey: ["audits"] });

  return (
    <div>
      <PageHeader
        title="Internal audit"
        subtitle="Planned checks that the business does what it says — and the actions its findings raised."
        action={
          <Button onClick={() => setPlanning(true)}>
            <Plus size={16} strokeWidth={1.8} /> Plan an audit
          </Button>
        }
      />

      <label className="mb-3 flex items-center gap-2 text-[13px] text-ink-700">
        <input
          type="checkbox"
          checked={openOnly}
          onChange={(e) => setOpenOnly(e.target.checked)}
          className="h-4 w-4 rounded border-chrome-600"
        />
        Open only
      </label>

      <DataGrid<Engagement>
        rows={rows}
        getRowId={(r) => r.id}
        loading={audits.isLoading}
        storageKey="audits"
        exportName="internal-audits"
        searchPlaceholder="Search by reference, title or subject…"
        emptyMessage="No audits planned."
        onRowClick={(r) => setOpen(r)}
        columns={[
          {
            key: "reference",
            header: "Reference",
            value: (r) => r.reference,
            render: (r) => <span className="font-mono text-[12px]">{r.reference}</span>,
          },
          { key: "title", header: "What is being checked", value: (r) => r.title },
          { key: "kind_display", header: "Kind", value: (r) => r.kind_display },
          { key: "subject_name", header: "Subject", value: (r) => r.subject_name },
          { key: "status_display", header: "Status", value: (r) => r.status_display },
          {
            key: "open_findings",
            header: "Open findings",
            numeric: true,
            align: "right",
            value: (r) => r.open_findings,
            render: (r) =>
              r.open_findings > 0 ? (
                <span className="font-semibold text-warning-700">{r.open_findings}</span>
              ) : (
                <span className="text-ink-500">0</span>
              ),
          },
          {
            key: "planned_for",
            header: "Planned",
            value: (r) => r.planned_for ?? "",
            render: (r) => (r.planned_for ? shortDate(r.planned_for) : "—"),
          },
          {
            key: "lead_auditor_name",
            header: "Lead",
            defaultHidden: true,
            value: (r) => r.lead_auditor_name || "—",
          },
        ]}
      />

      {current && <AuditDrawer item={current} onClose={() => setOpen(null)} onChanged={refresh} />}
      {planning && (
        <PlanAudit
          orgId={orgId}
          onClose={() => setPlanning(false)}
          onCreated={() => {
            setPlanning(false);
            refresh();
          }}
        />
      )}
    </div>
  );
}

function PlanAudit({
  orgId,
  onClose,
  onCreated,
}: {
  orgId: number | null;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [title, setTitle] = useState("");
  const [scope, setScope] = useState("");
  const [kind, setKind] = useState("SELF_INSPECTION");
  const [plannedFor, setPlannedFor] = useState("");

  const create = useMutation({
    mutationFn: () =>
      api("/api/quality/audits/", {
        method: "POST",
        body: JSON.stringify({
          organization: orgId,
          title,
          scope,
          kind,
          planned_for: plannedFor || null,
        }),
      }),
    onSuccess: onCreated,
  });

  return (
    <Drawer
      title="Plan an audit"
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={() => create.mutate()}
            disabled={create.isPending || !title.trim() || !scope.trim()}
          >
            {create.isPending ? "Planning…" : "Plan audit"}
          </Button>
        </>
      }
    >
      <Section title="What is being checked">
        <Grid>
          <Field label="Kind">
            <SelectField value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="SELF_INSPECTION">Self-inspection</option>
              <option value="BRANCH">Branch audit</option>
              <option value="SUPPLIER">Supplier audit</option>
              <option value="PROCESS">Process audit</option>
              <option value="REGULATORY">Regulatory inspection</option>
            </SelectField>
          </Field>
          <Field label="Planned for">
            <TextField
              type="date"
              value={plannedFor}
              onChange={(e) => setPlannedFor(e.target.value)}
            />
          </Field>
        </Grid>
        <div className="mt-2">
          <TextField label="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>
        <div className="mt-2">
          <TextArea
            label="Scope"
            value={scope}
            onChange={(e) => setScope(e.target.value)}
            rows={3}
            placeholder="What is examined — and what is deliberately not. The second half is what stops a scope drifting."
          />
        </div>
      </Section>
      {create.isError && <ErrorNote error={create.error} />}
    </Drawer>
  );
}

function AuditDrawer({
  item,
  onClose,
  onChanged,
}: {
  item: Engagement;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [observation, setObservation] = useState("");
  const [severity, setSeverity] = useState("MINOR");
  const [requirement, setRequirement] = useState("");
  const [summary, setSummary] = useState(item.summary);
  const [responses, setResponses] = useState<Record<number, string>>({});
  const [error, setError] = useState<string | null>(null);

  const run = useMutation({
    mutationFn: ({ path, body }: { path: string; body: Record<string, unknown> }) =>
      api(path, { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => {
      setError(null);
      setObservation("");
      setRequirement("");
      onChanged();
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "That did not go through."),
  });

  const unanswered = item.findings.filter((f) => f.status === "OPEN").length;
  const liveCases = item.findings.filter(
    (f) => f.case_number && f.case_status !== "CLOSED" && f.case_status !== "REJECTED",
  ).length;

  return (
    <Drawer
      title={item.reference}
      subtitle={item.title}
      onClose={onClose}
      width="max-w-4xl"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
          <Button
            onClick={() =>
              run.mutate({ path: `/api/quality/audits/${item.id}/close/`, body: { summary } })
            }
            disabled={run.isPending || item.status === "CLOSED"}
          >
            {item.status === "CLOSED" ? "Closed" : "Close audit"}
          </Button>
        </>
      }
    >
      <Section title="Scope">
        <p className="whitespace-pre-wrap text-[13px] text-ink-800">{item.scope}</p>
      </Section>

      {(unanswered > 0 || liveCases > 0) && (
        <p className="mb-3 flex items-start gap-1.5 text-[12px] text-warning-700">
          <AlertTriangle size={14} strokeWidth={1.8} className="mt-0.5 shrink-0" />
          {unanswered > 0 && `${unanswered} finding(s) have had no management response. `}
          {liveCases > 0 && `${liveCases} finding(s) still have open quality cases. `}
          This audit cannot close until both are dealt with — otherwise it closes on paper while
          what it found is still wrong.
        </p>
      )}

      <Section title="Findings">
        <ul className="divide-y divide-line rounded-lg border border-chrome-500">
          {item.findings.map((f) => (
            <li key={f.id} className="px-3 py-2.5">
              <div className="flex items-start gap-2">
                <SeverityChip value={f.severity} />
                <div className="min-w-0 flex-1">
                  <p className="text-[13px] text-ink-900">{f.observation}</p>
                  {f.requirement && (
                    <p className="mt-0.5 text-[11px] text-ink-500">Against {f.requirement}</p>
                  )}
                  {f.case_number && (
                    <p className="mt-1 inline-flex items-center gap-1 text-[11px] text-ink-600">
                      <ClipboardCheck size={12} strokeWidth={1.8} />
                      Raised {f.case_number}
                      <span
                        className={
                          f.case_status === "CLOSED" ? "text-success-700" : "text-warning-700"
                        }
                      >
                        · {f.case_status === "CLOSED" ? "closed" : "still open"}
                      </span>
                    </p>
                  )}
                  {f.management_response ? (
                    <p className="mt-1 rounded-md bg-chrome-100 px-2 py-1 text-[12px] text-ink-700">
                      Response: {f.management_response}
                    </p>
                  ) : (
                    <div className="mt-1.5 flex items-end gap-2">
                      <div className="flex-1">
                        <TextField
                          label="Management response"
                          value={responses[f.id] ?? ""}
                          onChange={(e) =>
                            setResponses({ ...responses, [f.id]: e.target.value })
                          }
                          placeholder="What will be done, or why nothing will be"
                        />
                      </div>
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() =>
                          run.mutate({
                            path: `/api/quality/findings/${f.id}/respond/`,
                            body: { response: responses[f.id] ?? "" },
                          })
                        }
                        disabled={run.isPending || !(responses[f.id] ?? "").trim()}
                      >
                        Respond
                      </Button>
                    </div>
                  )}
                </div>
              </div>
            </li>
          ))}
          {item.findings.length === 0 && (
            <li className="px-3 py-3 text-[13px] text-ink-500">Nothing found yet.</li>
          )}
        </ul>

        <div className="mt-3 rounded-lg border border-chrome-500 p-3">
          <div className="mb-2 text-[12px] font-medium text-ink-700">Record a finding</div>
          <Grid>
            <Field
              label="Severity"
              hint="Major and critical raise a quality case automatically, so their actions get verified."
            >
              <SelectField value={severity} onChange={(e) => setSeverity(e.target.value)}>
                <option value="MINOR">Minor</option>
                <option value="MAJOR">Major</option>
                <option value="CRITICAL">Critical</option>
              </SelectField>
            </Field>
            <Field label="Against" hint="The SOP, licence condition or regulation.">
              <TextField
                value={requirement}
                onChange={(e) => setRequirement(e.target.value)}
                placeholder="e.g. SOP-CC-002 §4"
              />
            </Field>
          </Grid>
          <div className="mt-2">
            <TextArea
              label="What was seen"
              value={observation}
              onChange={(e) => setObservation(e.target.value)}
              rows={2}
              placeholder="With the evidence for it."
            />
          </div>
          <div className="mt-2 flex justify-end">
            <Button
              variant="secondary"
              onClick={() =>
                run.mutate({
                  path: `/api/quality/audits/${item.id}/add-finding/`,
                  body: { observation, severity, requirement },
                })
              }
              disabled={run.isPending || !observation.trim()}
            >
              Add finding
            </Button>
          </div>
        </div>
      </Section>

      <Section title="Summary">
        <TextArea
          label="Conclusion"
          value={summary}
          onChange={(e) => setSummary(e.target.value)}
          rows={3}
        />
      </Section>

      {error && <p className="mt-2 text-[13px] text-danger-700">{error}</p>}
    </Drawer>
  );
}
