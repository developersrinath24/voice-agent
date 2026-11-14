import { forward, relay } from "@/lib/backend";

export const runtime = "nodejs";
export const maxDuration = 60;

export async function POST(request: Request) {
  return relay(
    await forward("/chat", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: await request.text(),
    }),
  );
}
