import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BadgeCheck, CheckCircle2, PauseCircle, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { api, ApiError } from "../lib/api";
import { Button, Modal, SelectField, Spinner, TextField } from "./ui";

// Local types so we don't touch the shared lib/types.ts while another agent edits it.
interface OrgDoc {
  id: number;
  doc_type: string;
  document_number: string;
  expiry_date: string | null;
  is_verified: boolean;
  verified_by_name: string | null;
}
interface Paged<T> {
  results: T[];
}
export interface OnboardingOrg {
  id: number;
  name: string;
  onboarding_status: string;
}

const DOC_TYPES = [
  ["RWANDA_FDA_LICENCE", "Rwanda FDA premises licence"],
  ["NPC_LICENCE", "NPC pharmacist licence"],
  ["RDB_CERTIFICATE", "RDB registration certificate"],
  ["RRA_VAT", "RRA / VAT certificate"],
  ["TAX_CLEARANCE", "Tax clearance"],
  ["OTHER", "Other"],
] as const;
const LABEL = Object.fromEntries(DOC_TYPES) as Record<string, string>;

const STATUS: Record<string, { label: string; cls: string }> = {
  ACTIVE: { label: "Active", cls: "bg-green-50 text-green-700" },
  SUSPENDED: { label: "Suspended", cls: "bg-red-50 text-red-700" },
  DRAFT: { label: "Draft", cls: "bg-surface-100 text-ink-600" },
  PENDING_REVIEW: { label: "Pending review", cls: "bg-amber-50 text-amber-700" },
};

export function OrgOnboardingModal({ org, onClose }: { org: OnboardingOrg; onClose: () => void }) {
  const qc = useQueryClient();
  const key = ["org-documents", org.id];
  const docs = useQuery({
    queryKey: key,
    queryFn: () => api<Paged<OrgDoc>>(`/api/organization-documents/?organization=${org.id}`),
  });
  const [status, setStatus] = useState(org.onboarding_status);
  const [docType, setDocType] = useState("RWANDA_FDA_LICENCE");
  const [number, setNumber] = useState("");
  const [expiry, setExpiry] = useState("");
  const [error, setError] = useState<string | null>(null);
  const refresh = () => qc.invalidateQueries({ queryKey: key });

  const changeStatus = useMutation({
    mutationFn: (action: "activate" | "suspend") =>
      api<OnboardingOrg>(`/api/organizations/${org.id}/${action}/`, { method: "POST" }),
    onSuccess: (o) => {
      setStatus(o.onboarding_status);
      void qc.invalidateQueries({ queryKey: ["organizations"] });
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not change status."),
  });
  const add = useMutation({
    mutationFn: () =>
      api<OrgDoc>("/api/organization-documents/", {
        method: "POST",
        body: JSON.stringify({
          organization: org.id,
          doc_type: docType,
          document_number: number,
          expiry_date: expiry || null,
        }),
      }),
    onSuccess: () => {
      setNumber("");
      setExpiry("");
      void refresh();
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not add the document."),
  });
  const verify = useMutation({
    mutationFn: (id: number) =>
      api<OrgDoc>(`/api/organization-documents/${id}/verify/`, { method: "POST" }),
    onSuccess: () => void refresh(),
  });
  const remove = useMutation({
    mutationFn: (id: number) =>
      api<void>(`/api/organization-documents/${id}/`, { method: "DELETE" }),
    onSuccess: () => void refresh(),
  });

  const s = STATUS[status] ?? STATUS.DRAFT;
  const verifiedCount = (docs.data?.results ?? []).filter((d) => d.is_verified).length;

  return (
    <Modal title={`${org.name} — onboarding`} size="lg" onClose={onClose}>
      <div className="flex flex-col gap-4">
        {/* Activation gate */}
        <div className="flex items-center justify-between rounded-lg border border-line bg-surface-50 p-3">
          <div>
            <div className="text-xs font-medium text-ink-500">Status</div>
            <span
              className={`mt-1 inline-block rounded-md px-2 py-0.5 text-sm font-semibold ${s.cls}`}
            >
              {s.label}
            </span>
            <div className="mt-1 text-xs text-ink-500">
              {verifiedCount} of {docs.data?.results.length ?? 0} documents verified
            </div>
          </div>
          <div className="flex gap-2">
            {status !== "ACTIVE" ? (
              <Button
                onClick={() => changeStatus.mutate("activate")}
                disabled={changeStatus.isPending}
              >
                <CheckCircle2 className="h-4 w-4" /> Activate
              </Button>
            ) : (
              <Button
                variant="secondary"
                onClick={() => changeStatus.mutate("suspend")}
                disabled={changeStatus.isPending}
              >
                <PauseCircle className="h-4 w-4" /> Suspend
              </Button>
            )}
          </div>
        </div>

        {/* Compliance documents */}
        <div className="overflow-hidden rounded-lg border border-line">
          <table className="w-full text-sm">
            <thead className="border-b border-line text-left text-xs text-ink-500">
              <tr>
                <th className="px-3 py-2">Document</th>
                <th className="px-3 py-2">Number</th>
                <th className="px-3 py-2">Expiry</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2 text-right">—</th>
              </tr>
            </thead>
            <tbody>
              {docs.isLoading && (
                <tr>
                  <td colSpan={5} className="py-6 text-center">
                    <Spinner />
                  </td>
                </tr>
              )}
              {(docs.data?.results ?? []).map((d) => (
                <tr key={d.id} className="border-b border-line last:border-0">
                  <td className="px-3 py-2 font-medium">{LABEL[d.doc_type] ?? d.doc_type}</td>
                  <td className="px-3 py-2 text-ink-700">{d.document_number || "—"}</td>
                  <td className="px-3 py-2 text-ink-700">{d.expiry_date || "—"}</td>
                  <td className="px-3 py-2">
                    {d.is_verified ? (
                      <span className="inline-flex items-center gap-1 text-success-700">
                        <BadgeCheck className="h-3.5 w-3.5" /> Verified
                      </span>
                    ) : (
                      <span className="text-warning-700">Pending</span>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex justify-end gap-1">
                      {!d.is_verified && (
                        <Button variant="secondary" onClick={() => verify.mutate(d.id)}>
                          Verify
                        </Button>
                      )}
                      <button
                        onClick={() => remove.mutate(d.id)}
                        className="rounded-md p-1.5 text-ink-500 hover:bg-red-50 hover:text-red-600"
                        aria-label="Delete document"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {docs.data?.results.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-3 py-5 text-center text-ink-500">
                    No compliance documents yet — add the licences and certificates below.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Add document */}
        <div className="rounded-lg border border-line bg-surface-50 p-3">
          <div className="mb-2 text-xs font-semibold text-ink-500">
            Add a document
          </div>
          <div className="grid grid-cols-2 gap-3">
            <SelectField label="Type" value={docType} onChange={(e) => setDocType(e.target.value)}>
              {DOC_TYPES.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </SelectField>
            <TextField
              label="Document number"
              value={number}
              onChange={(e) => setNumber(e.target.value)}
            />
            <TextField
              label="Expiry (optional)"
              type="date"
              value={expiry}
              onChange={(e) => setExpiry(e.target.value)}
            />
            <div className="flex items-end">
              <Button onClick={() => add.mutate()} disabled={add.isPending}>
                <Plus className="h-4 w-4" /> Add
              </Button>
            </div>
          </div>
          {error && <p className="mt-2 text-sm text-danger-700">{error}</p>}
        </div>
      </div>
    </Modal>
  );
}
