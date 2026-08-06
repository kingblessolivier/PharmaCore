import { useQuery } from "@tanstack/react-query";
import { Calendar, ClipboardCheck, Clock, ShieldCheck, UserCheck, UserPlus, Users, Wallet } from "lucide-react";
import { api } from "../../lib/api";
import type { Employee, LeaveRequest, Paginated, ShiftRoster } from "../../lib/types";
import { AppHeader, QuickAction, QuickActions, SectionCard, SectionGrid, StatTile } from "../../components/AppHome";

export function PeopleHome() {
  const active = useQuery({
    queryKey: ["employees", "ACTIVE"],
    queryFn: () => api<Paginated<Employee>>("/api/hr/employees/?status=ACTIVE"),
  });
  const probation = useQuery({
    queryKey: ["employees", "PROBATION"],
    queryFn: () => api<Paginated<Employee>>("/api/hr/employees/?status=PROBATION"),
  });
  const all = useQuery({ queryKey: ["employees", "all"], queryFn: () => api<Paginated<Employee>>("/api/hr/employees/") });

  // ---- Operational tiles: things the HR officer needs to see *today* ----
  const today = new Date().toISOString().slice(0, 10);
  const onLeaveToday = useQuery<Paginated<LeaveRequest>>({
    queryKey: ["leave", "today"],
    queryFn: () => api<Paginated<LeaveRequest>>(
      `/api/hr/leave/?start_date__lte=${today}&end_date__gte=${today}&status=APPROVED`,
    ),
  });
  const pendingLeave = useQuery<Paginated<LeaveRequest>>({
    queryKey: ["leave", "pending"],
    queryFn: () => api<Paginated<LeaveRequest>>("/api/hr/leave/?status=PENDING"),
  });
  const rosterToday = useQuery<Paginated<ShiftRoster>>({
    queryKey: ["roster", "today"],
    queryFn: () => api<Paginated<ShiftRoster>>(`/api/hr/roster/?date=${today}`),
  });

  return (
    <div>
      <AppHeader
        icon={Users}
        hue="#EA580C"
        title="People"
        subtitle="Who works here, their licences, and their employment status — the foundation for attendance and payroll."
      />

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Total employees" value={all.data?.count ?? "…"} />
        <StatTile label="Active" value={active.data?.count ?? "…"} />
        <StatTile label="On probation" value={probation.data?.count ?? "…"} />
        <StatTile label="On leave today" value={onLeaveToday.data?.count ?? "…"} />
      </div>

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Pending leave requests" value={pendingLeave.data?.count ?? "…"} />
        <StatTile label="Rostered today" value={rosterToday.data?.count ?? "…"} />
      </div>

      <QuickActions>
        <QuickAction to="/people/employees" icon={UserPlus} label="Add employee" primary />
        <QuickAction to="/people/attendance" icon={Clock} label="Clock in / out" />
        <QuickAction to="/people/leave" icon={UserCheck} label="Manage leave" />
        <QuickAction to="/people/payroll" icon={Wallet} label="Run payroll" />
        <QuickAction to="/people/roster" icon={Calendar} label="Weekly roster" />
        <QuickAction to="/approvals" icon={ClipboardCheck} label="Approvals inbox" />
      </QuickActions>

      <SectionGrid>
        <SectionCard
          icon={Users}
          title="Employees"
          description="The employee master — personal details, licences, contracts, gender/DOB, supervisor and contract dates."
          to="/people/employees"
          meta={all.data?.count}
        />
        <SectionCard
          icon={Clock}
          title="Time & Attendance"
          description="Clock-in/out timestamps, overtime hours auto-calculation, and lateness tracking."
          to="/people/attendance"
        />
        <SectionCard
          icon={Calendar}
          title="Shift Rosters"
          description="Credential-based shift scheduling with mandatory pharmacist coverage validation."
          to="/people/roster"
        />
        <SectionCard
          icon={UserCheck}
          title="Leave & Accrual"
          description="Annual, sick, and maternity leave request directory with approval workflow."
          to="/people/leave"
        />
        <SectionCard
          icon={Wallet}
          title="Payroll"
          description="Gross→net for every employee — PAYE, RSSB, CBHI — approval-gated, posts to Finance."
          to="/people/payroll"
        />
        <SectionCard
          icon={ShieldCheck}
          title="Approvals"
          description="Terminations, leave, and payroll runs route through the central approvals inbox."
          to="/approvals"
        />
      </SectionGrid>
    </div>
  );
}
