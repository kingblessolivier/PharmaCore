import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Pencil } from "lucide-react";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { OrganizationForm } from "../components/OrganizationForm";
import { OrgCatalogTab } from "../components/OrgCatalogTab";
import { OrgLicensesTab } from "../components/OrgLicensesTab";
import { OrgLogsTab } from "../components/OrgLogsTab";
import { OrgStockTab } from "../components/OrgStockTab";
import { OrgUsersTab } from "../components/OrgUsersTab";
import { Badge, Button, Card, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { isAdmin } from "../lib/roles";
import type { Organization } from "../lib/types";

type Tab = "details" | "users" | "catalog" | "stock" | "licences" | "logs";

function Field({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div>
      <div className="text-xs font-medium uppercase tracking-wide text-ink-500">{label}</div>
      <div className="mt-0.5 text-sm text-ink-900">{value || "—"}</div>
    </div>
  );
}

export function OrganizationDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const admin = isAdmin(user);
  const [editing, setEditing] = useState(false);
  const [tab, setTab] = useState<Tab>("details");

  const { data: org, isLoading, isError } = useQuery({
    queryKey: ["organization", Number(id)],
    queryFn: () => api<Organization>(`/api/organizations/${id}/`),
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-10">
        <Spinner />
      </div>
    );
  }
  if (isError || !org) {
    return <p className="text-sm text-red-600">Organization not found or not accessible.</p>;
  }

  const tabs: { id: Tab; label: string }[] = [
    { id: "details", label: "Details" },
    { id: "users", label: "Users & roles" },
    { id: "catalog", label: "Catalog & pricing" },
    { id: "stock", label: "Stock" },
    { id: "licences", label: "Licences" },
    { id: "logs", label: "Activity logs" },
  ];

  return (
    <div className="max-w-4xl">
      <button
        onClick={() => navigate("/organizations")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> Organizations
      </button>

      <div className="mb-4 flex items-start justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold tracking-tight text-ink-900">{org.name}</h1>
          <Badge tone={org.type === "DEPOT" ? "depot" : "retail"}>{org.type}</Badge>
          {org.is_active ? (
            <span className="text-sm text-green-700">Active</span>
          ) : (
            <span className="text-sm text-ink-500">Inactive</span>
          )}
        </div>
        {admin && !editing && tab === "details" && (
          <Button variant="secondary" onClick={() => setEditing(true)}>
            <Pencil className="h-4 w-4" /> Edit details
          </Button>
        )}
      </div>

      <div className="mb-5 flex gap-1 border-b border-line">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium ${
              tab === t.id
                ? "border-brand-600 text-brand-700"
                : "border-transparent text-ink-500 hover:text-ink-900"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "details" && (
        <Card className="p-6">
          <h2 className="mb-4 text-sm font-semibold text-ink-900">Pharmacy details</h2>
          {editing ? (
            <OrganizationForm org={org} onDone={() => setEditing(false)} onCancel={() => setEditing(false)} />
          ) : (
            <div className="grid grid-cols-2 gap-5 sm:grid-cols-3">
              <Field label="Type" value={org.type} />
              <Field label="Status" value={org.is_active ? "Active" : "Inactive"} />
              <Field label="TIN (RRA)" value={org.tin} />
              <Field label="Rwanda FDA licence" value={org.rwanda_fda_license_no} />
              <Field label="Licence expiry" value={org.license_expiry_date} />
              <Field label="Phone" value={org.phone} />
              <Field label="Email" value={org.email} />
              <Field label="District" value={org.district} />
              <Field label="Sector" value={org.sector} />
              <Field label="Cell" value={org.cell} />
              <Field label="Latitude" value={org.latitude} />
              <Field label="Longitude" value={org.longitude} />
              <div className="col-span-2 sm:col-span-3">
                <Field label="Address" value={org.address_line} />
              </div>
            </div>
          )}
        </Card>
      )}

      {tab === "users" && <OrgUsersTab organizationId={org.id} />}
      {tab === "catalog" && <OrgCatalogTab organizationId={org.id} orgType={org.type} />}
      {tab === "stock" && <OrgStockTab organizationId={org.id} />}
      {tab === "licences" && <OrgLicensesTab organizationId={org.id} />}
      {tab === "logs" && <OrgLogsTab organizationId={org.id} />}
    </div>
  );
}
