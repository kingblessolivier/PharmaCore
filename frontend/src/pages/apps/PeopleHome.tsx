import { useQuery } from "@tanstack/react-query";
import {
  BadgeCheck,
  CalendarDays,
  ClipboardCheck,
  Clock,
  DoorClosed,
  FileCheck2,
  GraduationCap,
  HandCoins,
  TriangleAlert,
  UserCog,
  UserPlus,
  Users,
  Wallet,
} from "lucide-react";
import { Link } from "react-router-dom";
import {
  AppHeader,
  QuickAction,
  QuickActions,
  SectionCard,
  SectionGrid,
  StatTile,
} from "../../components/AppHome";
import { Card } from "../../components/ui";
import { api } from "../../lib/api";
import type { PeopleOverview } from "../../lib/people";

export function PeopleHome() {
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
    <div className="flex max-w-6xl flex-col gap-6">
      <AppHeader
        icon={Users}
        hue="#EA580C"
        title="People"
        subtitle="Who works here, what they earn and how it is calculated, whether they are present, and whether they are still qualified to do the job — from the day they apply to the day they are cleared."
      />

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
          The employee lifecycle
        </h2>
        <SectionGrid>
          <SectionCard
            icon={UserPlus}
            title="Recruitment"
            description="Requisition → applicants → interviews → offer. Hiring creates the employee, contract, opening salary and onboarding in one step."
            to="/people/recruitment"
            meta={o?.open_requisitions ?? 0}
          />
          <SectionCard
            icon={UserCog}
            title="Employees"
            description="The master record: identity, statutory registration, contracts, itemised pay structure, leave, training and competencies."
            to="/people/employees"
            meta={o?.headcount ?? 0}
          />
          <SectionCard
            icon={Clock}
            title="Time & attendance"
            description="The clock feed — punches, lateness and overtime, which the timesheet is derived from."
            to="/people/attendance"
          />
          <SectionCard
            icon={ClipboardCheck}
            title="Timesheets"
            description="The approved, calculated period. Payroll reads this, never raw punches, and a run is blocked while one is pending."
            to="/people/timesheets"
            meta={o?.timesheets_pending ?? 0}
          />
          <SectionCard
            icon={CalendarDays}
            title="Leave"
            description="Requests held against a real balance, with accrual, carry-over and encashment on exit."
            to="/people/leave"
            meta={o?.leave_requests_pending ?? 0}
          />
          <SectionCard
            icon={BadgeCheck}
            title="Shift roster"
            description="Credential-based scheduling — every shift needs a pharmacist on cover."
            to="/people/roster"
          />
          <SectionCard
            icon={Wallet}
            title="Payroll"
            description="Gross→net from the statutory rates in force at period end. Never self-approved; posts to the ledger."
            to="/people/payroll"
          />
          <SectionCard
            icon={HandCoins}
            title="Loans & advances"
            description="Amortised staff loans deducted by payroll, skipped (not lost) when the employee had unpaid leave."
            to="/people/loans"
            meta={o?.loans_active ?? 0}
          />
          <SectionCard
            icon={FileCheck2}
            title="Statutory filings"
            description="PAYE, RSSB, CBHI, VAT and PIT returns — reconciled to the GL sub-ledger before they can be filed."
            to="/people/filings"
            meta={o?.filings_due ?? 0}
          />
          <SectionCard
            icon={DoorClosed}
            title="Offboarding"
            description="Notice, clearance checklist and the final settlement: leave encashment, pro-rata pay, loan recovery."
            to="/people/offboarding"
          />
          <SectionCard
            icon={GraduationCap}
            title="Statutory rates"
            description="PAYE bands, RSSB, maternity, CBHI and occupational hazards — effective-dated data, never hardcoded."
            to="/people/statutory-rates"
          />
        </SectionGrid>
      </div>
    </div>
  );
}
