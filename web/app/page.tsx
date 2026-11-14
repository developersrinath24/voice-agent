import Workspace from "@/components/Workspace";

export default function Home() {
  return (
    <main className="mx-auto flex h-dvh w-full max-w-[1600px] flex-col gap-3 overflow-hidden p-3 sm:p-5">
      <Workspace />

      <footer className="text-center text-[11px] leading-relaxed text-slate-500">
        Answers are generated only from the practice documents shown here. For chest pain, difficulty
        breathing or severe bleeding, call{" "}
        <span className="font-medium text-slate-700">999</span>.
      </footer>
    </main>
  );
}
