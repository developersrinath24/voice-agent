import { forward, relay } from "@/lib/backend";

export const runtime = "nodejs";

/**
 * Lets the UI say "backend offline" honestly instead of showing a generic
 * failure on the first question. Proxied so the browser never needs the key.
 */
export async function GET() {
  return relay(await forward("/health"));
}
