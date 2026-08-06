import { useQuery } from "@tanstack/react-query";
import { ShieldCheck, UserPlus, Users, Wallet } from "lucide-react";
import { api } from "../../lib/api";
import type { Employee, Paginated } from "../../lib/types";
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
      </div>

      <QuickActions>
        <QuickAction to="/people/employees" icon={UserPlus} label="Add employee" primary />
      </QuickActions>

      <SectionGrid>
        <SectionCard
          icon={Users}
          title="Employees"
          description="The employee master — personal details, licences, documents, offboarding."
          to="/people/employees"
          meta={all.data?.count}
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
          description="Terminations and payroll runs route through the approvals inbox."
          to="/approvals"
        />
      </SectionGrid>
    </div>
  );
}
