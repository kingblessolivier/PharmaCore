import { useQuery } from "@tanstack/react-query";
import { Building2, Network } from "lucide-react";
import { Card, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { Department, Organization, Paginated } from "../lib/types";

function StatCard({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: number | string;
  icon: typeof Building2;
}) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wide text-ink-500">{label}</span>
        <Icon className="h-4 w-4 text-brand-600" />
      </div>
      <div className="mt-2 text-2xl font-semibold tabular-nums">{value}</div>
    </Card>
  );
}

export function DashboardPage() {
  const { user } = useAuth();
  const orgs = useQuery({
    queryKey: ["organizations"],
    queryFn: () => api<Paginated<Organization>>("/api/organizations/"),
  });
  const depts = useQuery({
    queryKey: ["departments"],
    queryFn: () => api<Paginated<Department>>("/api/departments/"),
  });

  return (
    <div>
      <PageHeader title={`Welcome, ${user?.username ?? ""}`} />
      <p className="mb-5 text-sm text-ink-500">
        PharmaCore — Phase 1. Identity, organizations and departments are live.
      </p>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        <StatCard label="Organizations" value={orgs.data?.count ?? "—"} icon={Building2} />
        <StatCard label="Departments" value={depts.data?.count ?? "—"} icon={Network} />
        <StatCard label="Your roles" value={user?.roles.length ?? 0} icon={Network} />
      </div>
    </div>
  );
}
