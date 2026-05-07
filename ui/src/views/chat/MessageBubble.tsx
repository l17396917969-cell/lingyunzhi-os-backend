import { ToolCallPill, type ToolCall } from "./ToolCallPill";

export interface AssistantMessage {
  text: string;
  toolCalls: ToolCall[];
}

export function UserBubble({ text, fileNames }: { text: string; fileNames: string[] }) {
  return (
    <div className="bubble-in flex flex-col items-end">
      <div className="mb-1 flex items-center gap-2 font-mono text-[9px] uppercase tracking-[0.16em] text-zinc-400">
        <span>USER</span>
        <span className="pip pip-idle" style={{ width: 4, height: 4 }} />
      </div>
      <div className="max-w-[78%] rounded-md rounded-br-sm border border-[rgba(34,211,238,0.18)] bg-[rgba(34,211,238,0.06)] px-3.5 py-2.5 text-[13.5px] leading-relaxed text-zinc-100">
        <div className="whitespace-pre-wrap">{text}</div>
        {fileNames.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5 border-t border-[rgba(34,211,238,0.14)] pt-2">
            {fileNames.map((n) => (
              <span
                key={n}
                className="chip-mono inline-flex items-center gap-1 text-[10.5px] text-cyan-200/90"
              >
                <span className="text-cyan-500/60">▢</span>
                {n}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export function AssistantBubble({ message }: { message: AssistantMessage }) {
  const empty = !message.text && message.toolCalls.length === 0;
  return (
    <div className="bubble-in flex flex-col items-start">
      <div className="mb-1 flex items-center gap-2 font-mono text-[9px] uppercase tracking-[0.16em] text-zinc-400">
        <span>AGENT</span>
        <span
          className={`pip ${empty ? "pip-warn pulse-soft" : "pip-ok"}`}
          style={{ width: 4, height: 4 }}
        />
      </div>
      <div className="max-w-[88%] rounded-md rounded-bl-sm border border-[var(--hairline-strong)] bg-[var(--surface-1)] px-3.5 py-2.5">
        {empty && (
          <div className="font-mono text-[11px] uppercase tracking-[0.14em] text-zinc-400">
            思考中…
          </div>
        )}
        {message.text && (
          <div className="whitespace-pre-wrap text-[13.5px] leading-relaxed text-zinc-200">
            {message.text}
          </div>
        )}
        {message.toolCalls.length > 0 && (
          <div className="mt-2.5 flex flex-col gap-1 border-t hairline pt-2.5">
            <div className="mb-1 font-mono text-[9px] uppercase tracking-[0.16em] text-zinc-400">
              工具调用 · {message.toolCalls.length}
            </div>
            {message.toolCalls.map((c) => (
              <ToolCallPill key={c.sequence} call={c} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
