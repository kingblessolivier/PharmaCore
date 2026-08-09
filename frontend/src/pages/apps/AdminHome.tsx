import { ShieldCheck } from "lucide-react";
import { useState } from "react";
import { AppHeader, WorkQueue } from "../../components/AppHome";
import { useModuleWork } from "../../lib/modulework";
import { ApiKeysModal } from "../../components/ApiKeysModal";
import { ModuleInsights } from "../../components/ModuleInsights";

/* -------------------------------------------------------------------------- */
/* Admin — the control room.                                                   */
/*                                                                             */
/* The four hand-rolled count tiles that used to sit here (companies,          */
/* organizations, users, departments) each cost a page-size-1 request and two  */
/* of them then appeared a second time in the figures below. They now come     */
/* from the one aggregate, so the page states each number once.                */
/* -------------------------------------------------------------------------- */

export function AdminHome() {
  const work = useModuleWork("admin");
  const [apiKeysOpen, setApiKeysOpen] = useState(false);

  return (
    <div>
      <AppHeader icon={ShieldCheck} hue="#475569" title="Admin" />

      <WorkQueue items={work.items} loading={work.loading} />

      <div>
        <h2 className="mb-3 text-base font-semibold tracking-tight text-ink-900">
          The system at a glance
        </h2>
        <ModuleInsights
          module="admin"
          trendTitle="System activity, last 14 days"
          trendSubtitle="Sign-ins against records actually changed."
        />
      </div>
      {apiKeysOpen && <ApiKeysModal onClose={() => setApiKeysOpen(false)} />}
    </div>
  );
}
