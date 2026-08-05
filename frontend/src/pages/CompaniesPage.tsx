import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Network, Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { api, ApiError } from "../lib/api";
import type { Company, Organization, Paginated } from "../lib/types";
import { Badge, Button, Modal, PageHeader, SelectField, Spinner, TextField } from "../components/ui";

function CompanyModal({ company, onClose }: { company?: Company; onClose: () => void }) {
  const qc = useQueryClient();
  const editing = Boolean(company);
  const [name, setName] = useState(company?.name ?? "");
  const [legalName, setLegalName] = useState(company?.legal_name ?? "");
  const [tin, setTin] = useState(company?.tin ?? "");
  const [reg, setReg] = useState(company?.registration_number ?? "");
  const [contact, setContact] = useState(company?.contact_person ?? "");
  const [phone, setPhone] = useState(company?.phone ?? "");
  const [email, setEmail] = useState(company?.email ?? "");
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () =>
      api<Company>(editing ? `/api/companies/${company!.id}/` : "/api/companies/", {
        method: editing ? "PATCH" : "POST",
        body: JSON.stringify({
          name,
          legal_name: legalName,
          tin,
          registration_number: reg,
          contact_person: contact,
          phone,
          email,
        }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["companies"] });
      onClose();
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not save the company."),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    save.mutate();
  }

  return (
    <Modal title={editing ? `Edit ${company!.name}` : "Add company"} onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <TextField label="Company name" value={name} onChange={(e) => setName(e.target.value)} required autoFocus />
        <TextField label="Legal name (optional)" value={legalName} onChange={(e) => setLegalName(e.target.value)} />
        <div className="grid grid-cols-2 gap-3">
          <TextField label="TIN (RRA)" value={tin} onChange={(e) => setTin(e.target.value)} />
          <TextField label="Registration no. (RDB)" value={reg} onChange={(e) => setReg(e.target.value)} />
        </div>
        <TextField label="Contact person" value={contact} onChange={(e) => setContact(e.target.value)} />
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
          <TextField label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={save.isPending}>
            {save.isPending ? "Saving…" : editing ? "Save" : "Add company"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function BranchesModal({ company, onClose }: { company: Company; onClose: () => void }) {
  const qc = useQueryClient();
  const [assignId, setAssignId] = useState("");
  const orgs = useQuery({
    queryKey: ["organizations"],
    queryFn: () => api<Paginated<Organization>>("/api/organizations/"),
  });
  const all = orgs.data?.results ?? [];
  const branches = all.filter((o) => o.company === company.id);
  const unassigned = all.filter((o) => o.company === null);

  const assign = useMutation({
    mutationFn: (orgId: number) =>
      api<Organization>(`/api/organizations/${orgId}/`, {
        method: "PATCH",
        body: JSON.stringify({ company: company.id }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["organizations"] });
      void qc.invalidateQueries({ queryKey: ["companies"] });
      setAssignId("");
    },
  });
  const detach = useMutation({
    mutationFn: (orgId: number) =>
      api<Organization>(`/api/organizations/${orgId}/`, {
        method: "PATCH",
        body: JSON.stringify({ company: null }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["organizations"] });
      void qc.invalidateQueries({ queryKey: ["companies"] });
    },
  });

  return (
    <Modal title={`${company.name} — branches`} onClose={onClose}>
      <div className="flex flex-col gap-4">
        {orgs.isLoading && (
          <div className="flex justify-center py-6">
            <Spinner />
          </div>
        )}
        {orgs.data && (
          <>
            <div className="overflow-hidden rounded-lg border border-line">
              <table className="w-full text-sm">
                <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-500">
                  <tr>
                    <th className="px-3 py-2">Branch</th>
                    <th className="px-3 py-2">Type</th>
                    <th className="px-3 py-2 text-right">—</th>
                  </tr>
                </thead>
                <tbody>
                  {branches.map((o) => (
                    <tr key={o.id} className="border-b border-line last:border-0">
                      <td className="px-3 py-2 font-medium">{o.name}</td>
                      <td className="px-3 py-2">
                        <Badge>{o.type}</Badge>
                      </td>
                      <td className="px-3 py-2 text-right">
                        <Button variant="secondary" onClick={() => detach.mutate(o.id)}>
                          Detach
                        </Button>
                      </td>
                    </tr>
                  ))}
                  {branches.length === 0 && (
                    <tr>
                      <td colSpan={3} className="px-3 py-5 text-center text-ink-500">
                        No branches yet — attach one below.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            <div className="flex items-end gap-2">
              <div className="flex-1">
                <SelectField
                  label="Attach an existing organization"
                  value={assignId}
                  onChange={(e) => setAssignId(e.target.value)}
                >
                  <option value="">— select organization —</option>
                  {unassigned.map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.name} ({o.type})
                    </option>
                  ))}
                </SelectField>
              </div>
              <Button disabled={!assignId || assign.isPending} onClick={() => assign.mutate(Number(assignId))}>
                Attach
              </Button>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}

export function CompaniesPage() {
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<Company | null>(null);
  const [viewing, setViewing] = useState<Company | null>(null);

  const companies = useQuery({
    queryKey: ["companies"],
    queryFn: () => api<Paginated<Company>>("/api/companies/"),
  });

  return (
    <div>
      <PageHeader
        title="Companies"
        action={
          <Button onClick={() => setAdding(true)}>
            <Plus className="h-4 w-4" /> Add company
          </Button>
        }
      />
      <p className="mb-4 -mt-2 text-sm text-ink-500">
        A company is the legal business that owns one or more branches. A single pharmacy is one
        company with one branch; a chain is a company with an HQ and several branches.
      </p>

      {companies.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}
      {companies.data && (
        <div className="overflow-hidden rounded-lg border border-line bg-surface-0">
          <table className="w-full text-sm">
            <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-2.5">Company</th>
                <th className="px-4 py-2.5">TIN</th>
                <th className="px-4 py-2.5">Reg no.</th>
                <th className="px-4 py-2.5">Branches</th>
                <th className="px-4 py-2.5">Status</th>
                <th className="px-4 py-2.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {companies.data.results.map((c) => (
                <tr key={c.id} className="border-b border-line last:border-0 hover:bg-surface-100">
                  <td className="px-4 py-2.5">
                    <span className="flex items-center gap-2 font-medium">
                      <Building2 className="h-4 w-4 text-ink-500" /> {c.name}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-ink-700">{c.tin || "—"}</td>
                  <td className="px-4 py-2.5 text-ink-700">{c.registration_number || "—"}</td>
                  <td className="px-4 py-2.5 text-ink-700">{c.branch_count}</td>
                  <td className="px-4 py-2.5">
                    {c.is_active ? (
                      <span className="text-success">Active</span>
                    ) : (
                      <span className="text-ink-500">Inactive</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex justify-end gap-1">
                      <Button variant="secondary" onClick={() => setViewing(c)}>
                        <Network className="h-3.5 w-3.5" /> Branches
                      </Button>
                      <Button variant="secondary" onClick={() => setEditing(c)}>
                        Edit
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
              {companies.data.results.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-ink-500">
                    No companies yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {adding && <CompanyModal onClose={() => setAdding(false)} />}
      {editing && <CompanyModal company={editing} onClose={() => setEditing(null)} />}
      {viewing && <BranchesModal company={viewing} onClose={() => setViewing(null)} />}
    </div>
  );
}
