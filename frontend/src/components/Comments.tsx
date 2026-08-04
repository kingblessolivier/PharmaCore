import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Send } from "lucide-react";
import { useState, type FormEvent } from "react";
import { api } from "../lib/api";
import type { Comment, MentionableUser, Paginated } from "../lib/types";
import { Button, Spinner } from "./ui";

/** Reusable contextual-comments panel for any record. */
export function Comments({
  entityType,
  entityId,
  organization,
}: {
  entityType: string;
  entityId: string | number;
  organization?: number | null;
}) {
  const qc = useQueryClient();
  const key = ["comments", entityType, String(entityId)];
  const [body, setBody] = useState("");
  const [mentions, setMentions] = useState<number[]>([]);

  const comments = useQuery({
    queryKey: key,
    queryFn: () =>
      api<Paginated<Comment>>(
        `/api/workspace/comments/?entity_type=${entityType}&entity_id=${entityId}`,
      ),
  });
  const users = useQuery({
    queryKey: ["mentionable", organization ?? "all"],
    queryFn: () =>
      api<MentionableUser[]>(
        `/api/workspace/mentionable-users${organization ? `?organization=${organization}` : ""}`,
      ),
  });

  const add = useMutation({
    mutationFn: () =>
      api<Comment>("/api/workspace/comments/", {
        method: "POST",
        body: JSON.stringify({
          entity_type: entityType,
          entity_id: String(entityId),
          organization: organization ?? null,
          body,
          mentions,
        }),
      }),
    onSuccess: () => {
      setBody("");
      setMentions([]);
      void qc.invalidateQueries({ queryKey: key });
    },
  });

  const strike = useMutation({
    mutationFn: (id: number) => api<Comment>(`/api/workspace/comments/${id}/strike/`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: key }),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    if (body.trim()) add.mutate();
  }

  return (
    <div className="flex flex-col gap-3">
      {comments.isLoading && (
        <div className="flex justify-center py-4">
          <Spinner />
        </div>
      )}
      <ul className="flex flex-col gap-2">
        {(comments.data?.results ?? []).map((c) => (
          <li key={c.id} className="rounded-md bg-surface-100 px-3 py-2 text-sm">
            <div className="mb-0.5 flex items-center justify-between">
              <span className="font-medium text-ink-900">{c.author_name ?? "—"}</span>
              <span className="text-[11px] text-ink-500">{new Date(c.created_at).toLocaleString()}</span>
            </div>
            <p className={c.is_struck ? "text-ink-500 line-through" : "text-ink-700"}>{c.body}</p>
            {!c.is_struck && (
              <button onClick={() => strike.mutate(c.id)} className="mt-0.5 text-[11px] text-ink-500 hover:text-red-600">
                strike
              </button>
            )}
          </li>
        ))}
        {comments.data?.results.length === 0 && <li className="text-sm text-ink-500">No comments yet.</li>}
      </ul>

      <form onSubmit={submit} className="flex flex-col gap-2 border-t border-line pt-3">
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={2}
          placeholder="Add a comment…"
          className="rounded-md border border-line bg-surface-0 px-3 py-2 text-sm outline-none focus:border-brand-600"
        />
        <div className="flex items-center justify-between gap-2">
          <select
            multiple={false}
            value=""
            onChange={(e) => {
              const id = Number(e.target.value);
              if (id && !mentions.includes(id)) setMentions((m) => [...m, id]);
            }}
            className="rounded-md border border-line bg-surface-0 px-2 py-1 text-xs text-ink-600"
          >
            <option value="">@ mention…</option>
            {(users.data ?? []).map((u) => (
              <option key={u.id} value={u.id}>
                {u.username}
              </option>
            ))}
          </select>
          <div className="flex items-center gap-2">
            {mentions.length > 0 && (
              <span className="text-xs text-brand-700">
                notifying {mentions.map((id) => users.data?.find((u) => u.id === id)?.username).filter(Boolean).join(", ")}
              </span>
            )}
            <Button type="submit" disabled={add.isPending}>
              <Send className="h-4 w-4" /> Comment
            </Button>
          </div>
        </div>
      </form>
    </div>
  );
}
