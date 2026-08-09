/* -------------------------------------------------------------------------- */
/* Looking at a document without leaving the screen you found it on.           */
/*                                                                            */
/* Documents are stored as site-relative paths (`/media/documents/…`) so that  */
/* moving the deployment does not strand every stored file at the old domain.  */
/* Putting one of those straight into an `href` sends the browser to this      */
/* app's own origin, where the router finds no matching route and falls back   */
/* to the home page — which is what "the document link takes me home" was.     */
/*                                                                            */
/* Fetching it rather than linking to it fixes that and buys two other things: */
/* the request carries the access token, so a document is never readable       */
/* purely by knowing its URL; and the bytes are already in hand, so they can   */
/* be shown inline instead of landing in a downloads folder.                   */
/* -------------------------------------------------------------------------- */

import { useEffect, useState } from "react";
import { AlertTriangle, Download, ExternalLink, Loader2 } from "lucide-react";
import { Button, Modal } from "./ui";
import { ApiError, getToken } from "../lib/api";

const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface PreviewableDocument {
  doc_number: string;
  download_url: string;
  generated_at?: string;
}

/**
 * Fetch a stored document with the caller's credentials.
 *
 * Returns an object URL, which the caller must revoke — a blob held after the
 * viewer closes keeps the whole file in memory for the life of the tab.
 */
async function fetchDocument(path: string): Promise<{ url: string; type: string }> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const absolute = /^https?:/i.test(path) ? path : `${BASE}${path.startsWith("/") ? "" : "/"}${path}`;
  const response = await fetch(absolute, { headers });
  if (!response.ok) {
    throw new ApiError(
      response.status,
      response.status === 404
        ? "That document is no longer where it was stored."
        : "That document could not be opened.",
    );
  }
  const blob = await response.blob();
  return { url: URL.createObjectURL(blob), type: blob.type };
}

export function DocumentPreview({
  document: record,
  onClose,
}: {
  document: PreviewableDocument;
  onClose: () => void;
}) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [kind, setKind] = useState("");

  useEffect(() => {
    let revoked = false;
    let created: string | null = null;

    fetchDocument(record.download_url)
      .then(({ url, type }) => {
        // The viewer may already have closed while the fetch was in flight;
        // creating an object URL for a dead component leaks it.
        if (revoked) {
          URL.revokeObjectURL(url);
          return;
        }
        created = url;
        setBlobUrl(url);
        setKind(type);
      })
      .catch((e: unknown) =>
        setError(e instanceof ApiError ? e.message : "That document could not be opened."),
      );

    return () => {
      revoked = true;
      if (created) URL.revokeObjectURL(created);
    };
  }, [record.download_url]);

  const save = () => {
    if (!blobUrl) return;
    const link = window.document.createElement("a");
    link.href = blobUrl;
    link.download = `${record.doc_number}.pdf`;
    window.document.body.appendChild(link);
    link.click();
    link.remove();
  };

  return (
    <Modal title={record.doc_number} onClose={onClose} size="xl">
      <div className="space-y-3">
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs text-ink-500">
            {record.generated_at
              ? `Generated ${new Date(record.generated_at).toLocaleString()}`
              : "Stored document"}
          </p>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={save} disabled={!blobUrl}>
              <Download className="h-4 w-4" /> Save
            </Button>
            {blobUrl && (
              <a
                href={blobUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 rounded-md border border-line bg-surface-0 px-2.5 py-1.5 text-sm font-medium text-ink-700 hover:bg-surface-1"
              >
                <ExternalLink className="h-4 w-4" /> Open in a tab
              </a>
            )}
          </div>
        </div>

        <div className="h-[70vh] overflow-hidden rounded-lg border border-line bg-surface-1">
          {error ? (
            <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
              <AlertTriangle className="h-6 w-6 text-danger-600" aria-hidden />
              <p className="text-sm text-danger-700">{error}</p>
            </div>
          ) : !blobUrl ? (
            <div className="flex h-full items-center justify-center gap-2 text-sm text-ink-500">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
              Fetching the document…
            </div>
          ) : kind.startsWith("image/") ? (
            <img src={blobUrl} alt={record.doc_number} className="h-full w-full object-contain" />
          ) : (
            /* A blob URL in an iframe uses the browser's own PDF viewer, so
               there is no library to ship and nothing leaves this origin. */
            <iframe src={blobUrl} title={record.doc_number} className="h-full w-full" />
          )}
        </div>
      </div>
    </Modal>
  );
}

/** A link that opens the preview instead of navigating away. */
export function DocumentLink({
  document: record,
  onOpen,
}: {
  document: PreviewableDocument;
  onOpen: () => void;
}) {
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        onOpen();
      }}
      className="inline-flex items-center gap-1 text-xs text-brand-600 hover:underline"
    >
      {record.doc_number}
    </button>
  );
}
