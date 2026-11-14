"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { ClinicDocument } from "@/lib/types";

type Jump = { section: string; nonce: number };

type Props = {
  document: ClinicDocument | null;
  loading: boolean;
  jump: Jump | null;
  onRetry: () => void;
};

/**
 * The reading pane. Renders the same section text that was embedded, so the
 * answer on the right can be checked against the source on the left.
 */
export default function DocumentViewer({ document, loading, jump, onRetry }: Props) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const [flash, setFlash] = useState<string | null>(null);

  // A different document starts at the top.
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: 0 });
  }, [document?.source]);

  // A citation scrolls to its section and highlights it briefly. Declared after
  // the reset above so the jump wins when both fire in the same commit.
  useEffect(() => {
    const container = scrollRef.current;
    if (!container || !jump) return;

    const target = Array.from(container.querySelectorAll<HTMLElement>("[data-section]")).find(
      (element) => element.dataset.section === jump.section,
    );
    if (!target) return;

    target.scrollIntoView({ behavior: "smooth", block: "start" });
    setFlash(jump.section);
    const timer = window.setTimeout(() => setFlash(null), 2400);
    return () => window.clearTimeout(timer);
  }, [jump, document?.source]);

  if (loading) {
    return (
      <div className="flex min-h-0 flex-1 flex-col gap-3 rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
        <div className="h-4 w-40 animate-pulse rounded bg-slate-100" />
        <div className="h-3 w-64 animate-pulse rounded bg-slate-100" />
        <div className="mt-2 h-24 animate-pulse rounded-xl bg-slate-50" />
        <div className="h-24 animate-pulse rounded-xl bg-slate-50" />
      </div>
    );
  }

  if (!document) {
    return (
      <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-3 rounded-2xl bg-white p-8 text-center shadow-sm ring-1 ring-slate-200">
        <p className="text-sm font-medium text-slate-800">No documents to show</p>
        <p className="max-w-sm text-sm text-slate-500">
          The API returned an empty knowledge base. Check that the markdown files are on the server.
        </p>
        <button
          type="button"
          onClick={onRetry}
          className="rounded-full bg-slate-900 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-slate-700"
        >
          Reload
        </button>
      </div>
    );
  }

  return (
    <article className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-slate-200">
      <header className="border-b border-slate-100 px-5 py-4">
        <p className="flex flex-wrap items-center gap-x-2 text-[11px] uppercase tracking-wide text-slate-400">
          <span>{document.category}</span>
          <span aria-hidden="true">·</span>
          <span className="normal-case tracking-normal">knowledge_base/{document.source}</span>
        </p>
        <h2 className="mt-1 text-lg font-semibold tracking-tight text-slate-900">
          {document.title}
        </h2>
        <p className="mt-0.5 text-xs text-slate-500">
          {document.sections.length} sections · indexed as {document.chunk_count} passages
          {document.last_reviewed ? ` · last reviewed ${document.last_reviewed}` : ""}
        </p>
      </header>

      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-3 py-3 sm:px-4">
        {document.sections.map((section) => (
          <section
            key={section.section}
            data-section={section.section}
            className={`scroll-mt-3 rounded-xl px-3 py-3 transition-colors duration-500 ${
              flash === section.section
                ? "bg-teal-50 ring-1 ring-teal-200"
                : "ring-1 ring-transparent"
            }`}
          >
            <h3 className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              {section.section}
            </h3>
            <div className="prose prose-slate mt-1 max-w-none break-words text-[15px] leading-relaxed prose-headings:font-semibold prose-p:my-2 prose-a:text-teal-700 prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5 prose-table:my-3 prose-table:text-[13px] prose-th:bg-slate-50 prose-th:px-2 prose-th:py-1 prose-td:px-2 prose-td:py-1 prose-strong:text-slate-900">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{section.content}</ReactMarkdown>
            </div>
          </section>
        ))}
      </div>
    </article>
  );
}
