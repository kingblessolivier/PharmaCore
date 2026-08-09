import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { api, ApiError } from "../lib/api";
import { Button, Modal, SelectField, Spinner, TextField } from "./ui";

// Local types — keep out of the shared lib/types.ts.
interface ApiKeyRow {
  id: number;
  name: string;
  user_name: string;
  prefix: string;
  last_used_at: string | null;
}
interface UserRow {
  id: number;
  username: string;
}
interface Paged<T> {
  results: T[];
}

export function ApiKeysModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const keys = useQuery({
    queryKey: ["api-keys"],
    queryFn: () => api<Paged<ApiKeyRow>>("/api/api-keys/"),
  });
  const users = useQuery({
    queryKey: ["all-users"],
    queryFn: () => api<Paged<UserRow>>("/api/users/"),
  });
  const [name, setName] = useState("");
  const [userId, setUserId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [newKey, setNewKey] = useState<string | null>(null);
  const refresh = () => qc.invalidateQueries({ queryKey: ["api-keys"] });

  const create = useMutation({
    mutationFn: () =>
      api<{ key: string }>("/api/api-keys/", {
        method: "POST",
        body: JSON.stringify({ name, user: Number(userId) }),
      }),
    onSuccess: (d) => {
      setNewKey(d.key);
      setName("");
      setUserId("");
      void refresh();
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not create the key."),
  });
  const revoke = useMutation({
    mutationFn: (id: number) => api<void>(`/api/api-keys/${id}/`, { method: "DELETE" }),
    onSuccess: () => void refresh(),
  });

  return (
    <Modal title="API keys &amp; service accounts" size="lg" onClose={onClose}>
      <div className="flex flex-col gap-4">
        <p className="text-sm text-ink-500">
          A key authenticates machine/integration requests <strong>as the chosen user</strong>
          (with that user's roles and pharmacy). Send it as an <code>X-API-Key</code> header.
        </p>

        {newKey && (
          <div className="rounded-lg border border-brand-600 bg-brand-50/50 p-3">
            <div className="text-xs font-semibold text-brand-700">
              New key — copy it now, it won't be shown again
            </div>
            <code className="mt-1 block break-all rounded bg-surface-0 px-2 py-1.5 text-sm">
              {newKey}
            </code>
          </div>
        )}

        <div className="overflow-hidden rounded-lg border border-line">
          <table className="w-full text-sm">
            <thead className="border-b border-line text-left text-xs text-ink-500">
              <tr>
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Acts as</th>
                <th className="px-3 py-2">Prefix</th>
                <th className="px-3 py-2">Last used</th>
                <th className="px-3 py-2 text-right">—</th>
              </tr>
            </thead>
            <tbody>
              {keys.isLoading && (
                <tr>
                  <td colSpan={5} className="py-6 text-center">
                    <Spinner />
                  </td>
                </tr>
              )}
              {(keys.data?.results ?? []).map((k) => (
                <tr key={k.id} className="border-b border-line last:border-0">
                  <td className="px-3 py-2 font-medium">{k.name}</td>
                  <td className="px-3 py-2 text-ink-700">{k.user_name}</td>
                  <td className="px-3 py-2 font-mono text-ink-500">{k.prefix}…</td>
                  <td className="px-3 py-2 text-ink-500">
                    {k.last_used_at ? new Date(k.last_used_at).toLocaleString() : "never"}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <button
                      onClick={() => revoke.mutate(k.id)}
                      className="rounded-md p-1.5 text-ink-500 hover:bg-red-50 hover:text-red-600"
                      aria-label={`Revoke ${k.name}`}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
              {keys.data?.results.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-3 py-5 text-center text-ink-500">
                    No API keys yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="rounded-lg border border-line bg-surface-50 p-3">
          <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-ink-500">
            <KeyRound className="h-3.5 w-3.5" /> Create a key
          </div>
          <div className="grid grid-cols-2 gap-3">
            <TextField
              label="Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. EBM bridge"
            />
            <SelectField
              label="Acts as user"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
            >
              <option value="">— select user —</option>
              {(users.data?.results ?? []).map((u) => (
                <option key={u.id} value={u.id}>
                  {u.username}
                </option>
              ))}
            </SelectField>
          </div>
          {error && <p className="mt-2 text-sm text-danger-700">{error}</p>}
          <div className="mt-3 flex justify-end">
            <Button onClick={() => create.mutate()} disabled={create.isPending || !name || !userId}>
              <Plus className="h-4 w-4" /> Create key
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  );
}
