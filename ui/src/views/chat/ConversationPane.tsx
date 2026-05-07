import { useEffect, useRef, useState } from "react";
import { uploadToSession } from "@/api/chat";
import { translateError } from "@/api/errorMessages";
import { UserBubble, AssistantBubble, type AssistantMessage } from "./MessageBubble";

export interface ChatTurnView {
  user: { text: string; fileNames: string[] } | null;
  assistant: AssistantMessage | null;
}

export interface ConversationPaneProps {
  sessionId: string;
  turns: ChatTurnView[];
  busy: boolean;
  onSubmit: (message: string, uploadIds: string[]) => Promise<void>;
  onSave: () => void;
  onCancel: () => void;
}

export function ConversationPane(props: ConversationPaneProps) {
  const [text, setText] = useState("");
  const [pendingFiles, setPendingFiles] = useState<{ id: string; name: string; size: number }[]>([]);
  const [error, setError] = useState<string | null>(null);
  const dragCount = useRef(0);
  const [dragHover, setDragHover] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll on new messages (unless user has scrolled up)
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100;
    if (nearBottom) el.scrollTop = el.scrollHeight;
  }, [props.turns]);

  async function handleFiles(files: FileList | File[]) {
    setError(null);
    for (const f of Array.from(files)) {
      try {
        const r = await uploadToSession(props.sessionId, f);
        setPendingFiles((p) => [...p, { id: r.upload_id, name: f.name, size: r.size_bytes }]);
      } catch (e) {
        setError(translateError((e as Error).message));
      }
    }
  }

  async function send() {
    if (!text.trim() && pendingFiles.length === 0) return;
    const ids = pendingFiles.map((f) => f.id);
    const msg = text;
    setText("");
    setPendingFiles([]);
    try {
      await props.onSubmit(msg, ids);
    } catch (e) {
      setError(translateError(((e as { code?: string })?.code) ?? undefined));
    }
  }

  const turnCount = props.turns.length;

  return (
    <div
      className={`flex h-full flex-col ${dragHover ? "drop-active" : ""}`}
      onDragEnter={(e) => {
        e.preventDefault();
        dragCount.current += 1;
        setDragHover(true);
      }}
      onDragLeave={() => {
        dragCount.current -= 1;
        if (dragCount.current <= 0) setDragHover(false);
      }}
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => {
        e.preventDefault();
        dragCount.current = 0;
        setDragHover(false);
        if (e.dataTransfer.files.length) void handleFiles(e.dataTransfer.files);
      }}
    >
      {/* Header */}
      <div className="border-b hairline px-5 py-3">
        <div className="flex items-baseline justify-between">
          <div className="flex items-baseline gap-3">
            <span className="section-label">
              <span className="section-num">01</span> · 对话
            </span>
            <span className="font-display text-[20px] font-medium text-zinc-100">
              注入会话
            </span>
            {props.busy && (
              <span className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-amber-400/80">
                <span className="pip pip-warn pulse-soft" />
                进行中
              </span>
            )}
          </div>
          <div className="flex items-center gap-2.5">
            <span className="chip-mono text-zinc-400">{props.sessionId.slice(0, 8)}</span>
            <button
              type="button"
              disabled={props.busy}
              onClick={props.onSave}
              className="rounded-sm border border-emerald-700/40 bg-emerald-950/30 px-3 py-1 font-mono text-[11px] uppercase tracking-[0.12em] text-emerald-300 hover:border-emerald-500 hover:bg-emerald-900/40 hover:text-emerald-200 disabled:opacity-40"
            >
              保存
            </button>
            <button
              type="button"
              disabled={props.busy}
              onClick={props.onCancel}
              className="rounded-sm border border-red-900/40 bg-red-950/20 px-3 py-1 font-mono text-[11px] uppercase tracking-[0.12em] text-red-300 hover:border-red-500/70 hover:bg-red-900/30 hover:text-red-200 disabled:opacity-40"
            >
              取消
            </button>
          </div>
        </div>
      </div>

      {/* Message stream */}
      <div ref={scrollRef} className="flex flex-1 flex-col gap-5 overflow-auto px-5 py-6">
        {turnCount === 0 && !props.busy && (
          <div className="m-auto max-w-md text-center">
            <div className="mb-3 font-display text-[18px] text-zinc-300">
              准备就绪
            </div>
            <p className="text-[13px] leading-relaxed text-zinc-500">
              输入消息或拖入 <span className="chip-mono text-zinc-400">.sql</span>{" "}
              <span className="chip-mono text-zinc-400">.csv</span>{" "}
              <span className="chip-mono text-zinc-400">.json</span> 文件，开始本轮注入。
            </p>
            <div className="mt-4 font-mono text-[10px] uppercase tracking-[0.18em] text-zinc-700">
              session · {props.sessionId.slice(0, 12)}
            </div>
          </div>
        )}

        {props.turns.map((t, i) => (
          <div key={i} className="flex flex-col gap-3">
            {/* turn marker */}
            <div className="flex items-center gap-2 font-mono text-[9px] uppercase tracking-[0.18em] text-zinc-700">
              <span>turn {String(i + 1).padStart(2, "0")}</span>
              <span className="h-px flex-1 bg-[var(--hairline)]" />
            </div>
            {t.user && <UserBubble text={t.user.text} fileNames={t.user.fileNames} />}
            {t.assistant && <AssistantBubble message={t.assistant} />}
          </div>
        ))}
      </div>

      {/* Input area */}
      <div className="border-t hairline bg-[var(--surface-0)] px-5 py-4">
        {pendingFiles.length > 0 && (
          <div className="mb-2 flex flex-wrap items-center gap-1.5">
            <span className="font-mono text-[9px] uppercase tracking-[0.16em] text-zinc-400">
              附件 · {pendingFiles.length}
            </span>
            {pendingFiles.map((f) => (
              <span
                key={f.id}
                className="chip-mono inline-flex items-center gap-1.5 text-zinc-300"
              >
                <span className="text-cyan-500/70">▢</span>
                <span>{f.name}</span>
                <span className="text-zinc-400">{formatBytes(f.size)}</span>
                <button
                  type="button"
                  onClick={() => setPendingFiles((p) => p.filter((x) => x.id !== f.id))}
                  className="ml-0.5 text-zinc-400 hover:text-zinc-300"
                  aria-label="remove file"
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        )}

        <div
          className={`relative rounded-sm border bg-[var(--surface-1)] transition ${
            dragHover
              ? "border-[var(--accent)]"
              : "border-dashed border-[var(--hairline-strong)] hover:border-zinc-700"
          }`}
        >
          <textarea
            aria-label="message"
            rows={2}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void send();
              }
            }}
            placeholder="输入消息，或将文件拖入此处…"
            className="w-full resize-none bg-transparent px-3.5 py-3 pr-28 text-[13.5px] text-zinc-100 placeholder:text-zinc-700 focus:outline-none"
            disabled={props.busy}
          />
          <button
            type="button"
            onClick={send}
            disabled={props.busy || (!text.trim() && pendingFiles.length === 0)}
            className="absolute bottom-2 right-2 flex items-center gap-1.5 rounded-sm border border-[var(--hairline-strong)] bg-[var(--surface-2)] px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.14em] text-zinc-200 hover:border-[var(--accent)] hover:bg-[rgba(34,211,238,0.06)] hover:text-[var(--accent)] disabled:opacity-30 disabled:hover:border-[var(--hairline-strong)] disabled:hover:bg-[var(--surface-2)] disabled:hover:text-zinc-200"
          >
            发送
            <span className="text-zinc-400">↵</span>
          </button>
        </div>

        <div className="mt-2 flex items-center justify-between font-mono text-[10px] uppercase tracking-[0.14em] text-zinc-400">
          <span>支持 .sql / .csv / .json · 单文件 ≤ 25 MB</span>
          <span>shift + ↵ 换行</span>
        </div>

        {error && (
          <div className="bubble-in mt-2 flex items-center gap-2 rounded-sm border border-red-900/40 bg-red-950/20 px-3 py-1.5 text-[11.5px] text-red-300">
            <span className="pip pip-err" />
            <span>{error}</span>
          </div>
        )}
      </div>
    </div>
  );
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}
