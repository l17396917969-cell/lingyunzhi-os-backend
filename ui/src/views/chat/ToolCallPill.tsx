import { useState } from "react";

export interface ToolCall {
  sequence: number;
  name: string;
  args: Record<string, unknown>;
  status: "running" | "ok" | "error";
  summary?: string;
  error?: { code?: string; message?: string };
}

function summarize(args: Record<string, unknown>): string {
  const def = args.definition as Record<string, unknown> | undefined;
  if (def && typeof def === "object" && "api_name" in def) {
    return String((def as { api_name: string }).api_name);
  }
  if ("rid" in args) return String(args.rid);
  return "";
}

export function ToolCallPill({ call }: { call: ToolCall }) {
  const [open, setOpen] = useState(false);

  const meterClass =
    call.status === "ok"
      ? "pill-meter-ok"
      : call.status === "error"
        ? "pill-meter-err"
        : "pill-meter-warn";

  const pipClass =
    call.status === "ok" ? "pip-ok" : call.status === "error" ? "pip-err" : "pip-warn";

  const detail = summarize(call.args);

  return (
    <div
      className={`pill-meter ${meterClass} bubble-in rounded-sm bg-zinc-950/40 hover:bg-zinc-950/70`}
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2.5 px-2.5 py-1.5 text-left"
      >
        <span className={`pip ${pipClass} ${call.status === "running" ? "pulse-soft" : ""}`} />
        <span className="font-mono text-[11px] tabular-nums text-zinc-500">
          #{String(call.sequence).padStart(2, "0")}
        </span>
        <span className="font-mono text-[11.5px] text-zinc-200">{call.name}</span>
        {detail && (
          <span className="truncate font-mono text-[11px] text-zinc-500">
            <span className="text-zinc-700">/ </span>
            {detail}
          </span>
        )}
        {call.summary && call.status === "ok" && (
          <span className="ml-auto truncate font-mono text-[10.5px] text-zinc-400">
            {call.summary}
          </span>
        )}
        <span className="ml-auto font-mono text-[10px] text-zinc-700">
          {open ? "−" : "+"}
        </span>
      </button>
      {open && (
        <pre className="mx-2.5 mb-2 mt-0.5 max-h-48 overflow-auto whitespace-pre-wrap break-all rounded-sm border border-[var(--hairline)] bg-[var(--surface-0)] p-2 font-mono text-[10.5px] leading-relaxed text-zinc-400">
          {JSON.stringify({ args: call.args, error: call.error }, null, 2)}
        </pre>
      )}
    </div>
  );
}
