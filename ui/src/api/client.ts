export class ApiError extends Error {
  constructor(public status: number, public code?: string, public details?: unknown) {
    super(`${status} ${code ?? ""}`.trim());
  }
}

export async function api<T = unknown>(path: string, init: RequestInit = {}): Promise<T> {
  const r = await fetch(path, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });
  if (!r.ok) {
    let body: unknown = null;
    try { body = await r.json(); } catch { /* */ }
    const b = body as Record<string, unknown> | null;
    throw new ApiError(r.status, (b?.detail as Record<string, unknown>)?.code as string | undefined ?? b?.code as string | undefined, (b?.detail ?? b) as unknown);
  }
  return r.json() as Promise<T>;
}
