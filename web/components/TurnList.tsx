import type { Turn } from "@/lib/types";

function formatTimings(timings: Record<string, number>): string {
  const seconds = (ms?: number) => (typeof ms === "number" ? `${(ms / 1000).toFixed(1)}s` : null);
  return [
    seconds(timings.transcribe) && `heard in ${seconds(timings.transcribe)}`,
    seconds(timings.answer) && `answered in ${seconds(timings.answer)}`,
    seconds(timings.speak) && `spoken in ${seconds(timings.speak)}`,
  ]
    .filter(Boolean)
    .join(" · ");
}

function Sources({ turn }: { turn: Turn }) {
  if (!turn.sources?.length) return null;

  return (
    <ul className="mt-2 flex flex-wrap gap-1.5">
      {turn.sources.map((source) => (
        <li
          key={`${source.source}-${source.section}`}
          className="rounded-full bg-white px-2 py-0.5 text-[11px] text-slate-600 ring-1 ring-slate-200"
          title={`${source.source} · cosine score ${source.score.toFixed(3)}`}
        >
          {source.section}
          <span className="ml-1 text-slate-400">{source.score.toFixed(2)}</span>
        </li>
      ))}
    </ul>
  );
}

export default function TurnList({ turns }: { turns: Turn[] }) {
  return (
    <ol className="flex flex-col gap-5 px-4 py-5 sm:px-6" aria-live="polite">
      {turns.map((turn) => {
        const isUser = turn.role === "user";
        return (
          <li key={turn.id} className={`flex flex-col gap-1 ${isUser ? "items-end" : "items-start"}`}>
            <span className="px-1 text-[11px] font-medium uppercase tracking-wide text-slate-400">
              {isUser ? "You" : "Reception"}
            </span>

            <div
              className={
                isUser
                  ? "max-w-[85%] rounded-2xl rounded-br-sm bg-teal-600 px-4 py-2 text-[15px] leading-relaxed text-white"
                  : "max-w-[90%] rounded-2xl rounded-bl-sm bg-slate-100 px-4 py-3 text-[15px] leading-relaxed text-slate-900"
              }
            >
              {turn.text}
            </div>

            {!isUser && turn.grounded === false && (
              <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700 ring-1 ring-amber-200">
                not in the practice information
              </span>
            )}

            {!isUser && <Sources turn={turn} />}

            {!isUser && turn.timings && formatTimings(turn.timings) && (
              <span className="px-1 text-[11px] text-slate-400">
                {formatTimings(turn.timings)}
              </span>
            )}
          </li>
        );
      })}
    </ol>
  );
}
