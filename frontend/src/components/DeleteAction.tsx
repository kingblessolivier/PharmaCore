/* -------------------------------------------------------------------------- */
/* Deleting a record, and being told when you may not.                         */
/*                                                                            */
/* The API answers a refused deletion with 409 and a sentence explaining what  */
/* to do instead — "post a reversing entry", "cancel the order", "deactivate   */
/* it". That sentence is the whole point of the refusal, so a button that      */
/* swallows it is worse than no button: the record stays, nothing is said, and */
/* the reader concludes the system is broken.                                  */
/*                                                                            */
/* So this component always renders the outcome. It also hides itself from     */
/* anyone who is not an administrator, because offering an action that will be */
/* refused is its own small lie.                                              */
/* -------------------------------------------------------------------------- */

import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, Loader2, Trash2 } from "lucide-react";
import { useState } from "react";
import { ApiError, api } from "../lib/api";
import { useMayDelete } from "../lib/mayDelete";
import { Button, Modal } from "./ui";

export function DeleteAction({
  endpoint,
  name,
  what = "record",
  onDeleted,
  label,
}: {
  /** Full detail path, e.g. `/api/distribution/orders/12/`. */
  endpoint: string;
  /** What the reader calls this thing — an order number, a person's name. */
  name: string;
  /** The kind of thing, for the confirmation sentence. */
  what?: string;
  onDeleted?: () => void;
  /** Set to render a labelled button rather than a bare icon. */
  label?: string;
}) {
  const mayDelete = useMayDelete();
  const [asking, setAsking] = useState(false);
  const [refusal, setRefusal] = useState<string | null>(null);

  const remove = useMutation({
    mutationFn: () => api<void>(endpoint, { method: "DELETE" }),
    onSuccess: () => {
      setAsking(false);
      onDeleted?.();
    },
    onError: (error: unknown) => {
      // A 409 carries the reason. Anything else still gets a sentence rather
      // than a silent no-op.
      setRefusal(
        error instanceof ApiError
          ? error.message
          : `${name} could not be deleted, and the server did not say why.`,
      );
    },
  });

  if (!mayDelete) return null;

  return (
    <>
      {label ? (
        <Button
          variant="secondary"
          onClick={(e) => {
            e.stopPropagation();
            setRefusal(null);
            setAsking(true);
          }}
        >
          <Trash2 className="h-4 w-4" /> {label}
        </Button>
      ) : (
        <button
          type="button"
          aria-label={`Delete ${name}`}
          onClick={(e) => {
            e.stopPropagation();
            setRefusal(null);
            setAsking(true);
          }}
          className="rounded-md p-1.5 text-ink-500 hover:bg-danger-50 hover:text-danger-600"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      )}

      {asking && (
        <Modal title={`Delete ${what}`} onClose={() => setAsking(false)}>
          <div className="space-y-4">
            <p className="text-sm text-ink-700">
              Delete <strong className="text-ink-900">{name}</strong>? This cannot be undone. The
              deletion is recorded against your name in the audit log.
            </p>

            {refusal && (
              <div className="flex items-start gap-2 rounded-lg border border-danger-200 bg-danger-50 px-3 py-2.5">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-danger-600" aria-hidden />
                <p className="text-sm text-danger-800">{refusal}</p>
              </div>
            )}

            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setAsking(false)}>
                {refusal ? "Close" : "Cancel"}
              </Button>
              {!refusal && (
                <Button
                  variant="danger"
                  onClick={() => remove.mutate()}
                  disabled={remove.isPending}
                >
                  {remove.isPending ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" /> Deleting…
                    </>
                  ) : (
                    <>
                      <Trash2 className="h-4 w-4" /> Delete
                    </>
                  )}
                </Button>
              )}
            </div>
          </div>
        </Modal>
      )}
    </>
  );
}
