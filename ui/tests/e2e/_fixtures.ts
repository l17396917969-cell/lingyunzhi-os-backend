import { test as base, expect } from "@playwright/test";

export const test = base.extend<{ apiBaseUrl: string }>({
  // eslint-disable-next-line no-empty-pattern
  apiBaseUrl: async ({}, use) => {
    await use(process.env.API_BASE_URL ?? "http://127.0.0.1:8080");
  },
});

export { expect };

export async function mintToken(
  apiBaseUrl: string,
  scope: "read" | "editor" | "admin",
  label: string,
): Promise<string> {
  const adminToken = process.env.ONTO_BOOTSTRAP_TOKEN!;
  const r = await fetch(`${apiBaseUrl}/mcp`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${adminToken}`,
    },
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: 1,
      method: "tools/call",
      params: { name: "mint_token", arguments: { scope, label } },
    }),
  });
  const body = (await r.json()) as {
    result?: { structuredContent?: { token?: string }; content?: Array<{ text?: string }> };
  };
  // Try structuredContent first, fall back to parsing the content text
  if (body.result?.structuredContent?.token) {
    return body.result.structuredContent.token;
  }
  const text = body.result?.content?.[0]?.text ?? "";
  const m = text.match(/op_[A-Za-z0-9_-]+/);
  if (m) return m[0];
  throw new Error(`Could not extract token from MCP response: ${JSON.stringify(body)}`);
}
