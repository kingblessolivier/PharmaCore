/* -------------------------------------------------------------------------- */
/* The half of People that had no screen.                                      */
/*                                                                            */
/* Onboarding, performance reviews, disciplinary actions, CPD, interviews and  */
/* payroll adjustments were all fully modelled, serialized, routed and         */
/* permission-gated — and unreachable. An HR manager could not open a single   */
/* one of them, which meant a pharmacist's CPD hours (the thing their licence  */
/* depends on) had nowhere to be recorded.                                     */
/*                                                                            */
/* One page with tabs rather than six menu entries: they are all "the record   */
/* of one person", and splitting them across the nav is how People ended up    */
/* looking finished while most of it was closed.                               */
/* -------------------------------------------------------------------------- */

import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import {
  Award,
  CalendarCheck,
  ClipboardList,
  Gavel,
  Star,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import { PageHeader } from "../components/ui";
import { DataGrid, type Column } from "../components/DataGrid";
import { api } from "../lib/api";
import type { Paginated } from "../lib/types";
import { shortDate } from "../lib/format";

/* -------------------------------------------------------------------------- */

interface Onboarding {
  id: number;
  employee_name: string;
  started_on: string | null;
  target_completion: string | null;
  completed_at: string | null;
  progress_pct: number;
  notes: string;
}

interface Review {
  id: number;
  employee_name: string;
  reviewer_name: string | null;
  kind_display: string;
  status_display: string;
  period_start: string | null;
  period_end: string | null;
  rating: string | null;
}

interface Disciplinary {
  id: number;
  employee_name: string;
  kind_display: string;
  status_display: string;
  incident_date: string | null;
  issued_on: string | null;
  expires_on: string | null;
  reason: string;
}

interface CPD {
  id: number;
  employee_name: string;
  activity: string;
  activity_date: string | null;
  hours: string;
  provider: string;
  cpd_year: number;
  is_accredited: boolean;
  accreditation_body: string;
}

interface Interview {
  id: number;
  applicant: number;
  round_number: number;
  scheduled_at: string | null;
  mode: string;
  location: string;
  score: string | null;
  decision_display: string;
}

interface Adjustment {
  id: number;
  employee_name: string;
  kind_display: string;
  amount: string;
  is_taxable: boolean;
  in_pension_base: boolean;
  reason: string;
  apply_from: string | null;
}

/* -------------------------------------------------------------------------- */

const TABS: { id: string; label: string; icon: LucideIcon; hint: string }[] = [
  {
    id: "onboarding",
    label: "Onboarding",
    icon: ClipboardList,
    hint: "Who has joined and what is still outstanding before they can work unsupervised.",
  },
  {
    id: "cpd",
    label: "CPD",
    icon: Award,
    hint: "Continuing professional development. A pharmacist's licence depends on these hours.",
  },
  {
    id: "reviews",
    label: "Performance",
    icon: Star,
    hint: "Appraisals, and where each one has got to.",
  },
  {
    id: "disciplinary",
    label: "Disciplinary",
    icon: Gavel,
    hint: "Warnings on file, and when each one lapses.",
  },
  {
    id: "interviews",
    label: "Interviews",
    icon: CalendarCheck,
    hint: "Scheduled rounds and what the panel decided.",
  },
  {
    id: "adjustments",
    label: "Pay adjustments",
    icon: Wallet,
    hint: "One-off additions and deductions, and whether payroll taxes them.",
  },
];

export function PeopleRecordsPage() {
  const [params, setParams] = useSearchParams();
  const active = TABS.find((t) => t.id === params.get("tab")) ?? TABS[0];

  return (
    <div className="space-y-4">
      <PageHeader title="Employee records" />

      <div className="flex flex-wrap gap-1 border-b border-line">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const on = tab.id === active.id;
          return (
            <button
              key={tab.id}
              onClick={() => setParams({ tab: tab.id })}
              className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium ${
                on
                  ? "border-b-2 border-brand-600 text-brand-700"
                  : "text-ink-500 hover:text-ink-900"
              }`}
            >
              <Icon className="h-4 w-4" aria-hidden />
              {tab.label}
            </button>
          );
        })}
      </div>

      <p className="text-xs text-ink-500">{active.hint}</p>

      {active.id === "onboarding" && <OnboardingTab />}
      {active.id === "cpd" && <CpdTab />}
      {active.id === "reviews" && <ReviewsTab />}
      {active.id === "disciplinary" && <DisciplinaryTab />}
      {active.id === "interviews" && <InterviewsTab />}
      {active.id === "adjustments" && <AdjustmentsTab />}
    </div>
  );
}

/* -------------------------------------------------------------------------- */

function useRows<T>(key: string, path: string) {
  return useQuery({
    queryKey: [key],
    queryFn: () => api<Paginated<T>>(path),
  });
}

function Grid<T extends { id: number }>({
  rows,
  loading,
  columns,
  empty,
  storageKey,
}: {
  rows: T[];
  loading: boolean;
  columns: Column<T>[];
  empty: string;
  storageKey: string;
}) {
  return (
    <DataGrid
      rows={rows}
      columns={columns}
      loading={loading}
      getRowId={(r) => r.id}
      emptyMessage={empty}
      storageKey={storageKey}
      exportName={storageKey}
    />
  );
}

function OnboardingTab() {
  const { data, isLoading } = useRows<Onboarding>("hr-onboarding", "/api/hr/onboarding/");
  return (
    <Grid
      rows={data?.results ?? []}
      storageKey="hr-onboarding"
      loading={isLoading}
      empty="Nobody is part-way through onboarding."
      columns={[
        { key: "employee_name", header: "Employee", value: (r) => r.employee_name },
        { key: "started_on", header: "Started", value: (r) => shortDate(r.started_on) },
        { key: "target", header: "Due", value: (r) => shortDate(r.target_completion) },
        {
          key: "progress",
          header: "Progress",
          align: "right",
          value: (r) => r.progress_pct,
          render: (r) => (
            <span className="flex items-center justify-end gap-2">
              <span className="h-1.5 w-20 overflow-hidden rounded-full bg-surface-200">
                <span
                  className="block h-full bg-brand-600"
                  style={{ width: `${Math.min(100, r.progress_pct)}%` }}
                />
              </span>
              <span className="tabular-nums">{r.progress_pct}%</span>
            </span>
          ),
        },
        {
          key: "state",
          header: "State",
          value: (r) => (r.completed_at ? "Complete" : "In progress"),
        },
      ]}
    />
  );
}

function CpdTab() {
  const { data, isLoading } = useRows<CPD>("hr-cpd", "/api/hr/cpd/");
  return (
    <Grid
      rows={data?.results ?? []}
      storageKey="hr-cpd"
      loading={isLoading}
      empty="No CPD recorded. A pharmacist's licence renewal depends on these hours."
      columns={[
        { key: "employee_name", header: "Employee", value: (r) => r.employee_name },
        { key: "activity", header: "Activity", value: (r) => r.activity },
        { key: "provider", header: "Provider", value: (r) => r.provider || "—" },
        { key: "activity_date", header: "Date", value: (r) => shortDate(r.activity_date) },
        { key: "hours", header: "Hours", align: "right", value: (r) => Number(r.hours) },
        {
          key: "accredited",
          header: "Accredited",
          value: (r) => (r.is_accredited ? r.accreditation_body || "Yes" : "No"),
        },
      ]}
    />
  );
}

function ReviewsTab() {
  const { data, isLoading } = useRows<Review>("hr-reviews", "/api/hr/reviews/");
  return (
    <Grid
      rows={data?.results ?? []}
      storageKey="hr-reviews"
      loading={isLoading}
      empty="No appraisals on file."
      columns={[
        { key: "employee_name", header: "Employee", value: (r) => r.employee_name },
        { key: "reviewer_name", header: "Reviewer", value: (r) => r.reviewer_name ?? "—" },
        { key: "kind", header: "Kind", value: (r) => r.kind_display },
        {
          key: "period",
          header: "Period",
          value: (r) => `${shortDate(r.period_start)} – ${shortDate(r.period_end)}`,
        },
        { key: "rating", header: "Rating", align: "right", value: (r) => r.rating ?? "—" },
        { key: "status", header: "Status", value: (r) => r.status_display },
      ]}
    />
  );
}

function DisciplinaryTab() {
  const { data, isLoading } = useRows<Disciplinary>("hr-disciplinary", "/api/hr/disciplinary/");
  return (
    <Grid
      rows={data?.results ?? []}
      storageKey="hr-disciplinary"
      loading={isLoading}
      empty="Nothing on file."
      columns={[
        { key: "employee_name", header: "Employee", value: (r) => r.employee_name },
        { key: "kind", header: "Kind", value: (r) => r.kind_display },
        { key: "incident", header: "Incident", value: (r) => shortDate(r.incident_date) },
        { key: "issued", header: "Issued", value: (r) => shortDate(r.issued_on) },
        // A warning that has lapsed must not still count against somebody.
        { key: "expires", header: "Lapses", value: (r) => shortDate(r.expires_on) },
        { key: "status", header: "Status", value: (r) => r.status_display },
      ]}
    />
  );
}

function InterviewsTab() {
  const { data, isLoading } = useRows<Interview>("hr-interviews", "/api/hr/interviews/");
  return (
    <Grid
      rows={data?.results ?? []}
      storageKey="hr-interviews"
      loading={isLoading}
      empty="No interviews scheduled."
      columns={[
        { key: "applicant", header: "Applicant", value: (r) => `#${r.applicant}` },
        { key: "round", header: "Round", align: "right", value: (r) => r.round_number },
        { key: "when", header: "When", value: (r) => shortDate(r.scheduled_at) },
        { key: "mode", header: "Mode", value: (r) => r.mode },
        { key: "location", header: "Where", value: (r) => r.location || "—" },
        { key: "score", header: "Score", align: "right", value: (r) => r.score ?? "—" },
        { key: "decision", header: "Decision", value: (r) => r.decision_display },
      ]}
    />
  );
}

function AdjustmentsTab() {
  const { data, isLoading } = useRows<Adjustment>(
    "hr-payroll-adjustments",
    "/api/hr/payroll-adjustments/",
  );
  return (
    <Grid
      rows={data?.results ?? []}
      storageKey="hr-adjustments"
      loading={isLoading}
      empty="No one-off additions or deductions pending."
      columns={[
        { key: "employee_name", header: "Employee", value: (r) => r.employee_name },
        { key: "kind", header: "Kind", value: (r) => r.kind_display },
        {
          key: "amount",
          header: "Amount",
          align: "right",
          value: (r) => Number(r.amount),
          render: (r) => <span className="tabular-nums">{Number(r.amount).toLocaleString()}</span>,
        },
        // Both change what the employee actually receives, so neither is a
        // detail: a taxable addition and a tax-free one net differently.
        { key: "taxable", header: "Taxed", value: (r) => (r.is_taxable ? "Yes" : "No") },
        {
          key: "pension",
          header: "In pension base",
          value: (r) => (r.in_pension_base ? "Yes" : "No"),
        },
        { key: "from", header: "From", value: (r) => shortDate(r.apply_from) },
        { key: "reason", header: "Why", value: (r) => r.reason || "—" },
      ]}
    />
  );
}
