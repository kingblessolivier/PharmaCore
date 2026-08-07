/** Generating and opening finance documents.
 *
 * Every finance document is the record for the thing it describes, so the API
 * returns the same numbered PDF when asked twice rather than issuing a second
 * original. That means a "Statement" button can be pressed freely — it is a
 * fetch, not a mint.
 */

import { useMutation } from "@tanstack/react-query";
import { api } from "./api";

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

/** Generate (or fetch) a document, then open it in a new tab. */
export function useFinanceDocument(kind: FinanceDocumentKind) {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api<GeneratedDocument>(`/api/finance/documents/${kind}/`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: (doc) => {
      // A popup blocker will stop this; the number and link are still returned
      // so the caller can surface them rather than failing silently.
      window.open(doc.download_url, "_blank", "noopener");
    },
  });
}
