import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Modal, PageHeader, SelectField, Spinner, TextField } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { isAdmin } from "../lib/roles";
import type { Employee, EmploymentType, Organization, Paginated } from "../lib/types";

const STATUS_TONE: Record<string, string> = {
  PROBATION: "text-amber-700 bg-amber-50",
  ACTIVE: "text-green-700 bg-green-50",
  SUSPENDED: "text-red-700 bg-red-50",
  TERMINATED: "text-ink-500 bg-surface-100",
};

function NewEmployeeModal({ onClose, orgId }: { onClose: () => void; orgId: number }) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [employmentType, setEmploymentType] = useState<EmploymentType>("FULL_TIME");
  const [hireDate, setHireDate] = useState(new Date().toISOString().slice(0, 10));
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () =>
      api<Employee>("/api/hr/employees/", {
        method: "POST",
        body: JSON.stringify({
          organization: orgId,
          first_name: firstName,
          last_name: lastName,
          job_title: jobTitle,
          employment_type: employmentType,
          hire_date: hireDate,
        }),
      }),
    onSuccess: (employee) => {
      void qc.invalidateQueries({ queryKey: ["employees"] });
      navigate(`/people/employees/${employee.id}`);
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not create this employee."),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    create.mutate();
  }

  return (
    <Modal title="New employee" onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-3">
          <TextField label="First name" value={firstName} onChange={(e) => setFirstName(e.target.value)} required autoFocus />
          <TextField label="Last name" value={lastName} onChange={(e) => setLastName(e.target.value)} required />
        </div>
        <TextField label="Job title" value={jobTitle} onChange={(e) => setJobTitle(e.target.value)} />
        <div className="grid grid-cols-2 gap-3">
          <SelectField
            label="Employment type"
            value={employmentType}
            onChange={(e) => setEmploymentType(e.target.value as EmploymentType)}
          >
            <option value="FULL_TIME">Full time</option>
            <option value="PART_TIME">Part time</option>
            <option value="CONTRACT">Contract</option>
          </SelectField>
          <TextField label="Hire date" type="date" value={hireDate} onChange={(e) => setHireDate(e.target.value)} required />
        </div>
        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? "Saving…" : "Create"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export function EmployeesPage() {
  const { user } = useAuth();
  const admin = isAdmin(user);
  const [adding, setAdding] = useState(false);
  const [orgFilter, setOrgFilter] = useState<number | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const navigate = useNavigate();

  const orgsQ = useQuery({
    queryKey: ["organizations"],
    queryFn: () => api<Paginated<Organization>>("/api/organizations/"),
    enabled: admin,
  });
  const params = new URLSearchParams();
  if (orgFilter) params.set("organization", String(orgFilter));
  if (statusFilter) params.set("status", statusFilter);
  const employeesQ = useQuery({
    queryKey: ["employees", orgFilter, statusFilter],
    queryFn: () => api<Paginated<Employee>>(`/api/hr/employees/?${params.toString()}`),
  });

  const orgId = orgFilter ?? user?.organization ?? 0;

  return (
    <div>
      <PageHeader
        title="Employees"
        action={
          orgId > 0 && (
            <Button onClick={() => setAdding(true)}>
              <Plus className="h-4 w-4" /> New employee
            </Button>
          )
        }
      />

      <div className="mb-4 flex flex-wrap gap-3">
        {admin && orgsQ.data && (
          <div className="w-56">
            <SelectField
              value={orgFilter ?? ""}
              onChange={(e) => setOrgFilter(e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">All visible organizations</option>
              {orgsQ.data.results.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name}
                </option>
              ))}
            </SelectField>
          </div>
        )}
        <div className="w-48">
          <SelectField value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">All statuses</option>
            <option value="PROBATION">Probation</option>
            <option value="ACTIVE">Active</option>
            <option value="SUSPENDED">Suspended</option>
            <option value="TERMINATED">Terminated</option>
          </SelectField>
        </div>
      </div>

      {employeesQ.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {employeesQ.data && (
        <div className="overflow-hidden rounded-lg border border-line bg-surface-0">
          <table className="w-full text-sm">
            <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-2.5">Employee #</th>
                <th className="px-4 py-2.5">Name</th>
                <th className="px-4 py-2.5">Job title</th>
                <th className="px-4 py-2.5">Organization</th>
                <th className="px-4 py-2.5">Status</th>
              </tr>
            </thead>
            <tbody>
              {employeesQ.data.results.map((emp) => (
                <tr
                  key={emp.id}
                  onClick={() => navigate(`/people/employees/${emp.id}`)}
                  className="cursor-pointer border-b border-line last:border-0 hover:bg-surface-100"
                >
                  <td className="px-4 py-2.5 font-mono">{emp.employee_number}</td>
                  <td className="px-4 py-2.5 font-medium">{emp.full_name}</td>
                  <td className="px-4 py-2.5 text-ink-700">{emp.job_title || "—"}</td>
                  <td className="px-4 py-2.5 text-ink-700">{emp.organization_name}</td>
                  <td className="px-4 py-2.5">
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${STATUS_TONE[emp.employment_status]}`}
                    >
                      {emp.employment_status}
                    </span>
                  </td>
                </tr>
              ))}
              {employeesQ.data.results.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-ink-500">
                    No employees yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {adding && <NewEmployeeModal onClose={() => setAdding(false)} orgId={orgId} />}
    </div>
  );
}
