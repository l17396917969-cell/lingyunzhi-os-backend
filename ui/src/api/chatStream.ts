import { useEffect, useRef, useState } from "react";

export type SseEvent =
  | { type: "turn_start"; turn_id: string }
  | { type: "tool_call"; sequence: number; name: string; args: Record<string, unknown> }
  | {
      type: "tool_result";
      sequence: number;
      status: "ok" | "error";
      summary: string;
      error: { code?: string; message?: string } | null;
    }
  | { type: "assistant_message"; content: string; partial: boolean }
  | { type: "turn_complete"; tool_calls_made: number }
  | { type: "turn_error"; kind: string; message: string }
  | { type: "heartbeat" };

export interface UseChatStreamArgs {
  sessionId: string;
  turnId: string | null;
  onEvent: (e: SseEvent) => void;
}

const EVENT_TYPES = [
  "turn_start",
  "tool_call",
  "tool_result",
  "assistant_message",
  "turn_complete",
  "turn_error",
  "heartbeat",
] as const;

export function useChatStream({ sessionId, turnId, onEvent }: UseChatStreamArgs): { connected: boolean } {
  const [connected, setConnected] = useState(false);
  const cbRef = useRef(onEvent);
  cbRef.current = onEvent;
  useEffect(() => {
    if (!turnId || !sessionId) return;
    const es = new EventSource(`/chat/sessions/${sessionId}/stream?turn_id=${turnId}`, {
      withCredentials: true,
    });
    setConnected(true);
    const listeners: Record<string, EventListener> = {};
    for (const t of EVENT_TYPES) {
      listeners[t] = (ev) => {
        const data = (ev as MessageEvent).data;
        try {
          const payload = data ? (JSON.parse(data) as Record<string, unknown>) : {};
          cbRef.current({ type: t, ...payload } as SseEvent);
        } catch {
          // ignore malformed
        }
        if (t === "turn_complete" || t === "turn_error") {
          es.close();
          setConnected(false);
        }
      };
      es.addEventListener(t, listeners[t]);
    }
    es.onerror = () => {
      es.close();
      setConnected(false);
    };
    return () => {
      for (const t of EVENT_TYPES) es.removeEventListener(t, listeners[t]);
      es.close();
      setConnected(false);
    };
  }, [sessionId, turnId]);
  return { connected };
}
