"use client";

import type { ClinicDocument } from "@/lib/types";

type Props = {
  documents: ClinicDocument[];
  loading: boolean;
  activeSource: string | null;
  onSelect: (source: string) => void;
};

/** Vertical list on desktop, a scrollable strip above the page on mobile. */
export default function DocumentNav({ documents, loading, activeSource, onSelect }: Props) {
  if (loading) {
    return (
      <div className="flex gap-2 lg:flex-col" aria-hidden="true">
        {[0, 1, 2, 3, 4].map((index) => (
          <div
            key={index}
            className="h-14 w-40 shrink-0 animate-pulse rounded-xl bg-white ring-1 ring-slate-200 lg:w-full"
          />
        ))}
      </div>
    );
  }

  return (
    <nav
      aria-label="Documents"
      className="flex gap-2 overflow-x-auto pb-1 lg:min-h-0 lg:flex-1 lg:flex-col lg:overflow-x-hidden lg:overflow-y-auto lg:pb-0"
    >
      {documents.map((document) => {
        const active = document.source === activeSource;
        return (
          <button
            key={document.source}
            type="button"
            onClick={() => onSelect(document.source)}
            aria-current={active ? "true" : undefined}
            className={`shrink-0 rounded-xl px-3 py-2 text-left transition lg:w-full ${
              active
                ? "bg-slate-900 text-white shadow-sm"
                : "bg-white text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50"
            }`}
          >
            <span className="block whitespace-nowrap text-[13px] font-medium lg:whitespace-normal">
              {document.title}
            </span>
            <span
              className={`mt-0.5 block whitespace-nowrap text-[11px] lg:whitespace-normal ${
                active ? "text-slate-300" : "text-slate-500"
              }`}
            >
              {document.category} · {document.chunk_count} passages
            </span>
          </button>
        );
      })}
    </nav>
  );
}
