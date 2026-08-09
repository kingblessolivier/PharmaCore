import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, FileSignature, GraduationCap, Plus, UserCog, Wallet } from "lucide-react";
import { useMemo, useState } from "react";
import { DataGrid } from "../components/DataGrid";
import {
  Drawer,
  Empty,
  ErrorNote,
  Facts,
  Field,
  Grid,
  Input,
  LineEditor,
  Section,
  Select,
  StatusBadge,
  Textarea,
  TotalsRow,
} from "../components/RecordKit";
import { Badge, Button, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { amount, money, num, shortDate } from "../lib/format";
import {
  CONTRACT_KINDS,
  SALARY_COMPONENT_CODES,
  type CompetencyAssessment,
  type EmploymentContract,
  type LeaveBalance,
  type SalaryComponent,
  type SalaryRevision,
  type SalaryStructure,
  type TrainingRecord,
} from "../lib/people";
import { useDefaultOrg } from "../lib/recordData";
import type { Employee, Organization, Paginated } from "../lib/types";

const STATUS_FILTERS = [
  ["", "All statuses"],
  ["PROBATION", "Probation"],
  ["ACTIVE", "Active"],
  ["SUSPENDED", "Suspended"],
  ["TERMINATED", "Terminated"],
] as const;

type Tab = "profile" | "contract" | "pay" | "leave" | "development";

const emptyComponent = (): SalaryComponent => ({
  code: "BASIC",
  label: "",
  amount: "0",
  is_taxable: true,
  in_pension_base: true,
  in_maternity_base: true,
  is_prorated: true,
});

/* -------------------------------------------------------------------------- */
/*  New employee                                                               */
/* -------------------------------------------------------------------------- */

function NewEmployeeDrawer({ orgId, onClose }: { orgId: number | null; onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    middle_name: "",
    national_id: "",
    gender: "",
    dob: "",
    job_title: "",
    employment_type: "FULL_TIME",
    hire_date: new Date().toISOString().slice(0, 10),
    personal_phone: "",
    personal_email: "",
    rssb_number: "",
    tin: "",
    base_salary: "0",
  });
  const set = (patch: Partial<typeof form>) => setForm({ ...form, ...patch });

  const create = useMutation({
    mutationFn: () =>
      api<Employee>("/api/hr/employees/", {
        method: "POST",
        body: JSON.stringify({ ...form, organization: orgId, dob: form.dob || null }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["employees"] });
      onClose();
    },
  });

  return (
    <Drawer
      title="New employee"
      onClose={onClose}
      width="max-w-3xl"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            disabled={!form.first_name || !form.last_name || create.isPending}
            onClick={() => create.mutate()}
          >
            {create.isPending ? "Saving…" : "Create employee"}
          </Button>
        </>
      }
    >
      <ErrorNote error={create.error} />
      <Section title="Identity">
        <Grid cols={3}>
          <Field label="First name">
            <Input value={form.first_name} onChange={(e) => set({ first_name: e.target.value })} />
          </Field>
          <Field label="Middle name">
            <Input
              value={form.middle_name}
              onChange={(e) => set({ middle_name: e.target.value })}
            />
          </Field>
          <Field label="Last name">
            <Input value={form.last_name} onChange={(e) => set({ last_name: e.target.value })} />
          </Field>
          <Field label="National ID">
            <Input
              value={form.national_id}
              onChange={(e) => set({ national_id: e.target.value })}
            />
          </Field>
          <Field label="Gender">
            <Select value={form.gender} onChange={(e) => set({ gender: e.target.value })}>
              <option value="">—</option>
              <option value="F">Female</option>
              <option value="M">Male</option>
              <option value="OTHER">Other</option>
            </Select>
          </Field>
          <Field label="Date of birth">
            <Input type="date" value={form.dob} onChange={(e) => set({ dob: e.target.value })} />
          </Field>
        </Grid>
      </Section>
      <Section title="Employment">
        <Grid cols={3}>
          <Field label="Job title">
            <Input value={form.job_title} onChange={(e) => set({ job_title: e.target.value })} />
          </Field>
          <Field label="Employment type">
            <Select
              value={form.employment_type}
              onChange={(e) => set({ employment_type: e.target.value })}
            >
              <option value="FULL_TIME">Full time</option>
              <option value="PART_TIME">Part time</option>
              <option value="CONTRACT">Contract</option>
            </Select>
          </Field>
          <Field label="Hire date">
            <Input
              type="date"
              value={form.hire_date}
              onChange={(e) => set({ hire_date: e.target.value })}
            />
          </Field>
          <Field label="Opening salary (RWF)" hint="Set the itemised structure on the Pay tab.">
            <Input
              type="number"
              value={form.base_salary}
              onChange={(e) => set({ base_salary: e.target.value })}
            />
          </Field>
          <Field label="RSSB number">
            <Input
              value={form.rssb_number}
              onChange={(e) => set({ rssb_number: e.target.value })}
            />
          </Field>
          <Field label="TIN">
            <Input value={form.tin} onChange={(e) => set({ tin: e.target.value })} />
          </Field>
        </Grid>
      </Section>
      <Section title="Contact">
        <Grid cols={2}>
          <Field label="Personal phone">
            <Input
              value={form.personal_phone}
              onChange={(e) => set({ personal_phone: e.target.value })}
            />
          </Field>
          <Field label="Personal email">
            <Input
              type="email"
              value={form.personal_email}
              onChange={(e) => set({ personal_email: e.target.value })}
            />
          </Field>
        </Grid>
      </Section>
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */
/*  Tabs                                                                       */
/* -------------------------------------------------------------------------- */

function ProfileTab({ employee }: { employee: Employee }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({ ...employee });
  const set = (patch: Partial<Employee>) => setForm({ ...form, ...patch });

  const save = useMutation({
    mutationFn: () =>
      api<Employee>(`/api/hr/employees/${employee.id}/`, {
        method: "PATCH",
        body: JSON.stringify({
          first_name: form.first_name,
          middle_name: (form as Record<string, unknown>).middle_name ?? "",
          last_name: form.last_name,
          national_id: form.national_id,
          job_title: form.job_title,
          employment_type: form.employment_type,
          gender: (form as Record<string, unknown>).gender ?? "",
          dob: (form as Record<string, unknown>).dob || null,
          marital_status: (form as Record<string, unknown>).marital_status ?? "",
          dependants_count: Number((form as Record<string, unknown>).dependants_count ?? 0),
          nationality: (form as Record<string, unknown>).nationality ?? "",
          personal_phone: (form as Record<string, unknown>).personal_phone ?? "",
          personal_email: (form as Record<string, unknown>).personal_email ?? "",
          address: form.address,
          district: (form as Record<string, unknown>).district ?? "",
          sector: (form as Record<string, unknown>).sector ?? "",
          cell: (form as Record<string, unknown>).cell ?? "",
          village: (form as Record<string, unknown>).village ?? "",
          has_disability: Boolean((form as Record<string, unknown>).has_disability),
          disability_note: (form as Record<string, unknown>).disability_note ?? "",
          work_permit_number: (form as Record<string, unknown>).work_permit_number ?? "",
          work_permit_expiry: (form as Record<string, unknown>).work_permit_expiry || null,
          passport_number: (form as Record<string, unknown>).passport_number ?? "",
          rssb_number: form.rssb_number,
          rama_number: (form as Record<string, unknown>).rama_number ?? "",
          cbhi_number: (form as Record<string, unknown>).cbhi_number ?? "",
          is_rama_member: Boolean((form as Record<string, unknown>).is_rama_member),
          tin: (form as Record<string, unknown>).tin ?? "",
          bank_name: (form as Record<string, unknown>).bank_name ?? "",
          bank_branch: (form as Record<string, unknown>).bank_branch ?? "",
          bank_account: form.bank_account,
          bank_account_name: (form as Record<string, unknown>).bank_account_name ?? "",
          momo_number: form.momo_number,
          payment_method: (form as Record<string, unknown>).payment_method ?? "BANK",
          next_of_kin_name: form.next_of_kin_name,
          next_of_kin_relation: form.next_of_kin_relation,
          next_of_kin_phone: form.next_of_kin_phone,
          emergency_contact_phone: form.emergency_contact_phone,
        }),
      }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["employees"] }),
  });

  const f = form as unknown as Record<string, string | number | boolean>;

  return (
    <>
      <ErrorNote error={save.error} />
      <Section title="Identity">
        <Grid cols={3}>
          <Field label="First name">
            <Input value={form.first_name} onChange={(e) => set({ first_name: e.target.value })} />
          </Field>
          <Field label="Middle name">
            <Input
              value={String(f.middle_name ?? "")}
              onChange={(e) => setForm({ ...form, middle_name: e.target.value } as Employee)}
            />
          </Field>
          <Field label="Last name">
            <Input value={form.last_name} onChange={(e) => set({ last_name: e.target.value })} />
          </Field>
          <Field label="National ID">
            <Input
              value={form.national_id}
              onChange={(e) => set({ national_id: e.target.value })}
            />
          </Field>
          <Field label="Passport">
            <Input
              value={String(f.passport_number ?? "")}
              onChange={(e) => setForm({ ...form, passport_number: e.target.value } as Employee)}
            />
          </Field>
          <Field label="Nationality">
            <Input
              value={String(f.nationality ?? "")}
              onChange={(e) => setForm({ ...form, nationality: e.target.value } as Employee)}
            />
          </Field>
          <Field label="Gender">
            <Select
              value={String(f.gender ?? "")}
              onChange={(e) => setForm({ ...form, gender: e.target.value } as Employee)}
            >
              <option value="">—</option>
              <option value="F">Female</option>
              <option value="M">Male</option>
              <option value="OTHER">Other</option>
            </Select>
          </Field>
          <Field label="Date of birth">
            <Input
              type="date"
              value={String(f.dob ?? "")}
              onChange={(e) => setForm({ ...form, dob: e.target.value } as Employee)}
            />
          </Field>
          <Field label="Marital status">
            <Select
              value={String(f.marital_status ?? "")}
              onChange={(e) => setForm({ ...form, marital_status: e.target.value } as Employee)}
            >
              <option value="">—</option>
              <option value="SINGLE">Single</option>
              <option value="MARRIED">Married</option>
              <option value="DIVORCED">Divorced</option>
              <option value="WIDOWED">Widowed</option>
            </Select>
          </Field>
          <Field label="Dependants" hint="Drives CBHI household cover.">
            <Input
              type="number"
              value={Number(f.dependants_count ?? 0)}
              onChange={(e) =>
                setForm({ ...form, dependants_count: Number(e.target.value) } as Employee)
              }
            />
          </Field>
        </Grid>
      </Section>

      <Section title="Contact & address">
        <Grid cols={3}>
          <Field label="Personal phone">
            <Input
              value={String(f.personal_phone ?? "")}
              onChange={(e) => setForm({ ...form, personal_phone: e.target.value } as Employee)}
            />
          </Field>
          <Field label="Personal email">
            <Input
              value={String(f.personal_email ?? "")}
              onChange={(e) => setForm({ ...form, personal_email: e.target.value } as Employee)}
            />
          </Field>
          <Field label="Emergency contact">
            <Input
              value={form.emergency_contact_phone}
              onChange={(e) => set({ emergency_contact_phone: e.target.value })}
            />
          </Field>
          <Field label="District">
            <Input
              value={String(f.district ?? "")}
              onChange={(e) => setForm({ ...form, district: e.target.value } as Employee)}
            />
          </Field>
          <Field label="Sector">
            <Input
              value={String(f.sector ?? "")}
              onChange={(e) => setForm({ ...form, sector: e.target.value } as Employee)}
            />
          </Field>
          <Field label="Cell">
            <Input
              value={String(f.cell ?? "")}
              onChange={(e) => setForm({ ...form, cell: e.target.value } as Employee)}
            />
          </Field>
        </Grid>
        <div className="mt-3">
          <Field label="Address">
            <Textarea value={form.address} onChange={(e) => set({ address: e.target.value })} />
          </Field>
        </div>
      </Section>

      <Section title="Next of kin">
        <Grid cols={3}>
          <Field label="Name">
            <Input
              value={form.next_of_kin_name}
              onChange={(e) => set({ next_of_kin_name: e.target.value })}
            />
          </Field>
          <Field label="Relationship">
            <Input
              value={form.next_of_kin_relation}
              onChange={(e) => set({ next_of_kin_relation: e.target.value })}
            />
          </Field>
          <Field label="Phone">
            <Input
              value={form.next_of_kin_phone}
              onChange={(e) => set({ next_of_kin_phone: e.target.value })}
            />
          </Field>
        </Grid>
      </Section>

      <Section title="Statutory registration">
        <Grid cols={4}>
          <Field label="RSSB number">
            <Input
              value={form.rssb_number}
              onChange={(e) => set({ rssb_number: e.target.value })}
            />
          </Field>
          <Field label="TIN (RRA)">
            <Input
              value={String(f.tin ?? "")}
              onChange={(e) => setForm({ ...form, tin: e.target.value } as Employee)}
            />
          </Field>
          <Field label="CBHI number">
            <Input
              value={String(f.cbhi_number ?? "")}
              onChange={(e) => setForm({ ...form, cbhi_number: e.target.value } as Employee)}
            />
          </Field>
          <Field label="RAMA number">
            <Input
              value={String(f.rama_number ?? "")}
              onChange={(e) => setForm({ ...form, rama_number: e.target.value } as Employee)}
            />
          </Field>
        </Grid>
        <label className="mt-3 flex items-center gap-2 text-sm text-ink-700">
          <input
            type="checkbox"
            checked={Boolean(f.is_rama_member)}
            onChange={(e) =>
              setForm({ ...form, is_rama_member: e.target.checked } as unknown as Employee)
            }
            className="h-3.5 w-3.5 accent-brand-600"
          />
          RAMA member — adds the 7.5% + 7.5% deduction on basic
        </label>
      </Section>

      <Section title="Right to work" hint="Only needed for non-Rwandan staff.">
        <Grid cols={2}>
          <Field label="Work permit number">
            <Input
              value={String(f.work_permit_number ?? "")}
              onChange={(e) => setForm({ ...form, work_permit_number: e.target.value } as Employee)}
            />
          </Field>
          <Field label="Work permit expiry" hint="Blocks roster assignment once past.">
            <Input
              type="date"
              value={String(f.work_permit_expiry ?? "")}
              onChange={(e) => setForm({ ...form, work_permit_expiry: e.target.value } as Employee)}
            />
          </Field>
        </Grid>
      </Section>

      <Section title="Payment">
        <Grid cols={3}>
          <Field label="Method">
            <Select
              value={String(f.payment_method ?? "BANK")}
              onChange={(e) => setForm({ ...form, payment_method: e.target.value } as Employee)}
            >
              <option value="BANK">Bank transfer</option>
              <option value="MOMO">Mobile money</option>
              <option value="CASH">Cash</option>
            </Select>
          </Field>
          <Field label="Bank">
            <Input
              value={String(f.bank_name ?? "")}
              onChange={(e) => setForm({ ...form, bank_name: e.target.value } as Employee)}
            />
          </Field>
          <Field label="Branch">
            <Input
              value={String(f.bank_branch ?? "")}
              onChange={(e) => setForm({ ...form, bank_branch: e.target.value } as Employee)}
            />
          </Field>
          <Field label="Account number">
            <Input
              value={form.bank_account}
              onChange={(e) => set({ bank_account: e.target.value })}
            />
          </Field>
          <Field label="Account name">
            <Input
              value={String(f.bank_account_name ?? "")}
              onChange={(e) => setForm({ ...form, bank_account_name: e.target.value } as Employee)}
            />
          </Field>
          <Field label="MoMo number">
            <Input
              value={form.momo_number}
              onChange={(e) => set({ momo_number: e.target.value })}
            />
          </Field>
        </Grid>
      </Section>

      <div className="flex justify-end">
        <Button disabled={save.isPending} onClick={() => save.mutate()}>
          {save.isPending ? "Saving…" : "Save employee"}
        </Button>
      </div>
    </>
  );
}

function ContractTab({ employee }: { employee: Employee }) {
  const qc = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({
    kind: "PERMANENT",
    job_title: employee.job_title,
    start_date: new Date().toISOString().slice(0, 10),
    end_date: "",
    grade: "",
    step: "",
    probation_months: 3,
    notice_period_days: 30,
    annual_leave_days: 18,
    terms: "",
  });

  const contracts = useQuery({
    queryKey: ["contracts", employee.id],
    queryFn: () => api<Paginated<EmploymentContract>>(`/api/hr/contracts/?employee=${employee.id}`),
    select: (r) => r.results,
  });

  const issue = useMutation({
    mutationFn: () =>
      api("/api/hr/contracts/issue/", {
        method: "POST",
        body: JSON.stringify({ ...form, employee: employee.id, end_date: form.end_date || null }),
      }),
    onSuccess: () => {
      setAdding(false);
      void qc.invalidateQueries({ queryKey: ["contracts", employee.id] });
      void qc.invalidateQueries({ queryKey: ["employees"] });
    },
  });

  return (
    <Section
      title="Employment contracts"
      hint="Issuing a new contract supersedes the current one — the history is never rewritten."
      action={
        <Button variant="secondary" onClick={() => setAdding((a) => !a)}>
          <Plus className="h-3.5 w-3.5" /> {adding ? "Cancel" : "Issue contract"}
        </Button>
      }
    >
      {adding && (
        <div className="mb-3 rounded-lg border border-line bg-surface-50 p-3">
          <ErrorNote error={issue.error} />
          <Grid cols={3}>
            <Field label="Type">
              <Select
                value={form.kind}
                onChange={(e) => setForm({ ...form, kind: e.target.value })}
              >
                {CONTRACT_KINDS.map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Job title">
              <Input
                value={form.job_title}
                onChange={(e) => setForm({ ...form, job_title: e.target.value })}
              />
            </Field>
            <Field label="Start date">
              <Input
                type="date"
                value={form.start_date}
                onChange={(e) => setForm({ ...form, start_date: e.target.value })}
              />
            </Field>
            <Field label="End date" hint="Fixed-term only.">
              <Input
                type="date"
                value={form.end_date}
                onChange={(e) => setForm({ ...form, end_date: e.target.value })}
              />
            </Field>
            <Field label="Grade">
              <Input
                value={form.grade}
                onChange={(e) => setForm({ ...form, grade: e.target.value })}
              />
            </Field>
            <Field label="Step">
              <Input
                value={form.step}
                onChange={(e) => setForm({ ...form, step: e.target.value })}
              />
            </Field>
            <Field label="Probation (months)">
              <Input
                type="number"
                value={form.probation_months}
                onChange={(e) => setForm({ ...form, probation_months: Number(e.target.value) })}
              />
            </Field>
            <Field label="Notice period (days)">
              <Input
                type="number"
                value={form.notice_period_days}
                onChange={(e) => setForm({ ...form, notice_period_days: Number(e.target.value) })}
              />
            </Field>
            <Field label="Annual leave (days)">
              <Input
                type="number"
                value={form.annual_leave_days}
                onChange={(e) => setForm({ ...form, annual_leave_days: Number(e.target.value) })}
              />
            </Field>
          </Grid>
          <div className="mt-3">
            <Field label="Terms">
              <Textarea
                value={form.terms}
                onChange={(e) => setForm({ ...form, terms: e.target.value })}
              />
            </Field>
          </div>
          <div className="mt-3 flex justify-end">
            <Button disabled={issue.isPending} onClick={() => issue.mutate()}>
              {issue.isPending ? "Issuing…" : "Issue contract"}
            </Button>
          </div>
        </div>
      )}

      {(contracts.data ?? []).length === 0 ? (
        <Empty message="No contract on file — issue one so the terms are on the record." />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-line">
          <table className="w-full min-w-[720px] text-sm">
            <thead className="border-b border-line bg-surface-50 text-left text-[11px] uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-2.5 py-2">Contract</th>
                <th className="px-2.5 py-2">Period</th>
                <th className="px-2.5 py-2">Probation ends</th>
                <th className="px-2.5 py-2 text-right">Notice</th>
                <th className="px-2.5 py-2 text-right">Leave</th>
                <th className="px-2.5 py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {(contracts.data ?? []).map((c) => (
                <tr key={c.id} className="border-b border-line last:border-0">
                  <td className="px-2.5 py-2">
                    <div className="font-medium text-ink-900">{c.job_title}</div>
                    <div className="text-xs text-ink-500">
                      {c.kind_display}
                      {c.grade && ` · ${c.grade}`}
                    </div>
                  </td>
                  <td className="px-2.5 py-2">
                    {c.start_date} → {c.end_date ?? "open"}
                  </td>
                  <td className="px-2.5 py-2">{shortDate(c.probation_end)}</td>
                  <td className="px-2.5 py-2 text-right tabular-nums">{c.notice_period_days}d</td>
                  <td className="px-2.5 py-2 text-right tabular-nums">{c.annual_leave_days}d</td>
                  <td className="px-2.5 py-2">
                    <div className="flex items-center gap-1.5">
                      <StatusBadge status={c.status} label={c.status_display} />
                      {c.is_current && <Badge tone="info">Current</Badge>}
                      {c.is_expiring && <Badge tone="warning">Expiring</Badge>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  );
}

function PayTab({ employee }: { employee: Employee }) {
  const qc = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [effectiveFrom, setEffectiveFrom] = useState(new Date().toISOString().slice(0, 10));
  const [reason, setReason] = useState("ANNUAL_REVIEW");
  const [note, setNote] = useState("");
  const [components, setComponents] = useState<SalaryComponent[]>([emptyComponent()]);

  const structures = useQuery({
    queryKey: ["salary-structures", employee.id],
    queryFn: () =>
      api<Paginated<SalaryStructure>>(`/api/hr/salary-structures/?employee=${employee.id}`),
    select: (r) => r.results,
  });
  const revisions = useQuery({
    queryKey: ["salary-revisions", employee.id],
    queryFn: () =>
      api<Paginated<SalaryRevision>>(`/api/hr/salary-revisions/?employee=${employee.id}`),
    select: (r) => r.results,
  });

  const totals = useMemo(() => {
    const gross = components.reduce((s, c) => s + num(c.amount), 0);
    const pension = components.reduce((s, c) => s + (c.in_pension_base ? num(c.amount) : 0), 0);
    const maternity = components.reduce((s, c) => s + (c.in_maternity_base ? num(c.amount) : 0), 0);
    const taxable = components.reduce((s, c) => s + (c.is_taxable ? num(c.amount) : 0), 0);
    return { gross, pension, maternity, taxable };
  }, [components]);

  const save = useMutation({
    mutationFn: () =>
      api("/api/hr/salary-structures/set_for_employee/", {
        method: "POST",
        body: JSON.stringify({
          employee: employee.id,
          effective_from: effectiveFrom,
          reason,
          note,
          components: components.filter((c) => num(c.amount) > 0),
        }),
      }),
    onSuccess: () => {
      setAdding(false);
      setComponents([emptyComponent()]);
      void qc.invalidateQueries({ queryKey: ["salary-structures", employee.id] });
      void qc.invalidateQueries({ queryKey: ["salary-revisions", employee.id] });
      void qc.invalidateQueries({ queryKey: ["employees"] });
    },
  });

  const current = (structures.data ?? []).find((s) => s.is_active) ?? structures.data?.[0];

  return (
    <>
      {current && (
        <Section title="Current structure" hint={`Effective ${current.effective_from}.`}>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              ["Gross", current.gross],
              ["Pension base", current.pension_base],
              ["Maternity base", current.maternity_base],
              ["Taxable", current.taxable_base],
            ].map(([label, value]) => (
              <div key={label} className="rounded-lg border border-line px-3 py-2">
                <div className="text-[11px] uppercase tracking-wide text-ink-500">{label}</div>
                <div className="text-lg font-semibold tabular-nums">{amount(value)}</div>
              </div>
            ))}
          </div>
          <p className="mt-2 text-xs text-ink-500">
            Transport allowance is inside the pension base but outside the maternity base — which is
            why the two differ.
          </p>
          <div className="mt-3 overflow-x-auto rounded-lg border border-line">
            <table className="w-full min-w-[560px] text-sm">
              <thead className="border-b border-line bg-surface-50 text-left text-[11px] uppercase tracking-wide text-ink-500">
                <tr>
                  <th className="px-2.5 py-2">Component</th>
                  <th className="px-2.5 py-2 text-right">Amount</th>
                  <th className="px-2.5 py-2 text-center">Taxable</th>
                  <th className="px-2.5 py-2 text-center">Pension</th>
                  <th className="px-2.5 py-2 text-center">Maternity</th>
                </tr>
              </thead>
              <tbody>
                {current.components.map((c) => (
                  <tr key={c.id} className="border-b border-line last:border-0">
                    <td className="px-2.5 py-2">{c.label || c.code_display || c.code}</td>
                    <td className="px-2.5 py-2 text-right tabular-nums">{amount(c.amount)}</td>
                    <td className="px-2.5 py-2 text-center">{c.is_taxable ? "✓" : "—"}</td>
                    <td className="px-2.5 py-2 text-center">{c.in_pension_base ? "✓" : "—"}</td>
                    <td className="px-2.5 py-2 text-center">{c.in_maternity_base ? "✓" : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}

      <Section
        title="Set a new structure"
        hint="Opens a new effective-dated structure and closes the current one the day before."
        action={
          <Button variant="secondary" onClick={() => setAdding((a) => !a)}>
            <Plus className="h-3.5 w-3.5" /> {adding ? "Cancel" : "New structure"}
          </Button>
        }
      >
        {adding && (
          <>
            <ErrorNote error={save.error} />
            <Grid cols={3}>
              <Field label="Effective from">
                <Input
                  type="date"
                  value={effectiveFrom}
                  onChange={(e) => setEffectiveFrom(e.target.value)}
                />
              </Field>
              <Field label="Reason">
                <Select value={reason} onChange={(e) => setReason(e.target.value)}>
                  <option value="ANNUAL_REVIEW">Annual review</option>
                  <option value="PROMOTION">Promotion</option>
                  <option value="CONFIRMATION">Probation confirmation</option>
                  <option value="MARKET_ADJUSTMENT">Market adjustment</option>
                  <option value="DEMOTION">Demotion</option>
                  <option value="CORRECTION">Correction</option>
                  <option value="OTHER">Other</option>
                </Select>
              </Field>
              <Field label="Note">
                <Input value={note} onChange={(e) => setNote(e.target.value)} />
              </Field>
            </Grid>
            <div className="mt-3">
              <LineEditor<SalaryComponent>
                rows={components}
                onChange={setComponents}
                makeRow={emptyComponent}
                addLabel="Add component"
                columns={[
                  {
                    header: "Component",
                    width: "26%",
                    cell: (row, set) => (
                      <Select
                        value={row.code}
                        onChange={(e) => {
                          const spec = SALARY_COMPONENT_CODES.find(
                            (c) => c.value === e.target.value,
                          );
                          set({
                            code: e.target.value,
                            is_taxable: spec?.taxable ?? true,
                            in_pension_base: spec?.pensionable ?? true,
                            in_maternity_base: spec?.maternity ?? true,
                          });
                        }}
                      >
                        {SALARY_COMPONENT_CODES.map((c) => (
                          <option key={c.value} value={c.value}>
                            {c.label}
                          </option>
                        ))}
                      </Select>
                    ),
                  },
                  {
                    header: "Label",
                    width: "20%",
                    cell: (row, set) => (
                      <Input
                        value={row.label}
                        onChange={(e) => set({ label: e.target.value })}
                        placeholder="Optional"
                      />
                    ),
                  },
                  {
                    header: "Amount",
                    width: "16%",
                    align: "right",
                    cell: (row, set) => (
                      <Input
                        type="number"
                        value={row.amount}
                        onChange={(e) => set({ amount: e.target.value })}
                        className="text-right"
                      />
                    ),
                  },
                  {
                    header: "Taxable",
                    width: "12%",
                    align: "center",
                    cell: (row, set) => (
                      <input
                        type="checkbox"
                        checked={row.is_taxable}
                        onChange={(e) => set({ is_taxable: e.target.checked })}
                        className="h-3.5 w-3.5 accent-brand-600"
                      />
                    ),
                  },
                  {
                    header: "Pension",
                    width: "12%",
                    align: "center",
                    cell: (row, set) => (
                      <input
                        type="checkbox"
                        checked={row.in_pension_base}
                        onChange={(e) => set({ in_pension_base: e.target.checked })}
                        className="h-3.5 w-3.5 accent-brand-600"
                      />
                    ),
                  },
                  {
                    header: "Maternity",
                    width: "14%",
                    align: "center",
                    cell: (row, set) => (
                      <input
                        type="checkbox"
                        checked={row.in_maternity_base}
                        onChange={(e) => set({ in_maternity_base: e.target.checked })}
                        className="h-3.5 w-3.5 accent-brand-600"
                      />
                    ),
                  },
                ]}
                footer={
                  <>
                    <TotalsRow span={5} label="Gross" value={amount(totals.gross)} strong />
                    <TotalsRow span={5} label="Pension base" value={amount(totals.pension)} />
                    <TotalsRow span={5} label="Maternity base" value={amount(totals.maternity)} />
                    <TotalsRow span={5} label="Taxable base" value={amount(totals.taxable)} />
                  </>
                }
              />
            </div>
            <div className="mt-3 flex justify-end">
              <Button disabled={save.isPending || totals.gross <= 0} onClick={() => save.mutate()}>
                {save.isPending ? "Saving…" : "Set structure"}
              </Button>
            </div>
          </>
        )}
      </Section>

      <Section title="Salary history">
        {(revisions.data ?? []).length === 0 ? (
          <Empty message="No revisions yet." />
        ) : (
          <div className="overflow-x-auto rounded-lg border border-line">
            <table className="w-full min-w-[560px] text-sm">
              <thead className="border-b border-line bg-surface-50 text-left text-[11px] uppercase tracking-wide text-ink-500">
                <tr>
                  <th className="px-2.5 py-2">Effective</th>
                  <th className="px-2.5 py-2">Reason</th>
                  <th className="px-2.5 py-2 text-right">From</th>
                  <th className="px-2.5 py-2 text-right">To</th>
                  <th className="px-2.5 py-2 text-right">Change</th>
                  <th className="px-2.5 py-2">By</th>
                </tr>
              </thead>
              <tbody>
                {(revisions.data ?? []).map((r) => (
                  <tr key={r.id} className="border-b border-line last:border-0">
                    <td className="px-2.5 py-2">{r.effective_date}</td>
                    <td className="px-2.5 py-2">{r.reason_display}</td>
                    <td className="px-2.5 py-2 text-right tabular-nums">
                      {amount(r.previous_gross)}
                    </td>
                    <td className="px-2.5 py-2 text-right tabular-nums">{amount(r.new_gross)}</td>
                    <td className="px-2.5 py-2 text-right">
                      <Badge tone={num(r.change_pct) >= 0 ? "success" : "danger"}>
                        {num(r.change_pct) >= 0 ? "+" : ""}
                        {r.change_pct}%
                      </Badge>
                    </td>
                    <td className="px-2.5 py-2 text-ink-500">{r.approved_by_name ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>
    </>
  );
}

function LeaveTab({ employee }: { employee: Employee }) {
  const balances = useQuery({
    queryKey: ["leave-balances", employee.id],
    queryFn: () => api<Paginated<LeaveBalance>>(`/api/hr/leave-balances/?employee=${employee.id}`),
    select: (r) => r.results,
  });

  return (
    <Section
      title="Leave balances"
      hint="Requested days are held as pending, so two requests cannot spend the same day."
    >
      {(balances.data ?? []).length === 0 ? (
        <Empty message="No balances yet — seed the organization's leave types and run an accrual." />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-line">
          <table className="w-full min-w-[680px] text-sm">
            <thead className="border-b border-line bg-surface-50 text-left text-[11px] uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-2.5 py-2">Leave type</th>
                <th className="px-2.5 py-2 text-right">Entitled</th>
                <th className="px-2.5 py-2 text-right">Taken</th>
                <th className="px-2.5 py-2 text-right">Pending</th>
                <th className="px-2.5 py-2 text-right">Available</th>
                <th className="px-2.5 py-2">Year</th>
              </tr>
            </thead>
            <tbody>
              {(balances.data ?? []).map((b) => (
                <tr key={b.id} className="border-b border-line last:border-0">
                  <td className="px-2.5 py-2">
                    <span className="font-medium">{b.leave_type_name}</span>
                    {!b.is_paid && <Badge tone="neutral">unpaid</Badge>}
                  </td>
                  <td className="px-2.5 py-2 text-right tabular-nums">{b.entitled}</td>
                  <td className="px-2.5 py-2 text-right tabular-nums">{b.taken}</td>
                  <td className="px-2.5 py-2 text-right tabular-nums">
                    {num(b.pending) > 0 ? <Badge tone="warning">{b.pending}</Badge> : "—"}
                  </td>
                  <td className="px-2.5 py-2 text-right font-semibold tabular-nums">
                    {b.available}
                  </td>
                  <td className="px-2.5 py-2 text-ink-500">{b.year}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  );
}

function DevelopmentTab({ employee }: { employee: Employee }) {
  const training = useQuery({
    queryKey: ["training", employee.id],
    queryFn: () => api<Paginated<TrainingRecord>>(`/api/hr/training/?employee=${employee.id}`),
    select: (r) => r.results,
  });
  const competencies = useQuery({
    queryKey: ["competencies", employee.id],
    queryFn: () =>
      api<Paginated<CompetencyAssessment>>(`/api/hr/competencies/?employee=${employee.id}`),
    select: (r) => r.results,
  });

  return (
    <>
      <Section title="Competencies" hint="Controlled-drug handling gates the dispense permission.">
        {(competencies.data ?? []).length === 0 ? (
          <Empty message="No competency assessments on file." />
        ) : (
          <div className="flex flex-wrap gap-2">
            {(competencies.data ?? []).map((c) => (
              <div
                key={c.id}
                className={`rounded-lg border px-3 py-2 text-sm ${
                  c.is_valid ? "border-green-200 bg-green-50" : "border-red-200 bg-red-50"
                }`}
              >
                <div className="font-medium text-ink-900">{c.competency_display}</div>
                <div className="text-xs text-ink-600">
                  {c.result_display} · {c.valid_until ? `valid to ${c.valid_until}` : "no expiry"}
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section title="Training & SOPs">
        {(training.data ?? []).length === 0 ? (
          <Empty message="No training assigned." />
        ) : (
          <div className="overflow-x-auto rounded-lg border border-line">
            <table className="w-full min-w-[600px] text-sm">
              <thead className="border-b border-line bg-surface-50 text-left text-[11px] uppercase tracking-wide text-ink-500">
                <tr>
                  <th className="px-2.5 py-2">Course</th>
                  <th className="px-2.5 py-2">Type</th>
                  <th className="px-2.5 py-2">Due</th>
                  <th className="px-2.5 py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {(training.data ?? []).map((t) => (
                  <tr key={t.id} className="border-b border-line last:border-0">
                    <td className="px-2.5 py-2">
                      <span className="font-medium">{t.course_name}</span>
                      {t.is_mandatory && <Badge tone="info">mandatory</Badge>}
                    </td>
                    <td className="px-2.5 py-2 text-ink-600">{t.kind_display}</td>
                    <td className="px-2.5 py-2">
                      {t.is_overdue ? (
                        <Badge tone="danger">overdue {shortDate(t.due_on)}</Badge>
                      ) : (
                        shortDate(t.due_on)
                      )}
                    </td>
                    <td className="px-2.5 py-2">
                      <StatusBadge status={t.status} label={t.status_display} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>
    </>
  );
}

/* -------------------------------------------------------------------------- */
/*  Page                                                                       */
/* -------------------------------------------------------------------------- */

export function EmployeesPage() {
  const { orgId, orgs } = useDefaultOrg();
  const [orgFilter, setOrgFilter] = useState<number | "">("");
  const [statusFilter, setStatusFilter] = useState("");
  const [open, setOpen] = useState<Employee | null>(null);
  const [tab, setTab] = useState<Tab>("profile");
  const [creating, setCreating] = useState(false);

  const params = new URLSearchParams({ page_size: "500" });
  if (orgFilter) params.set("organization", String(orgFilter));
  if (statusFilter) params.set("status", statusFilter);

  const { data, isLoading } = useQuery({
    queryKey: ["employees", orgFilter, statusFilter],
    queryFn: () => api<Paginated<Employee>>(`/api/hr/employees/?${params.toString()}`),
  });

  const rows = data?.results ?? [];
  const current = open ? (rows.find((e) => e.id === open.id) ?? open) : null;

  const tabs: [Tab, string, typeof UserCog][] = [
    ["profile", "Profile", UserCog],
    ["contract", "Contract", FileSignature],
    ["pay", "Pay structure", Wallet],
    ["leave", "Leave", CalendarDays],
    ["development", "Development", GraduationCap],
  ];

  return (
    <div>
      <PageHeader
        title="Employees"
        action={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" /> New employee
          </Button>
        }
      />

      <DataGrid<Employee>
        rows={rows}
        loading={isLoading}
        getRowId={(e) => e.id}
        storageKey="people-employees"
        exportName="employees"
        searchPlaceholder="Search by name, number, job title…"
        emptyMessage="No employees yet."
        onRowClick={(e) => {
          setOpen(e);
          setTab("profile");
        }}
        toolbar={
          <>
            {orgs.length > 1 && (
              <select
                value={orgFilter}
                onChange={(e) => setOrgFilter(e.target.value ? Number(e.target.value) : "")}
                className="rounded-md border border-line bg-surface-0 px-2.5 py-1.5 text-xs font-medium text-ink-700"
                aria-label="Filter by organization"
              >
                <option value="">All organizations</option>
                {orgs.map((o: Organization) => (
                  <option key={o.id} value={o.id}>
                    {o.name}
                  </option>
                ))}
              </select>
            )}
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-md border border-line bg-surface-0 px-2.5 py-1.5 text-xs font-medium text-ink-700"
              aria-label="Filter by status"
            >
              {STATUS_FILTERS.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </>
        }
        columns={[
          {
            key: "employee_number",
            header: "Employee",
            render: (e) => (
              <div>
                <div className="font-medium text-ink-900">{e.full_name}</div>
                <div className="font-mono text-xs text-ink-500">{e.employee_number || "—"}</div>
              </div>
            ),
            value: (e) => `${e.full_name} ${e.employee_number}`,
          },
          { key: "job_title", header: "Job title", value: (e) => e.job_title || "—" },
          { key: "organization_name", header: "Branch" },
          { key: "department_name", header: "Department", value: (e) => e.department_name ?? "—" },
          {
            key: "employment_type",
            header: "Type",
            value: (e) => e.employment_type,
            render: (e) => (
              <span className="text-ink-600">{e.employment_type.replace("_", " ")}</span>
            ),
          },
          { key: "hire_date", header: "Hired", value: (e) => e.hire_date },
          {
            key: "base_salary",
            header: "Gross",
            align: "right",
            numeric: true,
            value: (e) => Number(e.base_salary),
            render: (e) => money(e.base_salary),
          },
          {
            key: "employment_status",
            header: "Status",
            value: (e) => e.employment_status,
            render: (e) => <StatusBadge status={e.employment_status} />,
          },
        ]}
      />

      {creating && <NewEmployeeDrawer orgId={orgId} onClose={() => setCreating(false)} />}

      {current && (
        <Drawer
          title={current.full_name}
          badge={<StatusBadge status={current.employment_status} />}
          subtitle={
            <>
              {current.employee_number || "no PF number"} · {current.job_title || "—"} ·{" "}
              {current.organization_name} · hired {current.hire_date}
            </>
          }
          onClose={() => setOpen(null)}
          width="max-w-5xl"
        >
          {current.employment_status === "TERMINATED" && (
            <div className="mb-4 rounded-md border border-line bg-surface-50 p-3">
              <Facts
                rows={[
                  ["Left on", shortDate(current.end_date)],
                  [
                    "Reason",
                    String(
                      (current as unknown as Record<string, string>).termination_reason || "—",
                    ),
                  ],
                  [
                    "Rehire",
                    (current as unknown as Record<string, boolean>).is_eligible_for_rehire
                      ? "Eligible"
                      : "Not eligible",
                  ],
                ]}
              />
            </div>
          )}

          <div className="mb-4 flex gap-1 border-b border-line">
            {tabs.map(([key, label, Icon]) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={`-mb-px flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm ${
                  tab === key
                    ? "border-brand-600 font-semibold text-brand-700"
                    : "border-transparent text-ink-600 hover:text-ink-900"
                }`}
              >
                <Icon className="h-3.5 w-3.5" />
                {label}
              </button>
            ))}
          </div>

          {tab === "profile" && <ProfileTab key={current.id} employee={current} />}
          {tab === "contract" && <ContractTab employee={current} />}
          {tab === "pay" && <PayTab employee={current} />}
          {tab === "leave" && <LeaveTab employee={current} />}
          {tab === "development" && <DevelopmentTab employee={current} />}
        </Drawer>
      )}
    </div>
  );
}
