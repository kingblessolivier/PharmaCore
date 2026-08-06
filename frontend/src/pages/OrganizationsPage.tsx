import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Settings2, ShieldCheck, Sliders, Trash2 } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { OrganizationForm } from "../components/OrganizationForm";
import { OrgOnboardingModal, type OnboardingOrg } from "../components/OrgOnboardingModal";
import { OrgSettingsModal } from "../components/OrgSettingsModal";
import { Badge, Button, ConfirmModal, Modal, PageHeader } from "../components/ui";
import { DataGrid } from "../components/DataGrid";
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

      <DataGrid<Organization>
        rows={data?.results ?? []}
        loading={isLoading}
        getRowId={(o) => o.id}
        storageKey="organizations"
        exportName="organizations"
        searchPlaceholder="Search organizations by name, TIN, district…"
        emptyMessage="No organizations yet."
        columns={[
          {
            key: "name",
            header: "Name",
            render: (o) => <span className="font-medium">{o.name}</span>,
          },
          {
            key: "type",
            header: "Type",
            value: (o) => o.type,
            render: (o) => <Badge tone={o.type === "DEPOT" ? "depot" : "retail"}>{o.type}</Badge>,
          },
          {
            key: "tin",
            header: "TIN",
            value: (o) => o.tin || "—",
            render: (o) => <span className="font-mono text-ink-700">{o.tin || "—"}</span>,
          },
          { key: "district", header: "District", value: (o) => o.district || "—" },
          {
            key: "is_active",
            header: "Status",
            value: (o) => (o.is_active ? "Active" : "Inactive"),
            render: (o) =>
              o.is_active ? (
                <span className="text-green-700">Active</span>
              ) : (
                <span className="text-ink-500">Inactive</span>
              ),
          },
          {
            key: "actions",
            header: "Manage",
            align: "right",
            fixed: true,
            sortable: false,
            render: (o) => (
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
            ),
          },
        ]}
      />
      {isError && <p className="text-sm text-red-600">Failed to load organizations.</p>}

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
