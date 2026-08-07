/* -------------------------------------------------------------------------- */
/* Connect client: chat and internal mail.                                    */
/*                                                                             */
/* Unread, read, starred and archived are all per person — the API returns     */
/* this viewer's state, never a shared one.                                    */
/* -------------------------------------------------------------------------- */

import { api } from "./api";

/* --- Chat ----------------------------------------------------------------- */

export interface SpaceMemberRow {
  user: number;
  name: string;
  role: string;
}

export interface Space {
  id: number;
  kind: "SPACE" | "DIRECT";
  /** For a direct message this is the other person's name. */
  name: string;
  topic: string;
  is_private: boolean;
  is_direct: boolean;
  members: SpaceMemberRow[];
  last_activity_at: string;
  unread: number;
}

export interface ChatReaction {
  emoji: string;
  count: number;
  mine: boolean;
}

export interface ChatMessage {
  id: number;
  space: number;
  parent: number | null;
  author: number | null;
  author_name: string;
  body: string;
  is_deleted: boolean;
  is_mine: boolean;
  edited_at: string | null;
  created_at: string;
  reply_count: number;
  reactions: ChatReaction[];
  replies?: ChatMessage[];
}

export async function listSpaces(): Promise<Space[]> {
  const body = await api<{ results: Space[] }>("/api/workspace/spaces/");
  return body.results;
}

export function createSpace(name: string, members: number[] = [], topic = "", isPrivate = false) {
  return api<Space>("/api/workspace/spaces/", {
    method: "POST",
    body: JSON.stringify({ name, members, topic, is_private: isPrivate }),
  });
}

/** Opens the existing one-to-one space if there is one, rather than a second. */
export function openDirect(userId: number) {
  return api<Space>("/api/workspace/spaces/direct/", {
    method: "POST",
    body: JSON.stringify({ user: userId }),
  });
}

export async function listMessages(spaceId: number): Promise<ChatMessage[]> {
  const body = await api<{ results: ChatMessage[] }>(
    `/api/workspace/spaces/${spaceId}/messages/`,
  );
  return body.results;
}

export function postMessage(spaceId: number, body: string, parent?: number) {
  return api<ChatMessage>(`/api/workspace/spaces/${spaceId}/messages/`, {
    method: "POST",
    body: JSON.stringify({ body, parent }),
  });
}

export function markSpaceRead(spaceId: number) {
  return api<{ ok: boolean }>(`/api/workspace/spaces/${spaceId}/read/`, { method: "POST" });
}

export function messageAction(
  id: number,
  verb: "edit" | "delete" | "react",
  payload: Record<string, unknown> = {},
) {
  return api<ChatMessage>(`/api/workspace/messages/${id}/${verb}/`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/* --- Mail ----------------------------------------------------------------- */

export type MailFolder = "inbox" | "unread" | "starred" | "archived" | "trash";

export interface MailSummary {
  inbox: number;
  unread: number;
  starred: number;
  archived: number;
  trash: number;
  sent: number;
}

export interface MailRow {
  recipient: number;
  message: number;
  thread: number;
  subject: string;
  sender: number | null;
  sender_name: string;
  preview: string;
  kind: "TO" | "CC" | "BCC";
  is_read: boolean;
  is_starred: boolean;
  is_archived: boolean;
  sent_at: string;
}

export function listMail(folder: MailFolder = "inbox") {
  return api<{ folder: string; summary: MailSummary; results: MailRow[] }>(
    `/api/workspace/mail/?folder=${folder}`,
  );
}

export function sendMail(payload: {
  subject: string;
  body: string;
  to: number[];
  cc?: number[];
  bcc?: number[];
  thread?: number;
}) {
  return api<{ thread: number; message: number; recipients: number }>(
    "/api/workspace/mail/",
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export function listSent() {
  return api<{
    results: {
      message: number;
      thread: number;
      subject: string;
      preview: string;
      sent_at: string;
      recipients: number;
    }[];
  }>("/api/workspace/mail/sent/");
}

/** Read, star, archive, trash — always this person's own copy. */
export function flagMail(
  recipientId: number,
  flag: "read" | "starred" | "archived" | "trashed",
  value: boolean,
) {
  return api<{ is_read: boolean; is_starred: boolean; is_archived: boolean; is_trashed: boolean }>(
    `/api/workspace/mail/${recipientId}/flag/`,
    { method: "POST", body: JSON.stringify({ flag, value }) },
  );
}

export function mailThread(recipientId: number) {
  return api<{
    thread: number;
    subject: string;
    messages: { id: number; sender: number | null; sender_name: string; body: string; sent_at: string }[];
  }>(`/api/workspace/mail/${recipientId}/thread/`);
}

/* --- Search --------------------------------------------------------------- */

export function searchConnect(term: string) {
  return api<{
    messages: {
      id: number;
      space: number;
      space_name: string;
      author: string;
      body: string;
      created_at: string;
    }[];
    mail: {
      recipient: number;
      thread: number;
      subject: string;
      sender: string;
      sent_at: string;
      is_read: boolean;
    }[];
  }>(`/api/workspace/search/?q=${encodeURIComponent(term)}`);
}
