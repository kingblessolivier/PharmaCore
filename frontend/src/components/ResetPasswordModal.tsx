import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { api, ApiError } from "../lib/api";
import { Button, Modal, TextField } from "./ui";

export function ResetPasswordModal({
  userId,
  username,
  onClose,
}: {
  userId: number;
  username: string;
  onClose: () => void;
}) {
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const reset = useMutation({
    mutationFn: () =>
      api<{ detail: string }>(`/api/users/${userId}/set-password/`, {
        method: "POST",
        body: JSON.stringify({ password }),
      }),
    onSuccess: () => setDone(true),
    onError: (e) =>
      setError(e instanceof ApiError ? e.message : "Could not reset the password."),
  });

  function submit() {
    setError(null);
    if (password !== confirm) {
      setError("The two passwords don't match.");
      return;
    }
    reset.mutate();
  }

  return (
    <Modal title={`Reset password — ${username}`} onClose={onClose}>
      {done ? (
        <div className="flex flex-col gap-4">
          <p className="text-sm text-ink-700">
            Password reset. <strong>{username}</strong> must set a new password the next time they
            sign in.
          </p>
          <div className="flex justify-end">
            <Button onClick={onClose}>Done</Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          <p className="text-sm text-ink-500">
            Set a temporary password. The user will be required to change it on next sign-in.
          </p>
          <TextField
            label="New password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoFocus
          />
          <TextField
            label="Confirm password"
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
          />
          {error && <p className="text-sm text-danger">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button onClick={submit} disabled={reset.isPending || !password}>
              {reset.isPending ? "Resetting…" : "Reset password"}
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}
