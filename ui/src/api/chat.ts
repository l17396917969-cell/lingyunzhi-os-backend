import { api } from "./client";

export interface ChatMessage {
  turn_index: number;
  role: "user" | "assistant" | "tool_call" | "tool_result";
  content: Record<string, unknown>;
  created_at: string | null;
}

export interface ChatSession {
  session_id: string;
  status: "active" | "saving" | "cancelling";
  messages: ChatMessage[];
}

export const createSession = () =>
  api<{ session_id: string }>("/chat/sessions", { method: "POST" });

export const getSession = (id: string) =>
  api<ChatSession>(`/chat/sessions/${id}`);

export async function uploadToSession(
  id: string,
  file: File,
): Promise<{ upload_id: string; kind: string; size_bytes: number }> {
  const fd = new FormData();
  fd.append("file", file);
  const r = await fetch(`/chat/sessions/${id}/uploads`, {
    method: "POST",
    body: fd,
    credentials: "include",
  });
  if (!r.ok) {
    const body = (await r.json().catch(() => ({}))) as { detail?: { code?: string } };
    throw new Error(body.detail?.code ?? "UPLOAD_FAILED");
  }
  return r.json();
}

export const submitTurn = (id: string, message: string, upload_ids: string[]) =>
  api<{ turn_id: string }>(`/chat/sessions/${id}/turns`, {
    method: "POST",
    body: JSON.stringify({ message, upload_ids }),
  });

export const saveSession = (id: string) =>
  fetch(`/chat/sessions/${id}/save`, { method: "POST", credentials: "include" });

export const cancelSession = (id: string) =>
  fetch(`/chat/sessions/${id}/cancel`, { method: "POST", credentials: "include" });
