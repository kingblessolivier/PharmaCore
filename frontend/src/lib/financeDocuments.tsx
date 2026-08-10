/** Generating and opening finance documents.
 *
 * Every finance document is the record for the thing it describes, so the API
 * returns the same numbered PDF when asked twice rather than issuing a second
 * original. That means a "Statement" button can be pressed freely — it is a
 * fetch, not a mint.
 *
 * Opening one used to be `window.open(doc.download_url)` in the mutation's
 * `onSuccess`, which fails twice over:
 *
 *   1. `onSuccess` runs after the network round-trip, so the call is no longer
 *      inside the click that started it. Every browser's popup blocker stops a
 *      window opened outside a user gesture. Nothing opened and nothing said
 *      why — which is exactly what "the journal voucher is not working" was.
 *   2. `download_url` is the site-relative API path `/api/documents/<id>/
 *      download/`. Handed to `window.open` it resolves against *this* app's
 *      origin, where the dev server returns index.html and the router falls
 *      back to the home page; in production it is a 401, because a bare browser
 *      navigation carries no bearer token.
 *
 * So the document is fetched with credentials and shown in place. Same fix
 * DocumentPreview already carried for stored documents — the finance buttons
 * simply never went through it.
 */

import { useMutation } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { useState } from "react";
import { api } from "./api";
import { DocumentPreview } from "../components/DocumentPreview";

export interface GeneratedDocument {
  id: number;
  doc_type: string;
  doc_number: string;
  reference_type: string;
  reference_id: string;
  content_hash: string;
  qr_token: string;
  generated_at: string;
  download_url: string;
}

export type FinanceDocumentKind =
  | "invoice"
  | "receipt"
  | "credit-note"
  | "statement"
  | "remittance-advice"
  | "payment-voucher"
  | "journal-voucher"
  | "financial-statements"
  | "vat-return";

export const DOCUMENT_LABEL: Record<FinanceDocumentKind, string> = {
  invoice: "Tax invoice",
  receipt: "Receipt",
  "credit-note": "Credit note",
  statement: "Statement of account",
  "remittance-advice": "Remittance advice",
  "payment-voucher": "Payment voucher",
  "journal-voucher": "Journal voucher",
  "financial-statements": "Financial statements",
  "vat-return": "VAT return",
};

/**
 * Generate (or fetch) a finance document and show it.
 *
 * Render `viewer` somewhere in the calling screen — it is the preview modal, or
 * null when there is nothing to show. `error` is the reason generation was
 * refused, which must be displayed: a button that goes quiet on failure is the
 * bug this hook was written to end.
 */
export function useFinanceDocument(kind: FinanceDocumentKind) {
  const [showing, setShowing] = useState<GeneratedDocument | null>(null);

  const mutation = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api<GeneratedDocument>(`/api/finance/documents/${kind}/`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: (doc) => setShowing(doc),
  });

  const viewer = showing ? (
    <DocumentPreview document={showing} onClose={() => setShowing(null)} />
  ) : null;

  return {
    ...mutation,
    viewer,
    /** Reopen the document already generated, without asking for it again. */
    show: () => mutation.data && setShowing(mutation.data),
    error: mutation.error
      ? mutation.error.message || `The ${DOCUMENT_LABEL[kind].toLowerCase()} could not be produced.`
      : null,
  };
}

/**
 * What happened when the button was pressed — the refusal, or the number issued.
 *
 * Both matter. A refusal must be read, and the number is what somebody quotes
 * later; the document itself has already opened, so this is the line that
 * remains on the screen behind it.
 */
export function DocumentNotice({ doc }: { doc: ReturnType<typeof useFinanceDocument> }) {
  if (doc.error) {
    return (
      <p className="flex items-start gap-1.5 text-xs text-danger-700">
        <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
        {doc.error}
      </p>
    );
  }
  if (!doc.data) return null;
  return (
    <p className="text-xs text-ink-500">
      Issued as <strong className="text-ink-800">{doc.data.doc_number}</strong> — numbered, hashed
      and QR-verifiable.{" "}
      <button type="button" onClick={doc.show} className="text-brand-600 hover:underline">
        View again
      </button>
    </p>
  );
}
