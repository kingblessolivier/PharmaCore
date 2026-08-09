/* -------------------------------------------------------------------------- */
/* Changing your own password.                                                 */
/*                                                                            */
/* POST /api/auth/change-password has existed the whole time with nothing      */
/* calling it. An administrator could reset somebody else's password, but no   */
/* one could change their own — so the only way out of a password a colleague  */
/* had seen was to ask an admin to reset it, which means telling them the      */
/* problem and getting a second password somebody else has also seen.          */
/* -------------------------------------------------------------------------- */

import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { KeyRound } from "lucide-react";
import { Button, Modal, TextField } from "./ui";
import { api, ApiError } from "../lib/api";

export function ChangePasswordModal({ onClose }: { onClose: () => void }) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [again, setAgain] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const save = useMutation({
    mutationFn: () =>
      api<{ detail?: string }>("/api/auth/change-password", {
        method: "POST",
        body: JSON.stringify({ old_password: current, new_password: next }),
      }),
    onSuccess: () => setDone(true),
    onError: (e) =>
      setError(e instanceof ApiError ? e.message : "Could not change the password. Try again."),
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    // Checked here as well as on the server: retyping is for catching a typo,
    // and a round trip to be told you mistyped is a poor way to find out.
    if (next !== again) {
      setError("The two new passwords do not match.");
      return;
    }
    if (next.length < 8) {
      setError("Use at least 8 characters.");
      return;
    }
    if (next === current) {
      setError("The new password has to be different from the old one.");
      return;
    }
    save.mutate();
  };

  return (
    <Modal title="Change your password" onClose={onClose}>
      {done ? (
        <div className="space-y-3">
          <p className="text-sm text-success-700">
            Your password has been changed. It applies the next time you sign in.
          </p>
          <div className="flex justify-end">
            <Button onClick={onClose}>Close</Button>
          </div>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-3">
          <TextField
            label="Current password"
            type="password"
            autoComplete="current-password"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
          />
          <TextField
            label="New password"
            type="password"
            autoComplete="new-password"
            value={next}
            onChange={(e) => setNext(e.target.value)}
          />
          <TextField
            label="New password again"
            type="password"
            autoComplete="new-password"
            value={again}
            onChange={(e) => setAgain(e.target.value)}
          />
          {error && <p className="text-sm text-danger-700">{error}</p>}
          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={save.isPending || !current || !next}>
              <KeyRound className="h-4 w-4" />
              {save.isPending ? "Changing…" : "Change password"}
            </Button>
          </div>
        </form>
      )}
    </Modal>
  );
}
