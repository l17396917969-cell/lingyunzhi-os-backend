import { useState } from "react";
import { api, ApiError } from "@/api/client";
import { translateError } from "@/api/errorMessages";

export function Login({ onSuccess }: { onSuccess: () => void }) {
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  return (
    <div className="flex min-h-screen items-center justify-center px-6">
      {/* faint grid backdrop */}
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 opacity-[0.04]"
        style={{
          backgroundImage:
            "linear-gradient(to right, #f4f4f5 1px, transparent 1px), linear-gradient(to bottom, #f4f4f5 1px, transparent 1px)",
          backgroundSize: "48px 48px",
        }}
      />

      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setError(null);
          setSubmitting(true);
          try {
            await api("/admin/login", { method: "POST", body: JSON.stringify({ token }) });
            onSuccess();
          } catch (err) {
            if (err instanceof ApiError && err.status === 401) {
              setError("令牌无效或已被撤销");
            } else if (err instanceof ApiError) {
              setError(translateError(err.code));
            } else {
              setError("登录失败");
            }
            setSubmitting(false);
          }
        }}
        className="corner-ticks panel relative w-[24rem] p-8"
      >
        {/* header */}
        <div className="mb-7 flex items-center justify-between">
          <div>
            <div className="font-display text-[28px] font-medium leading-none tracking-tight text-zinc-50">
              登录
            </div>
            <div className="mt-2 font-mono text-[10px] uppercase tracking-[0.18em] text-zinc-500">
              Sign In · Onto Platform
            </div>
          </div>
          <div className="flex flex-col items-end gap-1">
            <span className="pip pip-ok pulse-soft" />
            <span className="font-mono text-[9px] uppercase tracking-[0.14em] text-zinc-400">
              READY
            </span>
          </div>
        </div>

        {/* divider */}
        <div className="mb-5 flex items-center gap-3">
          <div className="h-px flex-1 bg-[var(--hairline-strong)]" />
          <div className="font-mono text-[9px] uppercase tracking-[0.18em] text-zinc-400">
            01 · 凭证
          </div>
          <div className="h-px flex-1 bg-[var(--hairline-strong)]" />
        </div>

        <p className="mb-4 text-[12px] leading-relaxed text-zinc-500">
          使用管理员或编辑令牌进入本体平台。
        </p>

        <label className="block">
          <span className="mb-1.5 block font-mono text-[10px] uppercase tracking-[0.14em] text-zinc-500">
            令牌 / TOKEN
          </span>
          <input
            aria-label="令牌"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            className="w-full rounded-sm border border-[var(--hairline-strong)] bg-[var(--surface-0)] px-3 py-2.5 font-mono text-[13px] text-zinc-100 placeholder:text-zinc-700 focus:border-[var(--accent)] focus:outline-none focus:ring-1 focus:ring-[var(--accent-soft)]"
            placeholder="op_…"
            autoFocus
            spellCheck={false}
          />
        </label>

        {error && (
          <div
            role="alert"
            className="bubble-in mt-4 flex items-center gap-2 rounded-sm border border-red-900/40 bg-red-950/20 px-3 py-2 text-[12px] text-red-300"
          >
            <span className="pip pip-err" />
            <span>{error}</span>
          </div>
        )}

        <button
          type="submit"
          disabled={submitting || !token}
          className="mt-6 group relative flex w-full items-center justify-between rounded-sm border border-[var(--hairline-strong)] bg-[var(--surface-2)] px-4 py-2.5 font-mono text-[12px] uppercase tracking-[0.18em] text-zinc-100 hover:border-[var(--accent)] hover:bg-[rgba(34,211,238,0.06)] hover:text-[var(--accent)] disabled:opacity-40 disabled:hover:border-[var(--hairline-strong)] disabled:hover:bg-[var(--surface-2)] disabled:hover:text-zinc-500"
        >
          <span>{submitting ? "验证中…" : "登录"}</span>
          <span className="text-zinc-400 group-hover:text-[var(--accent)]">→</span>
        </button>

        <div className="mt-6 border-t hairline pt-4 font-mono text-[9px] uppercase tracking-[0.18em] text-zinc-400">
          v1 · zh-CN
        </div>
      </form>
    </div>
  );
}

export default Login;
