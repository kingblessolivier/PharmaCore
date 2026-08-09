import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, DoorOpen, Plus, UserPlus, X } from "lucide-react";
import { useState } from "react";
import { DataGrid } from "../components/DataGrid";
import {
  Drawer,
  Empty,
  ErrorNote,
  Field,
  Grid,
  Input,
  ProgressBar,
  Section,
  Select,
  StatusBadge,
  Textarea,
} from "../components/RecordKit";
import { Badge, Button, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { money, num, shortDate } from "../lib/format";
import type { Applicant, JobRequisition } from "../lib/people";
import { useDefaultOrg } from "../lib/recordData";
import type { Paginated } from "../lib/types";

const STATUS_FILTERS = [
  ["", "All"],
  ["DRAFT", "Draft"],
  ["OPEN", "Open"],
  ["ON_HOLD", "On hold"],
  ["FILLED", "Filled"],
  ["CANCELLED", "Cancelled"],
] as const;

/* -------------------------------------------------------------------------- */

function ApplicantRow({
  applicant,
  onAdvance,
  onReject,
  onHire,
  busy,
}: {
  applicant: Applicant;
  onAdvance: () => void;
  onReject: () => void;
  onHire: () => void;
  busy: boolean;
}) {
  const done = ["HIRED", "REJECTED", "WITHDRAWN"].includes(applicant.stage);
  return (
    <tr className="border-b border-line last:border-0">
      <td className="px-2.5 py-2">
        <div className="font-medium text-ink-900">{applicant.full_name}</div>
        <div className="text-xs text-ink-500">
          {applicant.email || applicant.phone || "no contact"}
          {applicant.licence_number && ` · licence ${applicant.licence_number}`}
        </div>
      </td>
      <td className="px-2.5 py-2">
        <StatusBadge status={applicant.stage} label={applicant.stage_display} />
      </td>
      <td className="px-2.5 py-2 text-right tabular-nums">{applicant.years_experience}y</td>
      <td className="px-2.5 py-2 text-right tabular-nums">
        {num(applicant.expected_salary) > 0 ? money(applicant.expected_salary) : "—"}
      </td>
      <td className="px-2.5 py-2 text-right tabular-nums">
        {num(applicant.offered_salary) > 0 ? money(applicant.offered_salary) : "—"}
      </td>
      <td className="px-2.5 py-2">
        <div className="flex justify-end gap-1">
          {!done && applicant.stage !== "OFFERED" && (
            <Button size="sm" variant="secondary" disabled={busy} onClick={onAdvance}>
              <ChevronRight className="h-3.5 w-3.5" /> Advance
            </Button>
          )}
          {applicant.stage === "OFFERED" && (
            <Button size="sm" disabled={busy} onClick={onHire}>
              <UserPlus className="h-3.5 w-3.5" /> Hire
            </Button>
          )}
          {!done && (
            <Button size="sm" variant="secondary" disabled={busy} onClick={onReject}>
              <X className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      </td>
    </tr>
  );
}

/* -------------------------------------------------------------------------- */

function RequisitionDrawer({
  requisition,
  orgId,
  onClose,
}: {
  requisition: JobRequisition | null;
  orgId: number | null;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [addingApplicant, setAddingApplicant] = useState(false);
  const [form, setForm] = useState({
    job_title: requisition?.job_title ?? "",
    headcount: requisition?.headcount ?? 1,
    employment_type: requisition?.employment_type ?? "FULL_TIME",
    budget_min: requisition?.budget_min ?? "0",
    budget_max: requisition?.budget_max ?? "0",
    requires_licence: requisition?.requires_licence ?? false,
    job_description: requisition?.job_description ?? "",
    requirements: requisition?.requirements ?? "",
    closes_at: requisition?.closes_at ?? "",
  });
  const [applicant, setApplicant] = useState({
    first_name: "",
    last_name: "",
    email: "",
    phone: "",
    years_experience: "0",
    highest_qualification: "",
    licence_number: "",
    expected_salary: "0",
    source: "",
  });

  const invalidate = () => void qc.invalidateQueries({ queryKey: ["requisitions"] });

  const save = useMutation({
    mutationFn: () =>
      api<JobRequisition>(
        requisition ? `/api/hr/requisitions/${requisition.id}/` : "/api/hr/requisitions/",
        {
          method: requisition ? "PATCH" : "POST",
          body: JSON.stringify({
            ...form,
            organization: orgId,
            closes_at: form.closes_at || null,
          }),
        },
      ),
    onSuccess: () => {
      invalidate();
      if (!requisition) onClose();
    },
  });

  const openReq = useMutation({
    mutationFn: () =>
      api(`/api/hr/requisitions/${requisition!.id}/open/`, { method: "POST", body: "{}" }),
    onSuccess: invalidate,
  });

  const addApplicant = useMutation({
    mutationFn: () =>
      api("/api/hr/applicants/", {
        method: "POST",
        body: JSON.stringify({ ...applicant, requisition: requisition!.id }),
      }),
    onSuccess: () => {
      setAddingApplicant(false);
      setApplicant({ ...applicant, first_name: "", last_name: "", email: "", phone: "" });
      invalidate();
    },
  });

  const applicantAction = useMutation({
    mutationFn: ({ id, verb, body }: { id: number; verb: string; body?: object }) =>
      api(`/api/hr/applicants/${id}/${verb}/`, {
        method: "POST",
        body: JSON.stringify(body ?? {}),
      }),
    onSuccess: () => {
      invalidate();
      void qc.invalidateQueries({ queryKey: ["employees"] });
    },
  });

  return (
    <Drawer
      title={
        requisition
          ? `${requisition.reference || "Requisition"} · ${requisition.job_title}`
          : "New requisition"
      }
      badge={
        requisition && (
          <StatusBadge status={requisition.status} label={requisition.status_display} />
        )
      }
      subtitle={
        requisition
          ? `${requisition.headcount_filled}/${requisition.headcount} filled · ${requisition.applicant_count} applicant(s)`
          : "Ask to fill a role. Opening it starts the funnel."
      }
      onClose={onClose}
      width="max-w-4xl"
      footer={
        <>
          {requisition && ["DRAFT", "PENDING_APPROVAL", "ON_HOLD"].includes(requisition.status) && (
            <Button disabled={openReq.isPending} onClick={() => openReq.mutate()}>
              <DoorOpen className="h-3.5 w-3.5" /> Open requisition
            </Button>
          )}
          <Button disabled={save.isPending || !form.job_title} onClick={() => save.mutate()}>
            {save.isPending ? "Saving…" : requisition ? "Save changes" : "Create requisition"}
          </Button>
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
        </>
      }
    >
      <ErrorNote
        error={save.error ?? openReq.error ?? addApplicant.error ?? applicantAction.error}
      />

      <Section title="Role">
        <Grid cols={3}>
          <Field label="Job title" className="sm:col-span-2">
            <Input
              value={form.job_title}
              onChange={(e) => setForm({ ...form, job_title: e.target.value })}
            />
          </Field>
          <Field label="Headcount">
            <Input
              type="number"
              min={1}
              value={form.headcount}
              onChange={(e) => setForm({ ...form, headcount: Number(e.target.value) })}
            />
          </Field>
          <Field label="Employment type">
            <Select
              value={form.employment_type}
              onChange={(e) => setForm({ ...form, employment_type: e.target.value })}
            >
              <option value="FULL_TIME">Full time</option>
              <option value="PART_TIME">Part time</option>
              <option value="CONTRACT">Contract</option>
            </Select>
          </Field>
          <Field label="Budget from">
            <Input
              type="number"
              value={form.budget_min}
              onChange={(e) => setForm({ ...form, budget_min: e.target.value })}
            />
          </Field>
          <Field label="Budget to">
            <Input
              type="number"
              value={form.budget_max}
              onChange={(e) => setForm({ ...form, budget_max: e.target.value })}
            />
          </Field>
          <Field label="Closes">
            <Input
              type="date"
              value={form.closes_at}
              onChange={(e) => setForm({ ...form, closes_at: e.target.value })}
            />
          </Field>
        </Grid>
        <label className="mt-3 flex items-center gap-2 text-sm text-ink-700">
          <input
            type="checkbox"
            checked={form.requires_licence}
            onChange={(e) => setForm({ ...form, requires_licence: e.target.checked })}
            className="h-3.5 w-3.5 accent-brand-600"
          />
          Requires a valid professional licence (pharmacist / technician)
        </label>
        <div className="mt-3">
          <Grid cols={2}>
            <Field label="Job description">
              <Textarea
                value={form.job_description}
                onChange={(e) => setForm({ ...form, job_description: e.target.value })}
              />
            </Field>
            <Field label="Requirements">
              <Textarea
                value={form.requirements}
                onChange={(e) => setForm({ ...form, requirements: e.target.value })}
              />
            </Field>
          </Grid>
        </div>
      </Section>

      {requisition && (
        <Section
          title="Applicants"
          hint="Advance through the funnel; hiring creates the employee, contract and onboarding."
          action={
            <Button variant="secondary" onClick={() => setAddingApplicant((a) => !a)}>
              <Plus className="h-3.5 w-3.5" /> {addingApplicant ? "Cancel" : "Add applicant"}
            </Button>
          }
        >
          {addingApplicant && (
            <div className="mb-3 rounded-lg border border-line bg-surface-50 p-3">
              <Grid cols={3}>
                <Field label="First name">
                  <Input
                    value={applicant.first_name}
                    onChange={(e) => setApplicant({ ...applicant, first_name: e.target.value })}
                  />
                </Field>
                <Field label="Last name">
                  <Input
                    value={applicant.last_name}
                    onChange={(e) => setApplicant({ ...applicant, last_name: e.target.value })}
                  />
                </Field>
                <Field label="Source">
                  <Input
                    value={applicant.source}
                    onChange={(e) => setApplicant({ ...applicant, source: e.target.value })}
                    placeholder="Referral, job board…"
                  />
                </Field>
                <Field label="Email">
                  <Input
                    value={applicant.email}
                    onChange={(e) => setApplicant({ ...applicant, email: e.target.value })}
                  />
                </Field>
                <Field label="Phone">
                  <Input
                    value={applicant.phone}
                    onChange={(e) => setApplicant({ ...applicant, phone: e.target.value })}
                  />
                </Field>
                <Field label="Licence number">
                  <Input
                    value={applicant.licence_number}
                    onChange={(e) => setApplicant({ ...applicant, licence_number: e.target.value })}
                  />
                </Field>
                <Field label="Experience (years)">
                  <Input
                    type="number"
                    step="0.5"
                    value={applicant.years_experience}
                    onChange={(e) =>
                      setApplicant({ ...applicant, years_experience: e.target.value })
                    }
                  />
                </Field>
                <Field label="Qualification">
                  <Input
                    value={applicant.highest_qualification}
                    onChange={(e) =>
                      setApplicant({ ...applicant, highest_qualification: e.target.value })
                    }
                  />
                </Field>
                <Field label="Expected salary">
                  <Input
                    type="number"
                    value={applicant.expected_salary}
                    onChange={(e) =>
                      setApplicant({ ...applicant, expected_salary: e.target.value })
                    }
                  />
                </Field>
              </Grid>
              <div className="mt-3 flex justify-end">
                <Button
                  disabled={!applicant.first_name || !applicant.last_name || addApplicant.isPending}
                  onClick={() => addApplicant.mutate()}
                >
                  {addApplicant.isPending ? "Saving…" : "Add applicant"}
                </Button>
              </div>
            </div>
          )}

          {requisition.applicants.length === 0 ? (
            <Empty message="No applicants yet." />
          ) : (
            <div className="overflow-x-auto rounded-lg border border-line">
              <table className="w-full min-w-[720px] text-sm">
                <thead className="border-b border-line bg-surface-50 text-left text-[11px] uppercase tracking-wide text-ink-500">
                  <tr>
                    <th className="px-2.5 py-2">Applicant</th>
                    <th className="px-2.5 py-2">Stage</th>
                    <th className="px-2.5 py-2 text-right">Experience</th>
                    <th className="px-2.5 py-2 text-right">Expected</th>
                    <th className="px-2.5 py-2 text-right">Offered</th>
                    <th className="px-2.5 py-2" />
                  </tr>
                </thead>
                <tbody>
                  {requisition.applicants.map((a) => (
                    <ApplicantRow
                      key={a.id}
                      applicant={a}
                      busy={applicantAction.isPending}
                      onAdvance={() =>
                        applicantAction.mutate({
                          id: a.id,
                          verb: "advance",
                          body:
                            a.stage === "INTERVIEWED" ? { offered_salary: a.expected_salary } : {},
                        })
                      }
                      onReject={() =>
                        applicantAction.mutate({
                          id: a.id,
                          verb: "reject",
                          body: { reason: "Not selected" },
                        })
                      }
                      onHire={() =>
                        applicantAction.mutate({
                          id: a.id,
                          verb: "hire",
                          body: { hire_date: new Date().toISOString().slice(0, 10) },
                        })
                      }
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Section>
      )}
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

export function RecruitmentPage() {
  const { orgId } = useDefaultOrg();
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState<JobRequisition | null>(null);
  const [creating, setCreating] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["requisitions", status],
    queryFn: () =>
      api<Paginated<JobRequisition>>(
        `/api/hr/requisitions/?page_size=200${status ? `&status=${status}` : ""}`,
      ),
  });

  const rows = data?.results ?? [];
  const current = open ? (rows.find((r) => r.id === open.id) ?? open) : null;

  return (
    <div>
      <PageHeader
        title="Recruitment"
        action={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" /> New requisition
          </Button>
        }
      />

      <DataGrid<JobRequisition>
        rows={rows}
        loading={isLoading}
        getRowId={(r) => r.id}
        storageKey="recruitment"
        exportName="job-requisitions"
        searchPlaceholder="Search by title, reference, department…"
        emptyMessage="No requisitions yet."
        onRowClick={(r) => setOpen(r)}
        toolbar={
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="rounded-md border border-line bg-surface-0 px-2.5 py-1.5 text-xs font-medium text-ink-700"
            aria-label="Filter by status"
          >
            {STATUS_FILTERS.map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        }
        columns={[
          {
            key: "job_title",
            header: "Role",
            render: (r) => (
              <div>
                <div className="font-medium text-ink-900">{r.job_title}</div>
                <div className="font-mono text-xs text-ink-500">
                  {r.reference || `REQ#${r.id}`}
                  {r.department_name && ` · ${r.department_name}`}
                </div>
              </div>
            ),
          },
          {
            key: "status",
            header: "Status",
            value: (r) => r.status,
            render: (r) => <StatusBadge status={r.status} label={r.status_display} />,
          },
          {
            key: "filled",
            header: "Filled",
            value: (r) => r.headcount_filled,
            render: (r) => (
              <ProgressBar
                value={(r.headcount_filled / Math.max(1, r.headcount)) * 100}
                label={`${r.headcount_filled}/${r.headcount}`}
              />
            ),
          },
          {
            key: "applicant_count",
            header: "Applicants",
            align: "right",
            numeric: true,
            value: (r) => r.applicant_count,
            render: (r) =>
              r.applicant_count === 0 ? (
                <span className="text-ink-400">—</span>
              ) : (
                <Badge tone={r.applicant_count >= 3 ? "success" : "warning"}>
                  {r.applicant_count}
                </Badge>
              ),
          },
          {
            key: "budget",
            header: "Budget",
            align: "right",
            numeric: true,
            value: (r) => num(r.budget_max),
            render: (r) =>
              num(r.budget_max) > 0 ? (
                <span className="text-xs">
                  {money(r.budget_min)} – {money(r.budget_max)}
                </span>
              ) : (
                <span className="text-ink-400">—</span>
              ),
          },
          { key: "closes_at", header: "Closes", value: (r) => shortDate(r.closes_at) },
          {
            key: "requires_licence",
            header: "",
            fixed: true,
            sortable: false,
            render: (r) => (r.requires_licence ? <Badge tone="info">Licence</Badge> : null),
          },
        ]}
      />

      {creating && (
        <RequisitionDrawer requisition={null} orgId={orgId} onClose={() => setCreating(false)} />
      )}
      {current && (
        <RequisitionDrawer requisition={current} orgId={orgId} onClose={() => setOpen(null)} />
      )}
    </div>
  );
}
