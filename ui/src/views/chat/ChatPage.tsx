import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  createSession,
  getSession,
  saveSession,
  cancelSession,
  submitTurn,
  type ChatMessage,
} from "@/api/chat";
import { useChatStream, type SseEvent } from "@/api/chatStream";
import { translateError } from "@/api/errorMessages";
import { ApiError } from "@/api/client";
import { ConversationPane, type ChatTurnView } from "./ConversationPane";
import { StagingGraphPane } from "./StagingGraphPane";
import type { ToolCall } from "./ToolCallPill";
import type { AssistantMessage } from "./MessageBubble";

const STORAGE_KEY = "onto.chat.session_id";

function reconstructTurns(messages: ChatMessage[]): ChatTurnView[] {
  const result: ChatTurnView[] = [];
  let current: ChatTurnView | null = null;
  for (const m of messages) {
    if (m.role === "user") {
      if (current) result.push(current);
      current = {
        user: {
          text: (m.content.text as string) ?? "",
          fileNames: ((m.content.upload_ids as string[]) ?? []).map((s) => s.slice(0, 8)),
        },
        assistant: null,
      };
    } else if (m.role === "assistant" && current) {
      current.assistant = { text: (m.content.text as string) ?? "", toolCalls: [] };
    }
  }
  if (current) result.push(current);
  return result;
}

function updateLast(turns: ChatTurnView[], assistant: AssistantMessage): ChatTurnView[] {
  if (turns.length === 0) return turns;
  const last = turns[turns.length - 1];
  return [...turns.slice(0, -1), { ...last, assistant }];
}

export default function ChatPage() {
  const qc = useQueryClient();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [turns, setTurns] = useState<ChatTurnView[]>([]);
  const [turnId, setTurnId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const currentAssistantRef = useRef<AssistantMessage>({ text: "", toolCalls: [] });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        try {
          const session = await getSession(stored);
          if (cancelled) return;
          setSessionId(session.session_id);
          setTurns(reconstructTurns(session.messages));
          return;
        } catch {
          localStorage.removeItem(STORAGE_KEY);
        }
      }
      try {
        const r = await createSession();
        if (cancelled) return;
        localStorage.setItem(STORAGE_KEY, r.session_id);
        setSessionId(r.session_id);
      } catch (e) {
        const code = e instanceof ApiError ? e.code : undefined;
        setError(translateError(code));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const onSseEvent = useCallback(
    (e: SseEvent) => {
      if (e.type === "tool_call") {
        const call: ToolCall = {
          sequence: e.sequence,
          name: e.name,
          args: e.args,
          status: "running",
        };
        currentAssistantRef.current.toolCalls.push(call);
        setTurns((ts) => updateLast(ts, { ...currentAssistantRef.current }));
      } else if (e.type === "tool_result") {
        const c = currentAssistantRef.current.toolCalls.find((c) => c.sequence === e.sequence);
        if (c) {
          c.status = e.status === "ok" ? "ok" : "error";
          c.summary = e.summary;
          c.error = e.error ?? undefined;
        }
        setTurns((ts) => updateLast(ts, { ...currentAssistantRef.current }));
      } else if (e.type === "assistant_message") {
        currentAssistantRef.current.text = e.partial
          ? currentAssistantRef.current.text + e.content
          : e.content;
        setTurns((ts) => updateLast(ts, { ...currentAssistantRef.current }));
      } else if (e.type === "turn_complete") {
        qc.invalidateQueries({ queryKey: ["full", "staging"] });
        setBusy(false);
        setTurnId(null);
        currentAssistantRef.current = { text: "", toolCalls: [] };
      } else if (e.type === "turn_error") {
        setError(translateError(e.kind) + "：" + e.message);
        setBusy(false);
        setTurnId(null);
        currentAssistantRef.current = { text: "", toolCalls: [] };
      }
    },
    [qc],
  );

  useChatStream({
    sessionId: sessionId ?? "",
    turnId,
    onEvent: onSseEvent,
  });

  const onSubmit = useCallback(
    async (message: string, uploadIds: string[]) => {
      if (!sessionId) return;
      setError(null);
      setBusy(true);
      setTurns((ts) => [
        ...ts,
        {
          user: { text: message, fileNames: uploadIds.map((id) => id.slice(0, 8)) },
          assistant: { text: "", toolCalls: [] },
        },
      ]);
      currentAssistantRef.current = { text: "", toolCalls: [] };
      try {
        const r = await submitTurn(sessionId, message, uploadIds);
        setTurnId(r.turn_id);
      } catch (e) {
        setBusy(false);
        const code = e instanceof ApiError ? e.code : undefined;
        setError(translateError(code));
      }
    },
    [sessionId],
  );

  const onSave = useCallback(async () => {
    if (!sessionId) return;
    const r = await saveSession(sessionId);
    if (r.ok) {
      localStorage.removeItem(STORAGE_KEY);
      window.location.href = "/graph/staging";
    } else {
      const body = (await r.json().catch(() => ({}))) as { detail?: { code?: string } };
      setError(translateError(body.detail?.code));
    }
  }, [sessionId]);

  const onCancel = useCallback(async () => {
    if (!sessionId) return;
    const r = await cancelSession(sessionId);
    if (r.ok) {
      localStorage.removeItem(STORAGE_KEY);
      window.location.href = "/graph/staging";
    } else {
      const body = (await r.json().catch(() => ({}))) as { detail?: { code?: string } };
      setError(translateError(body.detail?.code));
    }
  }, [sessionId]);

  if (!sessionId) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-center">
          <span className="pip pip-warn pulse-soft" />
          <div className="mt-3 font-display text-[16px] text-zinc-300">正在初始化会话</div>
          {error && (
            <div className="mt-2 font-mono text-[11px] uppercase tracking-[0.14em] text-red-400">
              {error}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="relative grid h-screen grid-cols-[1.3fr_1fr]">
      <div className="border-r hairline overflow-hidden">
        <ConversationPane
          sessionId={sessionId}
          turns={turns}
          busy={busy}
          onSubmit={onSubmit}
          onSave={onSave}
          onCancel={onCancel}
        />
      </div>
      <div className="overflow-hidden">
        <StagingGraphPane turnInFlight={busy} />
      </div>
      {error && (
        <div role="alert" className="bubble-in absolute bottom-4 right-4 max-w-md rounded-sm border border-red-900/50 bg-red-950/40 px-3.5 py-2.5 backdrop-blur">
          <div className="flex items-start gap-2.5">
            <span className="pip pip-err mt-1.5" />
            <div className="flex-1 text-[12.5px] leading-relaxed text-red-200">{error}</div>
            <button
              type="button"
              className="font-mono text-[10px] uppercase tracking-[0.14em] text-red-400 hover:text-red-200"
              onClick={() => setError(null)}
            >
              关闭
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
