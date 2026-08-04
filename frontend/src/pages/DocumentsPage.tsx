import { useQuery } from "@tanstack/react-query";
import { Download, FileText, ShieldCheck } from "lucide-react";
import { PageHeader, Spinner } from "../components/ui";
import { api, downloadFile } from "../lib/api";
import type { DocumentRecord, Paginated } from "../lib/types";

const TYPE_LABEL: Record<string, string> = {
  PURCHASE_ORDER: "Purchase order",
  PACKING_SLIP: "Packing slip",
  DELIVERY_NOTE: "Delivery note",
  GRN: "Goods received",
  TAX_INVOICE: "Tax invoice",
  CREDIT_NOTE: "Credit note",
  RECEIPT: "Receipt",
};

export function DocumentsPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["documents"],
    queryFn: () => api<Paginated<DocumentRecord>>("/api/documents/"),
  });

  return (
    <div>
      <PageHeader title="Document vault" />
      <p className="mb-4 text-sm text-ink-500">
        Every generated document is numbered, hashed, and QR-verifiable. Finalized documents are
        write-once.
      </p>

      {isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}
      {isError && <p className="text-sm text-red-600">Failed to load documents.</p>}

      {data && (
        <div className="overflow-hidden rounded-lg border border-line bg-surface-0">
          <table className="w-full text-sm">
            <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-2.5">Type</th>
                <th className="px-4 py-2.5">Number</th>
                <th className="px-4 py-2.5">Hash (SHA-256)</th>
                <th className="px-4 py-2.5">Generated</th>
                <th className="px-4 py-2.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((d) => (
                <tr key={d.id} className="border-b border-line last:border-0 hover:bg-surface-100">
                  <td className="px-4 py-2.5">
                    <span className="inline-flex items-center gap-1.5 font-medium">
                      <FileText className="h-4 w-4 text-ink-500" />
                      {TYPE_LABEL[d.doc_type] ?? d.doc_type}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 font-mono">{d.doc_number}</td>
                  <td className="px-4 py-2.5">
                    <span className="inline-flex items-center gap-1 font-mono text-xs text-ink-500">
                      <ShieldCheck className="h-3.5 w-3.5 text-green-600" />
                      {d.content_hash.slice(0, 12)}…
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-ink-700">
                    {new Date(d.generated_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <button
                      onClick={() => void downloadFile(d.download_url, `${d.doc_number}.pdf`)}
                      className="inline-flex items-center gap-1.5 rounded-md border border-line px-2.5 py-1.5 text-xs font-semibold text-ink-700 hover:bg-surface-100"
                    >
                      <Download className="h-3.5 w-3.5" /> PDF
                    </button>
                  </td>
                </tr>
              ))}
              {data.results.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-ink-500">
                    No documents yet. They're generated as orders move through the workflow.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
