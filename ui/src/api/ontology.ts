import { api } from "./client";

export interface RegistrySummary {
  env: "staging" | "production";
  version: number;
  entity_counts: {
    shared_property_types: number;
    interface_types: number;
    object_types: number;
    link_types: number;
    action_types: number;
  };
}

export interface AuditLogItem {
  id: number; ts: string | null; tool: string;
  scope: string | null; outcome: string; error_code: string | null;
  token_label: string | null;
}

export const fetchSummary = (env: "staging" | "production") =>
  api<RegistrySummary>(`/api/registries/${env}/summary`);

export const fetchAuditRecent = () =>
  api<{ items: AuditLogItem[] }>(`/api/audit-log/recent?limit=20`);

export interface FullRegistry {
  version: string;
  shared_property_types: Record<string, unknown>;
  interface_types: Record<string, unknown>;
  object_types: Record<string, unknown>;
  link_types: Record<string, unknown>;
  action_types: Record<string, unknown>;
}

export const fetchFull = (env: "staging" | "production") =>
  api<FullRegistry>(`/api/registries/${env}/full`);
