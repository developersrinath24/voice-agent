"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import TurnList from "@/components/TurnList";
import { detailOf } from "@/lib/http";
import type { ChatTurn, Turn } from "@/lib/types";

const EXAMPLES = [
  "What time do you close on a Tuesday?",
  "How long does a repeat prescription take?",
  "Can I bring my dog to the appointment?",
];

type Status = "idle" | "working";
type Backend = "checking" | "online" | "offline";

type Props = {
  onOpenSource: (source: string, section: string) => void;
};

export default function ChatPanel({ onOpenSource }: Props) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [backend, setBackend] = useState<Backend>("checking");

  const scrollRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const busy = status === "working";

  const sendText = useCallback(
    async (message: string) => {
      const trimmed = message.trim();
      if (!trimmed || busy) return;

      setDraft("");
      setError(null);
      setStatus("working");

      try {
        const response = await fetch("/api/chat", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ message: trimmed, session_id: sessionId }),
        });
        const payload: unknown = await response.json().catch(() => null);
        if (!response.ok) throw new Error(detailOf(payload, response.status));

        const turn = payload as ChatTurn;
        setBackend("online");
        setSessionId(turn.session_id);
        setTurns((current) => [
          ...current,
          { id: crypto.randomUUID(), role: "user", text: trimmed },
          {
            id: crypto.randomUUID(),
            role: "assistant",
            text: turn.response,
            sources: turn.sources,
            grounded: turn.grounded,
          },
        ]);
      } catch (caught) {
        setBackend("offline");
        setError(caught instanceof Error ? caught.message : "Something went wrong.");
      } finally {
        setStatus("idle");
        inputRef.current?.focus();
      }
    },
    [busy, sessionId],
  );

  useEffect(() => {
    const element = scrollRef.current;
    if (element) element.scrollTop = element.scrollHeight;
  }, [turns, busy]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const response = await fetch("/api/health");
        if (!cancelled) setBackend(response.ok ? "online" : "offline");
      } catch {
        if (!cancelled) setBackend("offline");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2">
      <div className="flex items-center justify-between gap-2 px-1">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">Assistant</h2>
          <p className="text-[11px] text-slate-500">Answers only from the practice information</p>
        </div>
        <div className="flex items-center gap-2">
          {turns.length > 0 && (
            <button
              type="button"
              onClick={() => {
                setTurns([]);
                setSessionId(null);
                setError(null);
              }}
              className="rounded-full px-2 py-1 text-[11px] font-medium text-slate-500 transition hover:bg-slate-100 hover:text-slate-800"
            >
              New chat
            </button>
          )}
          <span
            title={
              backend === "online"
                ? "Connected to the API"
                : backend === "checking"
                  ? "Checking the API…"
                  : "API unreachable"
            }
            className={`h-2 w-2 rounded-full ${
              backend === "online"
                ? "bg-teal-500"
                : backend === "checking"
                  ? "bg-slate-300"
                  : "bg-red-500"
            }`}
          />
        </div>
      </div>

      <div
        ref={scrollRef}
        className="min-h-0 flex-1 overflow-y-auto rounded-2xl bg-white shadow-sm ring-1 ring-slate-200"
        aria-live="polite"
      >
        {turns.length === 0 ? (
          <div className="flex h-full flex-col justify-center gap-4 px-5 py-8">
            <div>
              <p className="text-base font-medium text-slate-800">Ask the practice</p>
              <p className="mt-1 text-sm leading-relaxed text-slate-500">
                Every answer cites the section it came from. Click a citation to read the passage
                beside it.
              </p>
            </div>
            <ul className="flex flex-col items-start gap-2">
              {EXAMPLES.map((example) => (
                <li key={example}>
                  <button
                    type="button"
                    onClick={() => void sendText(example)}
                    className="rounded-full bg-slate-50 px-3 py-1.5 text-left text-[13px] text-slate-700 ring-1 ring-slate-200 transition hover:bg-slate-100"
                  >
                    {example}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <TurnList turns={turns} onOpenSource={onOpenSource} />
        )}
      </div>

      <div className="min-h-5 px-1 text-xs">
        {busy && <p className="text-slate-500">Searching the practice information…</p>}
        {error && (
          <p
            role="alert"
            className="rounded-lg bg-red-50 px-3 py-2 text-red-700 ring-1 ring-red-200"
          >
            {error}
          </p>
        )}
      </div>

      <form
        className="flex items-center gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          void sendText(draft);
        }}
      >
        <input
          ref={inputRef}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Ask about hours, prescriptions, appointments…"
          disabled={busy}
          aria-label="Your question"
          className="h-12 min-w-0 flex-1 rounded-full bg-white px-4 text-[15px] ring-1 ring-slate-200 placeholder:text-slate-400 disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={busy || draft.trim().length === 0}
          className="h-12 rounded-full bg-teal-600 px-5 text-sm font-medium text-white transition hover:bg-teal-700 disabled:opacity-40"
        >
          Ask
        </button>
      </form>
    </div>
  );
}
