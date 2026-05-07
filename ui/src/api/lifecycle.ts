import { api } from "./client";

export interface DiffPayload {
  added: Record<string, Record<string, unknown>>;
  removed: Record<string, Record<string, unknown>>;
  modified: Record<string, Record<string, unknown>>;
}

export const fetchDiff = () => api<DiffPayload>("/api/registries/diff");

export const promote = (commit_message: string) =>
  api<{ ok: true }>("/api/registries/promote", { method: "POST", body: JSON.stringify({ commit_message }) });

export const revert = () =>
  api<{ ok: true }>("/api/registries/revert", { method: "POST" });

export const undoPromote = () =>
  api<{ ok: true }>("/api/registries/undo-promote", { method: "POST" });
