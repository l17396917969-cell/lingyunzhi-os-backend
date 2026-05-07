import { api } from "./client";

interface ListResp {
  items: { rid: string; api_name: string }[];
}

export interface DiffCounts {
  added: {
    object_types: number;
    link_types: number;
    shared_property_types: number;
    interface_types: number;
    action_types: number;
  };
  removed: {
    object_types: number;
    link_types: number;
    shared_property_types: number;
    interface_types: number;
    action_types: number;
  };
}

async function mcpCall<T>(name: string, args: Record<string, unknown>): Promise<T> {
  const r = await api<{ result: { structuredContent?: T; content: { text: string }[] } }>(
    "/mcp",
    {
      method: "POST",
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: 1,
        method: "tools/call",
        params: { name, arguments: args },
      }),
    },
  );
  if (r.result.structuredContent) return r.result.structuredContent;
  return JSON.parse(r.result.content[0].text) as T;
}

const KINDS = [
  "object_types",
  "link_types",
  "shared_property_types",
  "interface_types",
  "action_types",
] as const;

export async function computeDiffCounts(): Promise<DiffCounts> {
  const counts: DiffCounts = {
    added: Object.fromEntries(KINDS.map((k) => [k, 0])) as DiffCounts["added"],
    removed: Object.fromEntries(KINDS.map((k) => [k, 0])) as DiffCounts["removed"],
  };
  for (const kind of KINDS) {
    const tool = "list_" + kind;
    const stage = await mcpCall<ListResp>(tool, { env: "staging" });
    const prod = await mcpCall<ListResp>(tool, { env: "production" });
    const sRids = new Set(stage.items.map((i) => i.rid));
    const pRids = new Set(prod.items.map((i) => i.rid));
    counts.added[kind] = [...sRids].filter((x) => !pRids.has(x)).length;
    counts.removed[kind] = [...pRids].filter((x) => !sRids.has(x)).length;
  }
  return counts;
}

export async function promoteStagingToProduction(): Promise<void> {
  await mcpCall("promote_staging_to_production", {});
}

export async function revertStagingToProduction(): Promise<void> {
  await mcpCall("revert_staging_to_production", {});
}
