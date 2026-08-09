import { useQuery } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { useState } from "react";
import { api } from "../../lib/api";
import type { Paginated } from "../../lib/types";
import { AppHeader, StatTile, WorkQueue } from "../../components/AppHome";
import { useModuleWork } from "../../lib/modulework";
import { ApiKeysModal } from "../../components/ApiKeysModal";
import { ModuleInsights } from "../../components/ModuleInsights";

// Only the count is needed for the overview — fetch a single row.
function useCount(key: string, path: string) {
  return useQuery({
    queryKey: ["count", key],
    queryFn: () => api<Paginated<unknown>>(path),
    select: (d) => d.count,
  });
}

export function AdminHome() {
  const work = useModuleWork("admin");
  const [apiKeysOpen, setApiKeysOpen] = useState(false);
  const companies = useCount("companies", "/api/companies/?page_size=1");
  const orgs = useCount("orgs", "/api/organizations/?page_size=1");
  const users = useCount("users", "/api/users/?page_size=1");
  const depts = useCount("departments", "/api/departments/?page_size=1");
  const n = (q: { data?: number; isLoading: boolean }) => (q.isLoading ? "…" : (q.data ?? 0));

  return (
    <div>
      <AppHeader icon={ShieldCheck} hue="#475569" title="Admin" />

      <WorkQueue items={work.items} loading={work.loading} />

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Companies" value={n(companies)} />
        <StatTile label="Organizations" value={n(orgs)} />
        <StatTile label="Users" value={n(users)} />
        <StatTile label="Departments" value={n(depts)} />
      </div>

      <div>
        <h2 className="mb-3 text-base font-semibold tracking-tight text-ink-900">
          Who is in the system, and what is expiring
        </h2>
        <ModuleInsights module="admin" />
      </div>
      {apiKeysOpen && <ApiKeysModal onClose={() => setApiKeysOpen(false)} />}
    </div>
  );
}
