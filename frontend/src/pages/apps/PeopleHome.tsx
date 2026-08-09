import { useQuery } from "@tanstack/react-query";
import {
  CalendarDays,
  ClipboardCheck,
  FileCheck2,
  TriangleAlert,
  Users,
  Wallet,
} from "lucide-react";
import { Link } from "react-router-dom";
import {
  AppHeader,
  QuickAction,
  QuickActions,
  StatTile,
  WorkQueue,
} from "../../components/AppHome";
import { useModuleWork } from "../../lib/modulework";
import { Card } from "../../components/ui";
import { api } from "../../lib/api";
import type { PeopleOverview } from "../../lib/people";
import { ModuleInsights } from "../../components/ModuleInsights";

export function PeopleHome() {
  const work = useModuleWork("people");
  const { data } = useQuery({
    queryKey: ["people-overview"],
    queryFn: () => api<PeopleOverview>("/api/hr/overview/"),
  });

  const o = data;
  const a = o?.alerts;

  const attention = [
    {
      show: (o?.timesheets_pending ?? 0) > 0,
      tone: "amber",
      label: `${o?.timesheets_pending} timesheet(s) unapproved — payroll is blocked until they are decided`,
      to: "/people/timesheets",
    },
    {
      show: (o?.filings_overdue ?? 0) > 0,
      tone: "red",
      label: `${o?.filings_overdue} statutory return(s) past their due date`,
      to: "/people/filings",
    },
    {
      show: (o?.leave_requests_pending ?? 0) > 0,
      tone: "amber",
      label: `${o?.leave_requests_pending} leave request(s) waiting on a decision`,
      to: "/people/leave",
    },
    {
      show: (o?.training_overdue ?? 0) > 0,
      tone: "amber",
      label: `${o?.training_overdue} mandatory training item(s) overdue`,
      to: "/people/employees",
    },
    {
      show: (a?.contracts_expiring?.length ?? 0) > 0,
      tone: "amber",
      label: `${a?.contracts_expiring.length} contract(s) expire within 60 days`,
      to: "/people/employees",
    },
    {
      show: (a?.probations_ending?.length ?? 0) > 0,
      tone: "amber",
      label: `${a?.probations_ending.length} probation period(s) ending — confirm or act`,
      to: "/people/employees",
    },
    {
      show: (a?.work_permits_expiring?.length ?? 0) > 0,
      tone: "red",
      label: `${a?.work_permits_expiring.length} work permit(s) expiring — rostering will be blocked`,
      to: "/people/employees",
    },
    {
      show: (a?.competencies_expiring?.length ?? 0) > 0,
      tone: "red",
      label: `${a?.competencies_expiring.length} competency assessment(s) lapsing — including controlled-drug handling`,
      to: "/people/employees",
    },
    {
      show: (a?.loans_overdue ?? 0) > 0,
      tone: "amber",
      label: `${a?.loans_overdue} loan installment(s) overdue`,
      to: "/people/loans",
    },
  ].filter((x) => x.show);

  return (
    <div className="flex flex-col gap-6">
      <AppHeader icon={Users} hue="#EA580C" title="People" />

      <WorkQueue items={work.items} loading={work.loading} />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
        <Link to="/people/employees">
          <StatTile label="Headcount" value={o?.headcount ?? 0} hint="active staff" />
        </Link>
        <Link to="/people/attendance">
          <StatTile label="Present today" value={o?.present_today ?? 0} hint="clocked in" />
        </Link>
        <Link to="/people/leave">
          <StatTile label="On leave" value={o?.on_leave_today ?? 0} hint="approved today" />
        </Link>
        <Link to="/people/timesheets">
          <StatTile
            label="Timesheets"
            value={o?.timesheets_pending ?? 0}
            hint="awaiting approval"
          />
        </Link>
        <Link to="/people/recruitment">
          <StatTile label="In the funnel" value={o?.applicants_in_funnel ?? 0} hint="applicants" />
        </Link>
        <Link to="/people/filings">
          <StatTile label="Returns due" value={o?.filings_due ?? 0} hint="PAYE / RSSB / CBHI" />
        </Link>
      </div>

      <QuickActions>
        <QuickAction to="/people/payroll" icon={Wallet} label="Run payroll" primary />
        <QuickAction to="/people/timesheets" icon={ClipboardCheck} label="Approve timesheets" />
        <QuickAction to="/people/leave" icon={CalendarDays} label="Decide leave" />
        <QuickAction to="/people/filings" icon={FileCheck2} label="File a return" />
      </QuickActions>

      {attention.length > 0 && (
        <Card className="p-5">
          <div className="flex items-center gap-2 border-b border-line pb-3">
            <TriangleAlert className="h-4 w-4 text-amber-600" />
            <h3 className="text-sm font-semibold text-ink-900">Needs your attention</h3>
          </div>
          <ul className="mt-3 flex flex-col gap-2 text-sm">
            {attention.map((item) => (
              <li key={item.label}>
                <Link
                  to={item.to}
                  className={`flex items-center justify-between rounded-md px-3 py-2 ${
                    item.tone === "red"
                      ? "bg-red-50 text-red-800 hover:bg-red-100"
                      : "bg-amber-50 text-amber-900 hover:bg-amber-100"
                  }`}
                >
                  <span>{item.label}</span>
                  <span className="text-xs font-semibold">Open →</span>
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <div>
        <h2 className="mb-3 text-base font-semibold tracking-tight text-ink-900">
          The shape of the workforce
        </h2>
        <ModuleInsights module="people" />
      </div>
    </div>
  );
}
