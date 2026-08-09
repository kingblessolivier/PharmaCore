/* -------------------------------------------------------------------------- */
/* A lot's paperwork.                                                          */
/*                                                                            */
/* BatchDocument shipped in #106 with an API, constraints and nine tests, and  */
/* no screen — so a Certificate of Analysis could be required, modelled and    */
/* reported on, and still had nowhere to be uploaded. That is the same trap    */
/* the whole units problem came out of, and it was mine.                       */
/* -------------------------------------------------------------------------- */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { BadgeCheck, FileText, Plus, ShieldQuestion, Trash2 } from "lucide-react";
import { Button, SelectField, TextField } from "./ui";
import { api } from "../lib/api";
import type { Paginated } from "../lib/types";

export interface BatchDocument {
  id: number;
  batch: number;
  batch_number: string;
  doc_type: string;
  doc_type_display: string;
  document_number: string;
  document_url: string;
  issued_on: string | null;
  issued_by: string;
  is_verified: boolean;
  verified_at: string | null;
  notes: string;
  created_at: string;
}

/** The kinds a regulator asks for at an inspection. */
const DOC_TYPES = [
  { value: "COA", label: "Certificate of Analysis" },
  { value: "GMP", label: "Manufacturer GMP certificate" },
  { value: "IMPORT_PERMIT", label: "Import permit / authorisation" },
  { value: "BILL_OF_LADING", label: "Bill of lading" },
  { value: "CUSTOMS", label: "Customs declaration" },
  { value: "COLD_CHAIN_LOG", label: "Cold-chain shipping log" },
  { value: "DESTRUCTION", label: "Proof of destruction" },
  { value: "RECALL_NOTICE", label: "Recall notice" },
  { value: "OTHER", label: "Other" },
];

export function BatchPaperwork({ batchId }: { batchId: number }) {
  const qc = useQueryClient();
  const [adding, setAdding] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["batch-documents", batchId],
    queryFn: () =>
      api<Paginated<BatchDocument>>(`/api/inventory/batch-documents/?batch=${batchId}`),
  });
  const rows = data?.results ?? [];
  const invalidate = () => void qc.invalidateQueries({ queryKey: ["batch-documents", batchId] });

  const verify = useMutation({
    mutationFn: (id: number) =>
      api<BatchDocument>(`/api/inventory/batch-documents/${id}/verify/`, { method: "POST" }),
    onSuccess: invalidate,
  });
  const remove = useMutation({
    mutationFn: (id: number) =>
      api<void>(`/api/inventory/batch-documents/${id}/`, { method: "DELETE" }),
    onSuccess: invalidate,
  });

  const hasVerifiedCoA = rows.some((d) => d.doc_type === "COA" && d.is_verified);

  return (
    <div className="rounded-lg border border-line bg-surface-0">
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <div>
          <div className="text-sm font-semibold text-ink-900">Paperwork for this lot</div>
          <div className="text-xs text-ink-500">
            A Certificate of Analysis is issued for a specific batch — a manufacturer&apos;s GMP
            certificate does not answer for it.
          </div>
        </div>
        <Button variant="secondary" onClick={() => setAdding(true)}>
          <Plus className="h-4 w-4" /> Attach
        </Button>
      </div>

      {!hasVerifiedCoA && !isLoading && (
        <div className="border-b border-line bg-warning-50 px-4 py-2 text-xs text-warning-900">
          No verified Certificate of Analysis on file for this lot.
        </div>
      )}

      <ul className="divide-y divide-line">
        {rows.map((doc) => (
          <li key={doc.id} className="flex items-center gap-3 px-4 py-2.5">
            <FileText className="h-4 w-4 shrink-0 text-ink-400" aria-hidden />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm text-ink-900">{doc.doc_type_display}</span>
                {doc.is_verified ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-success-50 px-2 py-0.5 text-[11px] font-semibold text-success-700">
                    <BadgeCheck className="h-3 w-3" aria-hidden /> Verified
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 rounded-full bg-warning-50 px-2 py-0.5 text-[11px] font-semibold text-warning-800">
                    <ShieldQuestion className="h-3 w-3" aria-hidden /> Not checked
                  </span>
                )}
              </div>
              <div className="text-xs text-ink-500">
                {doc.document_number || "no reference"}
                {doc.issued_by && ` · ${doc.issued_by}`}
                {doc.issued_on && ` · ${doc.issued_on}`}
              </div>
            </div>
            {doc.document_url && (
              <a
                href={doc.document_url}
                target="_blank"
                rel="noreferrer"
                className="shrink-0 text-xs text-brand-600 hover:underline"
              >
                Open
              </a>
            )}
            {/* Verification is its own act: attaching a file is not the same as
                somebody checking it is the right file for this lot. */}
            {!doc.is_verified && (
              <button
                onClick={() => verify.mutate(doc.id)}
                disabled={verify.isPending}
                className="shrink-0 rounded-md border border-line px-2 py-1 text-xs text-ink-700 hover:bg-surface-100"
              >
                Verify
              </button>
            )}
            <button
              onClick={() => remove.mutate(doc.id)}
              aria-label={`Remove ${doc.doc_type_display}`}
              className="shrink-0 text-ink-400 hover:text-danger-600"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </li>
        ))}
        {rows.length === 0 && !isLoading && (
          <li className="px-4 py-6 text-center text-sm text-ink-500">Nothing on file yet.</li>
        )}
      </ul>

      {adding && (
        <AttachDocument
          batchId={batchId}
          onClose={() => setAdding(false)}
          onSaved={() => {
            invalidate();
            setAdding(false);
          }}
        />
      )}
    </div>
  );
}

function AttachDocument({
  batchId,
  onClose,
  onSaved,
}: {
  batchId: number;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [docType, setDocType] = useState("COA");
  const [number, setNumber] = useState("");
  const [url, setUrl] = useState("");
  const [issuedBy, setIssuedBy] = useState("");
  const [issuedOn, setIssuedOn] = useState("");
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () =>
      api<BatchDocument>("/api/inventory/batch-documents/", {
        method: "POST",
        body: JSON.stringify({
          batch: batchId,
          doc_type: docType,
          document_number: number,
          document_url: url,
          issued_by: issuedBy,
          issued_on: issuedOn || null,
        }),
      }),
    onSuccess: onSaved,
    onError: (e) =>
      setError(e instanceof Error ? e.message : "Could not attach that document to this lot."),
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    save.mutate();
  };

  return (
    <form onSubmit={submit} className="space-y-3 border-t border-line bg-surface-50 px-4 py-3">
      <SelectField label="Kind" value={docType} onChange={(e) => setDocType(e.target.value)}>
        {DOC_TYPES.map((d) => (
          <option key={d.value} value={d.value}>
            {d.label}
          </option>
        ))}
      </SelectField>
      <TextField
        label="Reference"
        value={number}
        onChange={(e) => setNumber(e.target.value)}
        placeholder="COA-2026-118"
      />
      <TextField
        label="Link to the document"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder="https://…"
      />
      <TextField
        label="Issued by"
        value={issuedBy}
        onChange={(e) => setIssuedBy(e.target.value)}
        placeholder="Cipla QA"
      />
      <TextField
        label="Issued on"
        type="date"
        value={issuedOn}
        onChange={(e) => setIssuedOn(e.target.value)}
      />
      {error && <p className="text-sm text-danger-700">{error}</p>}
      <p className="text-[11px] text-ink-500">
        Attaching does not verify it. Somebody still has to confirm it is the right document for
        this lot.
      </p>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="secondary" onClick={onClose}>
          Cancel
        </Button>
        <Button type="submit" disabled={save.isPending}>
          Attach
        </Button>
      </div>
    </form>
  );
}
