"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import TurnList from "@/components/TurnList";
import { Recorder } from "@/lib/recorder";
import type { ChatTurn, Turn, VoiceTurn } from "@/lib/types";

const MAX_SECONDS = 60;

const EXAMPLES = [
  "What time do you close on a Tuesday?",
  "How long does a repeat prescription take?",
  "Can I bring my dog to the appointment?",
];

type Status = "idle" | "recording" | "working";
type Backend = "checking" | "online" | "offline";

function detailOf(payload: unknown, status: number): string {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return `The server returned ${status}.`;
}

export default function VoiceConsole() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [status, setStatus] = useState<Status>("idle");
  const [seconds, setSeconds] = useState(0);
  const [stage, setStage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [audioSrc, setAudioSrc] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [backend, setBackend] = useState<Backend>("checking");

  const recorderRef = useRef<Recorder | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const playAnswer = useCallback((base64: string, mime: string) => {
    const bytes = Uint8Array.from(atob(base64), (character) => character.charCodeAt(0));
    const url = URL.createObjectURL(new Blob([bytes], { type: mime }));
    setAudioSrc((previous) => {
      if (previous) URL.revokeObjectURL(previous);
      return url;
    });
  }, []);

  const sendAudio = useCallback(
    async (blob: Blob) => {
      const form = new FormData();
      form.append("file", blob, `question.${Recorder.extensionFor(blob.type)}`);
      if (sessionId) form.append("session_id", sessionId);

      setStage("Transcribing and answering…");
      const response = await fetch("/api/voice", { method: "POST", body: form });
      const payload: unknown = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(detailOf(payload, response.status));

      const turn = payload as VoiceTurn;
      setSessionId(turn.session_id);
      setTurns((current) => [
        ...current,
        { id: crypto.randomUUID(), role: "user", text: turn.transcript },
        {
          id: crypto.randomUUID(),
          role: "assistant",
          text: turn.response,
          sources: turn.sources,
          grounded: turn.grounded,
          timings: turn.timings_ms,
        },
      ]);
      playAnswer(turn.audio_base64, turn.audio_mime);
    },
    [sessionId, playAnswer],
  );

  const stopAndSend = useCallback(async () => {
    const recorder = recorderRef.current;
    if (!recorder) return;

    recorderRef.current = null;
    setStatus("working");
    setError(null);

    try {
      await sendAudio(await recorder.stop());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Something went wrong.");
    } finally {
      setStatus("idle");
      setStage("");
      setSeconds(0);
    }
  }, [sendAudio]);

  const startRecording = useCallback(async () => {
    setError(null);
    try {
      const recorder = new Recorder();
      await recorder.start();
      recorderRef.current = recorder;
      setSeconds(0);
      setStatus("recording");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The microphone could not be opened.");
    }
  }, []);

  const sendText = useCallback(
    async (message: string) => {
      const trimmed = message.trim();
      if (!trimmed || status !== "idle") return;

      setDraft("");
      setError(null);
      setStatus("working");
      setStage("Thinking…");

      try {
        const response = await fetch("/api/chat", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ message: trimmed, session_id: sessionId }),
        });
        const payload: unknown = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(detailOf(payload, response.status));

        const turn = payload as ChatTurn;
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
        setError(caught instanceof Error ? caught.message : "Something went wrong.");
      } finally {
        setStatus("idle");
        setStage("");
      }
    },
    [sessionId, status],
  );

  // Recording clock, and a hard stop so a forgotten microphone cannot upload a
  // ten-minute file.
  useEffect(() => {
    if (status !== "recording") return;
    const id = window.setInterval(() => setSeconds((value) => value + 1), 1000);
    return () => window.clearInterval(id);
  }, [status]);

  useEffect(() => {
    if (status === "recording" && seconds >= MAX_SECONDS) void stopAndSend();
  }, [seconds, status, stopAndSend]);

  useEffect(() => () => recorderRef.current?.cancel(), []);

  useEffect(() => {
    const element = scrollRef.current;
    if (element) element.scrollTop = element.scrollHeight;
  }, [turns, stage]);

  useEffect(() => {
    if (!audioSrc) return;
    // Mobile browsers may refuse autoplay; the player controls stay available.
    void audioRef.current?.play().catch(() => undefined);
  }, [audioSrc]);

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

  const recording = status === "recording";
  const busy = status === "working";

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div
        ref={scrollRef}
        className="min-h-0 flex-1 overflow-y-auto rounded-2xl bg-white shadow-sm ring-1 ring-slate-200"
      >
        {turns.length === 0 ? (
          <div className="flex h-full flex-col justify-center gap-5 px-5 py-8 text-center">
            <div>
              <p className="text-base font-medium text-slate-800">Ask about the practice</p>
              <p className="mt-1 text-sm text-slate-500">
                Tap the microphone and speak, or start with an example.
              </p>
            </div>
            <ul className="flex flex-wrap justify-center gap-2">
              {EXAMPLES.map((example) => (
                <li key={example}>
                  <button
                    type="button"
                    onClick={() => void sendText(example)}
                    className="rounded-full bg-slate-50 px-3 py-1.5 text-sm text-slate-700 ring-1 ring-slate-200 transition hover:bg-slate-100"
                  >
                    {example}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <TurnList turns={turns} />
        )}
      </div>

      <div className="min-h-6 text-sm">
        {recording && (
          <p className="text-center text-red-600">
            Recording {seconds}s of {MAX_SECONDS}s — tap the square to send
          </p>
        )}
        {busy && <p className="text-center text-slate-500">{stage || "Working…"}</p>}
        {error && (
          <p
            role="alert"
            className="rounded-lg bg-red-50 px-3 py-2 text-center text-red-700 ring-1 ring-red-200"
          >
            {error}
          </p>
        )}
      </div>

      {audioSrc && <audio ref={audioRef} src={audioSrc} controls className="w-full" />}

      <form
        className="flex items-end gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          void sendText(draft);
        }}
      >
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Or type your question…"
          disabled={busy || recording}
          aria-label="Type your question"
          className="h-12 flex-1 rounded-full bg-white px-4 text-[15px] ring-1 ring-slate-200 placeholder:text-slate-400 disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={busy || recording || draft.trim().length === 0}
          className="h-12 rounded-full bg-slate-900 px-4 text-sm font-medium text-white transition hover:bg-slate-700 disabled:opacity-40"
        >
          Send
        </button>
        <button
          type="button"
          onClick={recording ? () => void stopAndSend() : () => void startRecording()}
          disabled={busy}
          aria-label={recording ? "Stop recording and send" : "Start recording"}
          className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full text-white transition disabled:opacity-40 ${
            recording
              ? "bg-red-600 ring-4 ring-red-100 hover:bg-red-700"
              : "bg-teal-600 ring-4 ring-teal-50 hover:bg-teal-700"
          }`}
        >
          {recording ? <StopIcon /> : <MicIcon />}
        </button>
      </form>

      <p className="text-center text-[11px] text-slate-400">
        {backend === "offline"
          ? "Backend unreachable — check that the API is running."
          : backend === "checking"
            ? "Checking backend…"
            : "Backend connected"}
      </p>
    </div>
  );
}

function MicIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-5 w-5"
      aria-hidden="true"
    >
      <path d="M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3Z" />
      <path d="M19 11a7 7 0 0 1-14 0" />
      <path d="M12 18v3" />
    </svg>
  );
}

function StopIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4" aria-hidden="true">
      <rect x="6" y="6" width="12" height="12" rx="2" />
    </svg>
  );
}
