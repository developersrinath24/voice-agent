"use client";

import { ConversationProvider, useConversation } from "@elevenlabs/react";
import { useCallback, useEffect, useRef, useState } from "react";

import TurnList from "@/components/TurnList";
import { detailOf } from "@/lib/http";
import type { Turn, VoiceSession } from "@/lib/types";

type Phase = "idle" | "starting" | "live" | "ended";

type Props = {
  onOpenSource: (source: string, section: string) => void;
  onBackToChat: () => void;
};

function clock(total: number): string {
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

export default function CallPanel(props: Props) {
  // The SDK keeps its connection state in a provider; the hooks only read it.
  // Keeping the provider here means switching to the text tab unmounts the call
  // and hangs up, rather than leaving a paid call running in the background.
  return (
    <ConversationProvider>
      <CallExperience {...props} />
    </ConversationProvider>
  );
}

function CallExperience({ onOpenSource, onBackToChat }: Props) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [session, setSession] = useState<VoiceSession | null>(null);
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null);

  const liveRef = useRef(false);
  const deadlineRef = useRef<number | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const { startSession, endSession, status, isSpeaking, isListening, isMuted, setMuted } =
    useConversation({
      onConnect: () => {
        setPhase("live");
      },
      onDisconnect: () => {
        setPhase("ended");
      },
      onError: (message) => {
        setError(message || "The call could not continue.");
      },
      onMessage: ({ message, source }) => {
        const text = message.trim();
        if (!text) return;
        setTurns((current) => [
          ...current,
          {
            id: crypto.randomUUID(),
            role: source === "user" ? "user" : "assistant",
            text,
          },
        ]);
      },
    });

  liveRef.current = phase === "starting" || phase === "live";

  // Unmounting the panel must hang up: a forgotten tab should not keep spending
  // credits, and the browser might otherwise hold the microphone open.
  useEffect(() => {
    return () => {
      if (liveRef.current) endSession();
    };
  }, [endSession]);

  const start = useCallback(async () => {
    setError(null);
    setTurns([]);
    setPhase("starting");

    try {
      // Ask for the microphone first. If it is blocked, the visitor gets a
      // browser-level explanation without the backend having spent a call.
      let stream: MediaStream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      } catch {
        throw new Error(
          "The microphone is blocked. Allow microphone access for this site, then try again.",
        );
      }
      stream.getTracks().forEach((track) => track.stop());

      const response = await fetch("/api/voice-session", { cache: "no-store" });
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok) throw new Error(detailOf(payload, response.status));

      const issued = payload as VoiceSession;
      setSession(issued);
      deadlineRef.current = Date.now() + issued.max_seconds * 1000;
      setSecondsLeft(issued.max_seconds);

      startSession({ signedUrl: issued.signed_url, connectionType: "websocket" });
    } catch (caught) {
      deadlineRef.current = null;
      setPhase("idle");
      setError(caught instanceof Error ? caught.message : "Could not start the call.");
    }
  }, [startSession]);

  const hangUp = useCallback(() => {
    endSession();
    setPhase("ended");
  }, [endSession]);

  // The cap is enforced here as well as in the prompt: an open line costs money
  // for as long as it lasts, and a visitor may simply walk away.
  useEffect(() => {
    if (phase !== "live") return;
    const tick = () => {
      const deadline = deadlineRef.current;
      if (deadline === null) return;
      const left = Math.max(0, Math.round((deadline - Date.now()) / 1000));
      setSecondsLeft(left);
      if (left === 0) hangUp();
    };
    tick();
    const timer = setInterval(tick, 1000);
    return () => clearInterval(timer);
  }, [phase, hangUp]);

  useEffect(() => {
    const element = scrollRef.current;
    if (element) element.scrollTop = element.scrollHeight;
  }, [turns]);

  const live = phase === "live";
  const starting = phase === "starting";

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2">
      <div className="flex items-center justify-between gap-2 px-1">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">Call reception</h2>
          <p className="text-[11px] text-slate-500">
            {live || starting
              ? `Live call · up to ${clock(session?.max_seconds ?? 90)}`
              : "Spoken answers from the same practice information"}
          </p>
        </div>
        <button
          type="button"
          onClick={onBackToChat}
          className="rounded-full px-2 py-1 text-[11px] font-medium text-slate-500 transition hover:bg-slate-100 hover:text-slate-800"
        >
          Back to text
        </button>
      </div>

      <div
        ref={scrollRef}
        className="min-h-0 flex-1 overflow-y-auto rounded-2xl bg-white shadow-sm ring-1 ring-slate-200"
        aria-live="polite"
      >
        {turns.length === 0 ? (
          <div className="flex h-full flex-col justify-center gap-4 px-5 py-8">
            <div>
              <p className="text-base font-medium text-slate-800">
                {live ? "You are through to reception" : "Talk to reception"}
              </p>
              <p className="mt-1 text-sm leading-relaxed text-slate-500">
                Press start and just talk — no push-to-talk. Ask about opening hours,
                prescriptions, appointments or home visits.
              </p>
            </div>

            <ul className="flex flex-col gap-1.5 text-[12px] leading-relaxed text-slate-500">
              <li>· This is a demo: the receptionist is an AI, and the practice is fictional.</li>
              <li>· Your speech is sent to ElevenLabs to transcribe and answer.</li>
              <li>· Calls are capped at {clock(session?.max_seconds ?? 90)}.</li>
              {session && (
                <li>
                  · {session.remaining_calls} call{session.remaining_calls === 1 ? "" : "s"} left in
                  today&apos;s allowance.
                </li>
              )}
            </ul>
          </div>
        ) : (
          <TurnList turns={turns} onOpenSource={onOpenSource} assistantLabel="Reception" />
        )}
      </div>

      <div className="min-h-5 px-1 text-xs">
        {starting && <p className="text-slate-500">Connecting the call…</p>}
        {live && (
          <p className="flex items-center gap-2 text-slate-500">
            <span
              className={`h-2 w-2 rounded-full ${isSpeaking ? "bg-teal-500" : "bg-amber-400"}`}
            />
            {isSpeaking ? "Reception is speaking…" : isListening ? "Listening…" : "Connected"}
            {secondsLeft !== null && (
              <span className="ml-auto tabular-nums text-slate-400">
                {clock(secondsLeft)} left
              </span>
            )}
          </p>
        )}
        {error && (
          <p
            role="alert"
            className="rounded-lg bg-red-50 px-3 py-2 text-red-700 ring-1 ring-red-200"
          >
            {error}
          </p>
        )}
      </div>

      <div className="flex items-center gap-2">
        {live || starting ? (
          <>
            <button
              type="button"
              onClick={() => setMuted(!isMuted)}
              disabled={!live}
              className="h-12 rounded-full bg-white px-4 text-sm font-medium text-slate-700 ring-1 ring-slate-200 transition hover:bg-slate-50 disabled:opacity-40"
            >
              {isMuted ? "Unmute" : "Mute"}
            </button>
            <button
              type="button"
              onClick={hangUp}
              className="h-12 flex-1 rounded-full bg-red-600 px-5 text-sm font-medium text-white transition hover:bg-red-700"
            >
              End call
            </button>
          </>
        ) : (
          <button
            type="button"
            onClick={() => void start()}
            className="h-12 flex-1 rounded-full bg-teal-600 px-5 text-sm font-medium text-white transition hover:bg-teal-700 disabled:opacity-40"
          >
            {phase === "ended" ? "Start another call" : "Start call"}
          </button>
        )}
      </div>

      {status === "connected" && !live && (
        <p className="px-1 text-[11px] text-slate-400">Connected, finishing the call…</p>
      )}
    </div>
  );
}
