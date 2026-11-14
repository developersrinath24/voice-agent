import { forward, relay } from "@/lib/backend";

export const runtime = "nodejs";

/** The knowledge base, proxied so the browser never needs the API key. */
export async function GET() {
  return relay(await forward("/documents"));
}
