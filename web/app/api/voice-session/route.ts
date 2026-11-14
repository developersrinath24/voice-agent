import { forward, relay } from "@/lib/backend";

export const runtime = "nodejs";

export async function GET() {
  return relay(await forward("/voice/session"));
}
