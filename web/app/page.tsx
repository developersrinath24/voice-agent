import VoiceConsole from "@/components/VoiceConsole";

export default function Home() {
  return (
    <main className="mx-auto flex h-dvh w-full max-w-2xl flex-col gap-4 px-4 py-5 sm:py-8">
      <header className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Bramble Court Surgery</h1>
          <p className="text-sm text-slate-500">Voice assistant · fictional practice</p>
        </div>
        <span className="hidden rounded-full bg-white px-3 py-1 text-xs text-slate-500 ring-1 ring-slate-200 sm:block">
          Ask about hours, prescriptions, appointments
        </span>
      </header>

      <VoiceConsole />

      <footer className="text-center text-xs leading-relaxed text-slate-500">
        Answers come only from the practice information. For chest pain, difficulty breathing or
        severe bleeding, call <span className="font-medium text-slate-700">999</span>.
      </footer>
    </main>
  );
}
