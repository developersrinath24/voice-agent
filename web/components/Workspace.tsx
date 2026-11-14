"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";

import ChatPanel from "@/components/ChatPanel";
import DocumentNav from "@/components/DocumentNav";
import DocumentViewer from "@/components/DocumentViewer";
import { detailOf } from "@/lib/http";
import type { ClinicDocument } from "@/lib/types";

// The ElevenLabs SDK touches browser audio APIs, so it is loaded only when the
// visitor asks for a call, never during the initial page render. Text chat —
// the default — does not pay for it at all.
const CallPanel = dynamic(() => import("@/components/CallPanel"), {
  ssr: false,
  loading: () => (
    <div className="flex min-h-0 flex-1 items-center justify-center rounded-2xl bg-white p-6 text-sm text-slate-500 shadow-sm ring-1 ring-slate-200">
      Preparing the call…
    </div>
  ),
});

type Tab = "documents" | "assistant";
type Mode = "chat" | "call";

/** A request to scroll to one section. `nonce` lets the same section re-trigger. */
type Jump = { section: string; nonce: number };

export default function Workspace() {
  const [documents, setDocuments] = useState<ClinicDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [documentsError, setDocumentsError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [jump, setJump] = useState<Jump | null>(null);
  const [tab, setTab] = useState<Tab>("assistant");
  const [mode, setMode] = useState<Mode>("chat");

  const loadDocuments = useCallback(async () => {
    setLoading(true);
    setDocumentsError(null);
    try {
      const response = await fetch("/api/documents", { cache: "no-store" });
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok) throw new Error(detailOf(payload, response.status));
      setDocuments(payload as ClinicDocument[]);
    } catch (caught) {
      setDocumentsError(
        caught instanceof Error ? caught.message : "Could not load the knowledge base.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDocuments();
  }, [loadDocuments]);

  const active = useMemo(
    () => documents.find((document) => document.source === selected) ?? documents[0] ?? null,
    [documents, selected],
  );

  const passages = useMemo(
    () => documents.reduce((total, document) => total + document.chunk_count, 0),
    [documents],
  );

  // A citation in the transcript opens the section it came from. That is the
  // whole verification loop: claim on the right, source on the left.
  const openSource = useCallback((source: string, section: string) => {
    setSelected(source);
    setJump({ section, nonce: Date.now() });
    setTab("documents");
  }, []);

  return (
    <>
      <header className="flex flex-wrap items-end justify-between gap-x-4 gap-y-2">
        <div className="min-w-0">
          <h1 className="text-lg font-semibold tracking-tight text-slate-900">
            Bramble Court Surgery
          </h1>
          <p className="text-sm text-slate-500">
            A fictional practice. Read the source, ask a question, check the answer against it.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <p className="hidden text-right text-[11px] leading-tight text-slate-500 sm:block">
            {loading
              ? "Loading knowledge base…"
              : `${documents.length} documents · ${passages} indexed passages`}
          </p>
          <div className="flex rounded-full bg-white p-1 text-xs font-medium ring-1 ring-slate-200 lg:hidden">
            <TabButton active={tab === "documents"} onClick={() => setTab("documents")}>
              Documents
            </TabButton>
            <TabButton active={tab === "assistant"} onClick={() => setTab("assistant")}>
              Assistant
            </TabButton>
          </div>
        </div>
      </header>

      <div className="flex min-h-0 flex-1 flex-col gap-3 lg:flex-row">
        <section
          aria-label="Knowledge base"
          className={`${tab === "documents" ? "flex" : "hidden"} min-h-0 flex-col gap-2 lg:flex lg:w-60 lg:shrink-0`}
        >
          {documentsError ? (
            <div className="rounded-2xl bg-white p-4 text-sm shadow-sm ring-1 ring-slate-200">
              <p className="font-medium text-slate-800">The knowledge base did not load</p>
              <p className="mt-1 text-slate-500">{documentsError}</p>
              <button
                type="button"
                onClick={() => void loadDocuments()}
                className="mt-3 rounded-full bg-slate-900 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-slate-700"
              >
                Try again
              </button>
            </div>
          ) : (
            <DocumentNav
              documents={documents}
              loading={loading}
              activeSource={active?.source ?? null}
              onSelect={(source) => {
                setSelected(source);
                setJump(null);
              }}
            />
          )}
        </section>

        <section
          className={`${tab === "documents" ? "flex" : "hidden"} min-h-0 flex-1 flex-col lg:flex`}
        >
          <DocumentViewer
            document={active}
            loading={loading}
            jump={jump}
            onRetry={() => void loadDocuments()}
          />
        </section>

        <section
          className={`${tab === "assistant" ? "flex" : "hidden"} min-h-0 flex-1 flex-col lg:flex lg:w-[420px] lg:shrink-0`}
        >
          {mode === "chat" ? (
            <ChatPanel onOpenSource={openSource} onCall={() => setMode("call")} />
          ) : (
            <CallPanel onOpenSource={openSource} onBackToChat={() => setMode("chat")} />
          )}
        </section>
      </div>
    </>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`rounded-full px-3 py-1.5 transition ${
        active ? "bg-slate-900 text-white" : "text-slate-600 hover:text-slate-900"
      }`}
    >
      {children}
    </button>
  );
}
