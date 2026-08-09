/* -------------------------------------------------------------------------- */
/* Internal mail — an inbox, laid out like one.                               */
/*                                                                             */
/* Folders here are views over this person's own flags rather than separate     */
/* storage: the same message sits in one colleague's inbox and another's        */
/* archive at the same time. Reading, starring and archiving therefore only     */
/* ever change the reader's copy.                                              */
/* -------------------------------------------------------------------------- */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, Inbox, PenSquare, Send, Star, Trash2 } from "lucide-react";
import { useState } from "react";
import { Drawer, ErrorNote, Field, Grid, Input, Section, Textarea } from "../components/RecordKit";
import { Badge, Button, PageHeader, Spinner } from "../components/ui";
import { api } from "../lib/api";
import {
  flagMail,
  listMail,
  mailThread,
  sendMail,
  type MailFolder,
  type MailRow,
} from "../lib/connect";
import { dateTime } from "../lib/format";
import type { MentionableUser, Paginated } from "../lib/types";

const FOLDERS: { key: MailFolder; label: string; icon: typeof Inbox }[] = [
  { key: "inbox", label: "Inbox", icon: Inbox },
  { key: "unread", label: "Unread", icon: Inbox },
  { key: "starred", label: "Starred", icon: Star },
  { key: "archived", label: "Archived", icon: Archive },
  { key: "trash", label: "Trash", icon: Trash2 },
];

export function MailPage() {
  const qc = useQueryClient();
  const [folder, setFolder] = useState<MailFolder>("inbox");
  const [open, setOpen] = useState<MailRow | null>(null);
  const [composing, setComposing] = useState(false);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [to, setTo] = useState<number[]>([]);
  /* Replying is the whole point of mail and the screen could not do it: the
     thread rendered read-only, and compose only ever started a new subject. */
  const [replyBody, setReplyBody] = useState("");
  const [replyAll, setReplyAll] = useState(false);

  const mail = useQuery({
    queryKey: ["mail", folder],
    queryFn: () => listMail(folder),
  });

  const people = useQuery({
    queryKey: ["mentionable-users"],
    queryFn: () =>
      api<Paginated<MentionableUser> | MentionableUser[]>("/api/workspace/mentionable-users"),
  });

  const thread = useQuery({
    queryKey: ["mail-thread", open?.recipient],
    enabled: open != null,
    queryFn: () => mailThread(open!.recipient),
  });

  const refresh = () => void qc.invalidateQueries({ queryKey: ["mail"] });

  const reply = useMutation({
    mutationFn: () =>
      sendMail({
        /* No subject: the server keeps the thread's own, the way a reply should
           never rename the conversation it is joining. */
        subject: "",
        body: replyBody,
        to: (replyAll ? thread.data?.participants : thread.data?.reply_to)?.map((p) => p.id) ?? [],
        thread: thread.data?.thread,
      }),
    onSuccess: () => {
      setReplyBody("");
      void qc.invalidateQueries({ queryKey: ["mail-thread", open?.recipient] });
      refresh();
    },
  });

  const flag = useMutation({
    mutationFn: (p: {
      id: number;
      flag: "read" | "starred" | "archived" | "trashed";
      value: boolean;
    }) => flagMail(p.id, p.flag, p.value),
    onSuccess: refresh,
  });

  const send = useMutation({
    mutationFn: () => sendMail({ subject, body, to }),
    onSuccess: () => {
      setComposing(false);
      setSubject("");
      setBody("");
      setTo([]);
      refresh();
    },
  });

  const rows = mail.data?.results ?? [];
  const summary = mail.data?.summary;
  const contacts = Array.isArray(people.data) ? people.data : (people.data?.results ?? []);

  return (
    <div className="space-y-4">
      <PageHeader
        title="Mail"
        action={
          <Button onClick={() => setComposing(true)}>
            <PenSquare className="h-4 w-4" /> Compose
          </Button>
        }
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[14rem_1fr]">
        <aside className="rounded-lg border border-line bg-surface-0">
          <ul className="divide-y divide-line">
            {FOLDERS.map((f) => {
              const count = summary ? summary[f.key === "trash" ? "trash" : f.key] : 0;
              return (
                <li key={f.key}>
                  <button
                    onClick={() => {
                      setFolder(f.key);
                      setOpen(null);
                    }}
                    className={`flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-surface-100 ${
                      folder === f.key ? "bg-brand-50 text-brand-900" : "text-ink-800"
                    }`}
                  >
                    <f.icon className="h-3.5 w-3.5 shrink-0 text-ink-400" />
                    <span className="flex-1">{f.label}</span>
                    {count > 0 && (
                      <span className="text-xs tabular-nums text-ink-500">{count}</span>
                    )}
                  </button>
                </li>
              );
            })}
            <li>
              <div className="flex items-center gap-2 px-3 py-2 text-sm text-ink-500">
                <Send className="h-3.5 w-3.5 text-ink-400" />
                <span className="flex-1">Sent</span>
                <span className="text-xs tabular-nums">{summary?.sent ?? 0}</span>
              </div>
            </li>
          </ul>
        </aside>

        <section className="rounded-lg border border-line bg-surface-0">
          {mail.isLoading ? (
            <div className="p-4">
              <Spinner />
            </div>
          ) : rows.length === 0 ? (
            <p className="p-6 text-sm text-ink-500">Nothing in {folder}.</p>
          ) : (
            <ul className="divide-y divide-line">
              {rows.map((r) => (
                <li key={r.recipient}>
                  <div
                    className={`flex items-start gap-3 px-4 py-3 hover:bg-surface-100 ${
                      r.is_read ? "" : "bg-brand-50/40"
                    }`}
                  >
                    <button
                      onClick={() =>
                        flag.mutate({ id: r.recipient, flag: "starred", value: !r.is_starred })
                      }
                      className="mt-0.5 shrink-0"
                      aria-label={r.is_starred ? "Unstar" : "Star"}
                    >
                      <Star
                        className={`h-4 w-4 ${
                          r.is_starred ? "fill-warning-400 text-warning-500" : "text-ink-300"
                        }`}
                      />
                    </button>

                    <button
                      onClick={() => {
                        setOpen(r);
                        if (!r.is_read) {
                          flag.mutate({ id: r.recipient, flag: "read", value: true });
                        }
                      }}
                      className="min-w-0 flex-1 text-left"
                    >
                      <div className="flex items-baseline gap-2">
                        <span
                          className={`truncate text-sm ${
                            r.is_read ? "text-ink-700" : "font-semibold text-ink-900"
                          }`}
                        >
                          {r.sender_name || "Unknown sender"}
                        </span>
                        {r.kind !== "TO" && <Badge tone="neutral">{r.kind}</Badge>}
                        <span className="ml-auto shrink-0 text-xs text-ink-500">
                          {dateTime(r.sent_at)}
                        </span>
                      </div>
                      <div
                        className={`truncate text-sm ${
                          r.is_read ? "text-ink-600" : "font-medium text-ink-900"
                        }`}
                      >
                        {r.subject}
                      </div>
                      <div className="truncate text-xs text-ink-500">{r.preview}</div>
                    </button>

                    <button
                      onClick={() =>
                        flag.mutate({
                          id: r.recipient,
                          flag: folder === "trash" ? "trashed" : "archived",
                          value: folder === "trash" ? false : !r.is_archived,
                        })
                      }
                      className="mt-0.5 shrink-0 text-ink-400 hover:text-ink-700"
                      aria-label={folder === "trash" ? "Restore" : "Archive"}
                    >
                      <Archive className="h-4 w-4" />
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      {open && (
        <Drawer
          title={open.subject}
          subtitle={`From ${open.sender_name}`}
          onClose={() => setOpen(null)}
        >
          {thread.isLoading ? (
            <Spinner />
          ) : (
            <>
              <Section title="Conversation">
                <ul className="space-y-3">
                  {(thread.data?.messages ?? []).map((m) => (
                    <li
                      key={m.id}
                      className={`max-w-[85%] rounded-lg border px-3 py-2 ${
                        m.is_mine
                          ? "ml-auto border-brand-200 bg-brand-50"
                          : "border-line bg-surface-0"
                      }`}
                    >
                      <div className="flex items-baseline gap-2">
                        <span className="text-form font-medium text-ink-900">
                          {m.is_mine ? "You" : m.sender_name}
                        </span>
                        <span className="text-micro text-ink-500">{dateTime(m.sent_at)}</span>
                      </div>
                      <p className="mt-1 whitespace-pre-wrap text-form text-ink-800">{m.body}</p>
                    </li>
                  ))}
                </ul>
              </Section>

              {/* The reply box sits at the foot of the conversation, where a
                  reply belongs — not behind a button that opens a new compose
                  window and loses the thread you were reading. */}
              <Section title={replyAll ? "Reply to everyone" : "Reply"}>
                {(thread.data?.participants.length ?? 0) === 0 ? (
                  <p className="text-form text-ink-500">
                    Nobody else is on this thread, so there is no one to reply to.
                  </p>
                ) : (
                  <>
                    <div className="mb-2 flex items-center justify-between gap-3">
                      <span className="text-form text-ink-600">
                        To{" "}
                        {(replyAll ? thread.data?.participants : thread.data?.reply_to)
                          ?.map((p) => p.name)
                          .join(", ") || "—"}
                      </span>
                      {(thread.data?.participants.length ?? 0) > 1 && (
                        <button
                          onClick={() => setReplyAll((v) => !v)}
                          className="text-form font-medium text-brand-700 hover:underline"
                        >
                          {replyAll ? "Reply to sender only" : "Reply to everyone"}
                        </button>
                      )}
                    </div>
                    <Textarea
                      rows={4}
                      value={replyBody}
                      onChange={(e) => setReplyBody(e.target.value)}
                      placeholder="Write a reply…"
                    />
                    <div className="mt-2 flex justify-end">
                      <Button
                        onClick={() => reply.mutate()}
                        disabled={reply.isPending || !replyBody.trim()}
                      >
                        <Send className="h-4 w-4" />
                        {reply.isPending ? "Sending…" : "Send reply"}
                      </Button>
                    </div>
                    <ErrorNote error={reply.error} />
                  </>
                )}
              </Section>
            </>
          )}
        </Drawer>
      )}

      {composing && (
        <Drawer
          title="New message"
          onClose={() => setComposing(false)}
          footer={
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setComposing(false)}>
                Cancel
              </Button>
              <Button
                onClick={() => send.mutate()}
                disabled={send.isPending || !subject.trim() || to.length === 0}
              >
                <Send className="h-4 w-4" />
                {send.isPending ? "Sending…" : "Send"}
              </Button>
            </div>
          }
        >
          <Section title="Recipients">
            <Field label="To">
              <select
                multiple
                size={6}
                value={to.map(String)}
                onChange={(e) =>
                  setTo(Array.from(e.target.selectedOptions).map((o) => Number(o.value)))
                }
                className="w-full rounded-md border border-line bg-surface-0 px-2 py-1.5 text-sm"
              >
                {contacts.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.username}
                  </option>
                ))}
              </select>
            </Field>
            <p className="mt-1 text-xs text-ink-500">
              Hold Ctrl (or Cmd) to select several. Someone addressed twice still gets one copy.
            </p>
          </Section>

          <Section title="Message">
            <Grid cols={2}>
              <Field label="Subject">
                <Input value={subject} onChange={(e) => setSubject(e.target.value)} />
              </Field>
            </Grid>
            <Field label="Body">
              <Textarea rows={8} value={body} onChange={(e) => setBody(e.target.value)} />
            </Field>
          </Section>

          {send.isError && <ErrorNote error={send.error} />}
        </Drawer>
      )}
    </div>
  );
}
