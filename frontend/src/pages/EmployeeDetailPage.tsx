import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, FileText, Plus, ShieldAlert } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Button, Modal, PageHeader, SelectField, Spinner, TextField } from "../components/ui";
import { api, ApiError } from "../lib/api";
import type { Employee, EmployeeDocument } from "../lib/types";

const DOC_TYPES: { value: string; label: string }[] = [
  { value: "NATIONAL_ID", label: "National ID / passport" },
  { value: "PROFESSIONAL_LICENSE", label: "Professional licence" },
  { value: "ACADEMIC_CERTIFICATE", label: "Academic certificate" },
  { value: "EMPLOYMENT_CONTRACT", label: "Signed employment contract" },
  { value: "POLICE_CLEARANCE", label: "Police clearance" },
  { value: "MEDICAL_FITNESS", label: "Medical fitness certificate" },
  { value: "BANK_PROOF", label: "Bank / MoMo proof" },
  { value: "OTHER", label: "Other" },
];

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[11px] font-medium uppercase tracking-wide text-ink-500">{label}</div>
      <div className="text-sm text-ink-900">{value || "—"}</div>
    </div>
  );
}

function AddDocumentModal({ onClose, employeeId }: { onClose: () => void; employeeId: number }) {
  const qc = useQueryClient();
  const [docType, setDocType] = useState("NATIONAL_ID");
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () =>
      api<EmployeeDocument>(`/api/hr/employees/${employeeId}/documents/`, {
        method: "POST",
        body: JSON.stringify({ doc_type: docType, document_url: url }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["employee", employeeId] });
      onClose();
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not attach this document."),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    create.mutate();
  }

  return (
    <Modal title="Attach a document" onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <SelectField label="Document type" value={docType} onChange={(e) => setDocType(e.target.value)}>
          {DOC_TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </SelectField>
        <TextField label="Document URL" value={url} onChange={(e) => setUrl(e.target.value)} required />
        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? "Saving…" : "Attach"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function TerminateModal({ onClose, employeeId }: { onClose: () => void; employeeId: number }) {
  const qc = useQueryClient();
  const [reason, setReason] = useState("");
  const [effectiveDate, setEffectiveDate] = useState(new Date().toISOString().slice(0, 10));
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const submitRequest = useMutation({
    mutationFn: () =>
      api<{ approval_request: number }>(`/api/hr/employees/${employeeId}/request-termination/`, {
        method: "POST",
        body: JSON.stringify({ reason, effective_date: effectiveDate }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["employee", employeeId] });
      setDone(true);
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not submit this request."),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    submitRequest.mutate();
  }

  return (
    <Modal title="Request termination" onClose={onClose}>
      {done ? (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-ink-700">
            Submitted for approval — the employee stays active until a senior approver decides this
            in the <strong>Approvals inbox</strong> (no self-approval; you cannot decide your own request).
          </p>
          <div className="flex justify-end">
            <Button onClick={onClose}>Done</Button>
          </div>
        </div>
      ) : (
        <form onSubmit={submit} className="flex flex-col gap-4">
          <TextField label="Effective date" type="date" value={effectiveDate} onChange={(e) => setEffectiveDate(e.target.value)} />
          <TextField label="Reason" value={reason} onChange={(e) => setReason(e.target.value)} required autoFocus />
          {error && <p className="text-sm text-danger">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <button
              type="submit"
              disabled={submitRequest.isPending}
              className="inline-flex items-center gap-2 rounded-md bg-red-600 px-3 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-40"
            >
              {submitRequest.isPending ? "Submitting…" : "Submit for approval"}
            </button>
          </div>
        </form>
      )}
    </Modal>
  );
}

export function EmployeeDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [addingDoc, setAddingDoc] = useState(false);
  const [terminating, setTerminating] = useState(false);

  const empQ = useQuery({
    queryKey: ["employee", Number(id)],
    queryFn: () => api<Employee>(`/api/hr/employees/${id}/`),
  });

  if (empQ.isLoading || !empQ.data) {
    return (
      <div className="flex justify-center py-10">
        <Spinner />
      </div>
    );
  }

  const emp = empQ.data;
  const terminated = emp.employment_status === "TERMINATED";

  return (
    <div>
      <button
        onClick={() => navigate("/people/employees")}
        className="mb-3 inline-flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-3.5 w-3.5" /> Back to employees
      </button>
      <PageHeader
        title={emp.full_name}
        action={
          !terminated && (
            <button
              onClick={() => setTerminating(true)}
              className="inline-flex items-center gap-2 rounded-md border border-red-200 px-3 py-2 text-sm font-semibold text-red-700 hover:bg-red-50"
            >
              <ShieldAlert className="h-4 w-4" /> Request termination
            </button>
          )
        }
      />
      <p className="mb-5 text-sm text-ink-500">
        {emp.employee_number} · {emp.job_title || "No title"} · {emp.organization_name}
      </p>

      <div className="mb-6 grid grid-cols-2 gap-4 rounded-lg border border-line bg-surface-0 p-5 sm:grid-cols-3">
        <Field label="Status" value={emp.employment_status} />
        <Field label="Employment type" value={emp.employment_type} />
        <Field label="Hire date" value={emp.hire_date} />
        <Field label="End date" value={emp.end_date ?? ""} />
        <Field label="National ID" value={emp.national_id} />
        <Field label="Department" value={emp.department_name ?? ""} />
        <Field label="Bank account" value={emp.bank_account} />
        <Field label="MoMo number" value={emp.momo_number} />
        <Field label="RSSB number" value={emp.rssb_number} />
        <Field label="Professional licence" value={emp.license_number ?? ""} />
        <Field label="Linked login" value={emp.user_username ?? "Not provisioned"} />
        <Field label="Next of kin" value={emp.next_of_kin_name ? `${emp.next_of_kin_name} (${emp.next_of_kin_relation})` : ""} />
      </div>

      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-ink-900">Documents</h2>
        <Button variant="secondary" onClick={() => setAddingDoc(true)}>
          <Plus className="h-4 w-4" /> Attach document
        </Button>
      </div>
      <div className="overflow-hidden rounded-lg border border-line bg-surface-0">
        <table className="w-full text-sm">
          <tbody>
            {emp.documents.map((d) => (
              <tr key={d.id} className="border-b border-line last:border-0">
                <td className="flex items-center gap-2 px-4 py-2.5">
                  <FileText className="h-4 w-4 text-ink-500" />
                  {d.doc_type.replace(/_/g, " ")}
                </td>
                <td className="px-4 py-2.5 text-right">
                  <a href={d.document_url} target="_blank" rel="noreferrer" className="text-brand-700 hover:underline">
                    View
                  </a>
                </td>
              </tr>
            ))}
            {emp.documents.length === 0 && (
              <tr>
                <td className="px-4 py-8 text-center text-ink-500">No documents attached yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {addingDoc && <AddDocumentModal onClose={() => setAddingDoc(false)} employeeId={emp.id} />}
      {terminating && <TerminateModal onClose={() => setTerminating(false)} employeeId={emp.id} />}
    </div>
  );
}
