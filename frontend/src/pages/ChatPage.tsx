/* -------------------------------------------------------------------------- */
/* Chat — spaces and direct messages, threaded.                               */
/*                                                                             */
/* Laid out the way Teams and Google Chat lay it out, because that is what      */
/* people have already learned: a list of rooms on the left with unread counts, */
/* the conversation on the right, replies tucked under the message they answer. */
/* Unread is this viewer's own count — never a shared one.                      */
/* -------------------------------------------------------------------------- */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Hash, Plus, Send, Trash2, User as UserIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { Drawer, ErrorNote, Field, Input, Section } from "../components/RecordKit";
import { Badge, Button, PageHeader, Spinner } from "../components/ui";
import {
  createSpace,
  listMessages,
  listSpaces,
  markSpaceRead,
  messageAction,
  postMessage,
  type ChatMessage,
} from "../lib/connect";
import { dateTime } from "../lib/format";

const QUICK_REACTIONS = ["👍", "✅", "👀", "🎉"];

export function ChatPage() {
  const qc = useQueryClient();
  const [activeId, setActiveId] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [replyTo, setReplyTo] = useState<ChatMessage | null>(null);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [newTopic, setNewTopic] = useState("");

  /* Chat was static: a colleague's reply arrived only if you reloaded the page,
     which makes it a message board. Polling is the honest option here — there is
     no websocket in this stack, and 4s is close enough to live for a counter
     conversation while staying cheap on a weak connection. */
  const spaces = useQuery({
    queryKey: ["spaces"],
    queryFn: listSpaces,
    refetchInterval: 15_000,
  });

  // Open the first space once the list arrives, so the screen is never an
  // empty pane with no indication of what to do.
  useEffect(() => {
    if (activeId === null && spaces.data?.length) setActiveId(spaces.data[0].id);
  }, [spaces.data, activeId]);

  const messages = useQuery({
    queryKey: ["messages", activeId],
    enabled: activeId != null,
    queryFn: () => listMessages(activeId as number),
    refetchInterval: 4_000,
    /* Keep the thread on screen while the next poll lands, so the conversation
       does not blink out every four seconds. */
    placeholderData: (prev) => prev,
  });

  const read = useMutation({
    mutationFn: (id: number) => markSpaceRead(id),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["spaces"] }),
  });

  // Opening a space marks it read for this person only.
  useEffect(() => {
    if (activeId != null && messages.data) read.mutate(activeId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeId, messages.data]);

  const send = useMutation({
    mutationFn: () => postMessage(activeId as number, draft, replyTo?.id),
    onSuccess: () => {
      setDraft("");
      setReplyTo(null);
      void qc.invalidateQueries({ queryKey: ["messages", activeId] });
      void qc.invalidateQueries({ queryKey: ["spaces"] });
    },
  });

  const act = useMutation({
    mutationFn: (p: { id: number; verb: "delete" | "react"; payload?: Record<string, unknown> }) =>
      messageAction(p.id, p.verb, p.payload ?? {}),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["messages", activeId] }),
  });

  const create = useMutation({
    mutationFn: () => createSpace(newName, [], newTopic),
    onSuccess: (space) => {
      setCreating(false);
      setNewName("");
      setNewTopic("");
      setActiveId(space.id);
      void qc.invalidateQueries({ queryKey: ["spaces"] });
    },
  });

  const rooms = spaces.data ?? [];
  const active = rooms.find((s) => s.id === activeId) ?? null;

  return (
    <div className="space-y-4">
      <PageHeader
        title="Chat"
        action={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" /> New space
          </Button>
        }
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[16rem_1fr]">
        <aside className="rounded-lg border border-line bg-surface-0">
          <div className="border-b border-line px-3 py-2 text-xs font-semibold text-ink-500">
            Spaces
          </div>
          {spaces.isLoading ? (
            <div className="p-4">
              <Spinner />
            </div>
          ) : rooms.length === 0 ? (
            <p className="p-4 text-sm text-ink-500">
              No spaces yet. Create one for your branch or team.
            </p>
          ) : (
            <ul className="max-h-[28rem] divide-y divide-line overflow-y-auto">
              {rooms.map((s) => (
                <li key={s.id}>
                  <button
                    onClick={() => setActiveId(s.id)}
                    className={`flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-surface-100 ${
                      s.id === activeId ? "bg-brand-50 text-brand-900" : "text-ink-800"
                    }`}
                  >
                    {s.is_direct ? (
                      <UserIcon className="h-3.5 w-3.5 shrink-0 text-ink-400" />
                    ) : (
                      <Hash className="h-3.5 w-3.5 shrink-0 text-ink-400" />
                    )}
                    <span className="min-w-0 flex-1 truncate">{s.name}</span>
                    {s.unread > 0 && <Badge tone="brand">{s.unread}</Badge>}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        <section className="flex min-h-[28rem] flex-col rounded-lg border border-line bg-surface-0">
          {active === null ? (
            <div className="flex flex-1 items-center justify-center p-8 text-sm text-ink-500">
              Choose a space to start reading.
            </div>
          ) : (
            <>
              <header className="border-b border-line px-4 py-3">
                <div className="text-sm font-semibold text-ink-900">{active.name}</div>
                <div className="text-xs text-ink-500">
                  {active.topic ||
                    (active.is_direct ? "Direct message" : `${active.members.length} member(s)`)}
                </div>
              </header>

              <div className="flex-1 space-y-3 overflow-y-auto p-4">
                {messages.isLoading ? (
                  <Spinner />
                ) : (messages.data ?? []).length === 0 ? (
                  <p className="text-sm text-ink-500">Nothing here yet — say something.</p>
                ) : (
                  (messages.data ?? []).map((m) => (
                    <MessageRow
                      key={m.id}
                      message={m}
                      onReply={() => setReplyTo(m)}
                      onDelete={() => act.mutate({ id: m.id, verb: "delete" })}
                      onReact={(emoji) =>
                        act.mutate({ id: m.id, verb: "react", payload: { emoji } })
                      }
                    />
                  ))
                )}
              </div>

              <footer className="border-t border-line p-3">
                {replyTo && (
                  <div className="mb-2 flex items-center justify-between rounded-md bg-surface-100 px-2 py-1 text-xs text-ink-600">
                    <span className="truncate">
                      Replying to {replyTo.author_name}: {replyTo.body.slice(0, 60)}
                    </span>
                    <button onClick={() => setReplyTo(null)} className="ml-2 text-ink-500">
                      cancel
                    </button>
                  </div>
                )}
                <div className="flex gap-2">
                  <Input
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey && draft.trim()) {
                        e.preventDefault();
                        send.mutate();
                      }
                    }}
                    placeholder={replyTo ? "Reply…" : `Message ${active.name}`}
                  />
                  <Button onClick={() => send.mutate()} disabled={send.isPending || !draft.trim()}>
                    <Send className="h-4 w-4" />
                  </Button>
                </div>
                {send.isError && <ErrorNote error={send.error} />}
              </footer>
            </>
          )}
        </section>
      </div>

      {creating && (
        <Drawer
          title="New space"
          onClose={() => setCreating(false)}
          footer={
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setCreating(false)}>
                Cancel
              </Button>
              <Button
                onClick={() => create.mutate()}
                disabled={create.isPending || !newName.trim()}
              >
                {create.isPending ? "Creating…" : "Create space"}
              </Button>
            </div>
          }
        >
          <Section title="About this space">
            <Field label="Name">
              <Input
                autoFocus
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Kigali branch"
              />
            </Field>
            <Field label="Topic">
              <Input
                value={newTopic}
                onChange={(e) => setNewTopic(e.target.value)}
                placeholder="Daily operations and handover"
              />
            </Field>
          </Section>
          {create.isError && <ErrorNote error={create.error} />}
        </Drawer>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */

function MessageRow({
  message,
  onReply,
  onDelete,
  onReact,
}: {
  message: ChatMessage;
  onReply: () => void;
  onDelete: () => void;
  onReact: (emoji: string) => void;
}) {
  /* `is_mine` has been on the payload all along and the screen rendered every
     message identically, so a conversation read as a flat log. Side and tint are
     what make it read as a conversation — and the author's name is dropped on
     your own messages, because you know who you are. */
  const mine = message.is_mine;

  return (
    <div className={`group flex flex-col ${mine ? "items-end" : "items-start"}`}>
      <div
        className={`max-w-[75%] rounded-2xl px-3 py-2 ${
          mine
            ? "rounded-br-sm bg-brand-600 text-white"
            : "rounded-bl-sm bg-surface-100 text-ink-900"
        }`}
      >
        {!mine && (
          <span className="block text-micro font-semibold text-ink-700">{message.author_name}</span>
        )}
        {message.is_deleted ? (
          <p className={`text-form italic ${mine ? "text-white/70" : "text-ink-400"}`}>
            This message was deleted.
          </p>
        ) : (
          <p className="whitespace-pre-wrap text-form">{message.body}</p>
        )}
      </div>

      <div className="mt-0.5 flex items-center gap-1.5 px-1">
        <span className="text-micro text-ink-500">{dateTime(message.created_at)}</span>
        {message.edited_at && <span className="text-micro text-ink-400">edited</span>}
      </div>

      <div className="mt-1 flex flex-wrap items-center gap-1.5">
        {message.reactions.map((r) => (
          <button
            key={r.emoji}
            onClick={() => onReact(r.emoji)}
            className={`rounded-full border px-1.5 py-0.5 text-xs ${
              r.mine ? "border-brand-300 bg-brand-50" : "border-line bg-surface-100"
            }`}
          >
            {r.emoji} {r.count}
          </button>
        ))}
        <div className="flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
          {QUICK_REACTIONS.map((e) => (
            <button
              key={e}
              onClick={() => onReact(e)}
              className="rounded px-1 text-xs hover:bg-surface-100"
              aria-label={`React ${e}`}
            >
              {e}
            </button>
          ))}
          <button
            onClick={onReply}
            className="rounded px-1 text-xs text-ink-500 hover:bg-surface-100"
          >
            Reply
          </button>
          {message.is_mine && !message.is_deleted && (
            <button
              onClick={onDelete}
              className="rounded px-1 text-ink-400 hover:bg-danger-50 hover:text-danger-600"
              aria-label="Delete message"
            >
              <Trash2 className="h-3 w-3" />
            </button>
          )}
        </div>
      </div>

      {(message.replies ?? []).length > 0 && (
        <ul className="mt-2 space-y-2 border-l-2 border-line pl-3">
          {(message.replies ?? []).map((r) => (
            <li key={r.id}>
              <div className="flex items-baseline gap-2">
                <span className="text-xs font-medium text-ink-900">{r.author_name}</span>
                <span className="text-xs text-ink-500">{dateTime(r.created_at)}</span>
              </div>
              {r.is_deleted ? (
                <p className="text-xs italic text-ink-400">This message was deleted.</p>
              ) : (
                <p className="whitespace-pre-wrap text-sm text-ink-700">{r.body}</p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
