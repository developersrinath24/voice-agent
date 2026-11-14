import { forward, relay } from "@/lib/backend";

// FormData parsing needs the Node runtime; the edge runtime's File handling is
// not worth the constraints here.
export const runtime = "nodejs";
// A warm voice turn is ~3s, but the first one after a deploy can be ~6s, and the
// upload has to finish. Without this Vercel would cut the function off early.
export const maxDuration = 60;

export async function POST(request: Request) {
  const incoming = await request.formData();
  const file = incoming.get("file");

  if (!(file instanceof File)) {
    return Response.json({ detail: "No audio file in the request." }, { status: 400 });
  }

  // Rebuild the form rather than forwarding it: the backend wants exactly one
  // file field plus an optional session id, and this keeps it explicit.
  const form = new FormData();
  form.append("file", file, file.name || "question.webm");

  const sessionId = incoming.get("session_id");
  if (typeof sessionId === "string" && sessionId.length > 0) {
    form.append("session_id", sessionId);
  }

  return relay(await forward("/voice/turn", { method: "POST", body: form }));
}
