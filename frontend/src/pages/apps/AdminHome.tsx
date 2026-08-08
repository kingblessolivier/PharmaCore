import { useQuery } from "@tanstack/react-query";
import { Activity, Boxes, Building2, KeyRound, Network, ShieldCheck, Terminal, Users } from "lucide-react";
import { useState } from "react";
import { api } from "../../lib/api";
import type { Paginated } from "../../lib/types";
import {
  AppHeader,
  SectionCard,
  SectionGrid,
  StatTile,
  WorkQueue,
} from "../../components/AppHome";
import { useModuleWork } from "../../lib/modulework";
import { ApiKeysModal } from "../../components/ApiKeysModal";

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
      <AppHeader
        icon={ShieldCheck}
        hue="#475569"
        title="Admin"
        subtitle="Companies, branches, people, access and the audit trail — the control room."
      />

      <WorkQueue items={work.items} loading={work.loading} />

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Companies" value={n(companies)} />
        <StatTile label="Organizations" value={n(orgs)} />
        <StatTile label="Users" value={n(users)} />
        <StatTile label="Departments" value={n(depts)} />
      </div>

      <SectionGrid>
        <SectionCard
          icon={Building2}
          title="Organizations & branches"
          description="Companies and the branches (depots, pharmacies, HQs) they own."
          to="/companies"
          meta={n(companies)}
        />
        <SectionCard
          icon={Network}
          title="Organizations"
          description="Every depot, retail pharmacy and HQ — profile, licences, stock."
          to="/organizations"
          meta={n(orgs)}
        />
        <SectionCard
          icon={Boxes}
          title="Departments"
          description="Operational departments within each organization."
          to="/departments"
          meta={n(depts)}
        />
        <SectionCard
          icon={Users}
          title="Users & roles"
          description="Create and manage staff, assign roles, and view-as any user."
          to="/users"
          meta={n(users)}
        />
        <SectionCard
          icon={KeyRound}
          title="Roles & permissions"
          description="The permission matrix — what each role is allowed to do (resource × action)."
          to="/permissions"
        />
        <SectionCard
          icon={Activity}
          title="Audit log"
          description="The immutable trail of every login, change, and view-as session."
          to="/activity"
        />
        <button
          onClick={() => setApiKeysOpen(true)}
          className="group flex flex-col gap-2 rounded-lg border border-line bg-surface-0 p-4 text-left transition-colors hover:border-brand-600 hover:bg-brand-50/30"
        >
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-surface-100 text-ink-600 group-hover:bg-brand-100 group-hover:text-brand-700">
            <Terminal className="h-4 w-4" />
          </span>
          <span>
            <span className="block text-sm font-semibold text-ink-900">API keys &amp; service accounts</span>
            <span className="block text-xs text-ink-500">
              Machine access keys that act as a chosen user (X-API-Key).
            </span>
          </span>
        </button>
      </SectionGrid>
      {apiKeysOpen && <ApiKeysModal onClose={() => setApiKeysOpen(false)} />}
    </div>
  );
}
