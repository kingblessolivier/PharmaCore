import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Settings2, ShieldCheck, Sliders, Trash2 } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { OrganizationForm } from "../components/OrganizationForm";
import { OrgOnboardingModal, type OnboardingOrg } from "../components/OrgOnboardingModal";
import { OrgSettingsModal } from "../components/OrgSettingsModal";
import { Badge, Button, ConfirmModal, Modal, PageHeader, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { isAdmin } from "../lib/roles";
import type { Organization, Paginated } from "../lib/types";

export function OrganizationsPage() {
  const { user } = useAuth();
  const admin = isAdmin(user);
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<Organization | null>(null);
  const [onboarding, setOnboarding] = useState<OnboardingOrg | null>(null);
  const [settingsFor, setSettingsFor] = useState<Organization | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["organizations"],
    queryFn: () => api<Paginated<Organization>>("/api/organizations/"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api<void>(`/api/organizations/${id}/`, { method: "DELETE" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["organizations"] });
      setDeleting(null);
    },
  });

  return (
    <div>
      <PageHeader
        title="Organizations"
        action={
          admin && (
            <Button onClick={() => setCreating(true)}>
              <Plus className="h-4 w-4" /> Register organization
            </Button>
          )
        }
      />

      {isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}
      {isError && <p className="text-sm text-red-600">Failed to load organizations.</p>}

      {data && (
        <div className="overflow-hidden rounded-lg border border-line bg-surface-0">
          <table className="w-full text-sm">
            <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-2.5">Name</th>
                <th className="px-4 py-2.5">Type</th>
                <th className="px-4 py-2.5">TIN</th>
                <th className="px-4 py-2.5">District</th>
                <th className="px-4 py-2.5">Status</th>
                <th className="px-4 py-2.5 text-right">Manage</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((o) => (
                <tr key={o.id} className="border-b border-line last:border-0 hover:bg-surface-100">
                  <td className="px-4 py-2.5 font-medium">{o.name}</td>
                  <td className="px-4 py-2.5">
                    <Badge tone={o.type === "DEPOT" ? "depot" : "retail"}>{o.type}</Badge>
                  </td>
                  <td className="px-4 py-2.5 font-mono text-ink-700">{o.tin || "—"}</td>
                  <td className="px-4 py-2.5 text-ink-700">{o.district || "—"}</td>
                  <td className="px-4 py-2.5">
                    {o.is_active ? (
                      <span className="text-green-700">Active</span>
                    ) : (
                      <span className="text-ink-500">Inactive</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex justify-end gap-1">
                      <Button variant="secondary" onClick={() => navigate(`/organizations/${o.id}`)}>
                        <Settings2 className="h-4 w-4" /> Manage
                      </Button>
                      {admin && (
                        <Button
                          variant="secondary"
                          onClick={() =>
                            setOnboarding({
                              id: o.id,
                              name: o.name,
                              onboarding_status:
                                (o as unknown as { onboarding_status?: string }).onboarding_status ??
                                "ACTIVE",
                            })
                          }
                        >
                          <ShieldCheck className="h-4 w-4" /> Onboarding
                        </Button>
                      )}
                      {admin && (
                        <Button variant="secondary" onClick={() => setSettingsFor(o)}>
                          <Sliders className="h-4 w-4" /> Settings
                        </Button>
                      )}
                      {admin && (
                        <button
                          onClick={() => setDeleting(o)}
                          className="rounded-md p-1.5 text-ink-500 hover:bg-red-50 hover:text-red-600"
                          aria-label={`Delete ${o.name}`}
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {data.results.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-ink-500">
                    No organizations yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {creating && (
        <Modal title="Register organization" onClose={() => setCreating(false)}>
          <OrganizationForm
            onDone={(o) => {
              setCreating(false);
              navigate(`/organizations/${o.id}`);
            }}
            onCancel={() => setCreating(false)}
          />
        </Modal>
      )}
      {onboarding && (
        <OrgOnboardingModal org={onboarding} onClose={() => setOnboarding(null)} />
      )}
      {settingsFor && (
        <OrgSettingsModal
          orgId={settingsFor.id}
          orgName={settingsFor.name}
          onClose={() => setSettingsFor(null)}
        />
      )}
      {deleting && (
        <ConfirmModal
          title="Delete organization"
          message={`Delete "${deleting.name}"? This also removes its departments and is recorded in the audit log. This can't be undone.`}
          busy={deleteMutation.isPending}
          onConfirm={() => deleteMutation.mutate(deleting.id)}
          onClose={() => setDeleting(null)}
        />
      )}
    </div>
  );
}
