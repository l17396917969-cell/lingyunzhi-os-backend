import { api } from "./client";

export interface JobRow {
  id: string; status: string; mode: string; progress_pct: number;
  error_code: string | null; created_at: string | null;
}

export async function uploadFile(file: File): Promise<{ upload_id: string; kind: string; size_bytes: number }> {
  const fd = new FormData();
  fd.append("file", file);
  const r = await fetch("/admin/ingestion/uploads", { method: "POST", body: fd, credentials: "include" });
  if (!r.ok) {
    const body = await r.json().catch(() => ({})) as Record<string, unknown>;
    const detail = body?.detail as Record<string, unknown> | undefined;
    throw new Error((detail?.code as string | undefined) ?? (body?.code as string | undefined) ?? "UPLOAD_FAILED");
  }
  return r.json() as Promise<{ upload_id: string; kind: string; size_bytes: number }>;
}

export const submitJob = (upload_ids: string[], mode: "replace" | "merge", instructions?: string) =>
  api<{ job_id: string; status: string }>("/admin/ingestion/jobs", {
    method: "POST", body: JSON.stringify({ upload_ids, mode, instructions }),
  });

export const listJobs = () =>
  api<{ items: JobRow[] }>("/admin/ingestion/jobs?limit=50").catch(() => ({ items: [] as JobRow[] }));

export const getJob = (id: string) =>
  api<Record<string, unknown>>(`/admin/ingestion/jobs/${id}`);

export const cancelJob = (id: string) =>
  fetch(`/admin/ingestion/jobs/${id}:cancel`, { method: "POST", credentials: "include" });
