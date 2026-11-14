/**
 * Server-side helpers for talking to the FastAPI backend.
 *
 * The browser never calls the backend directly. Every request goes through a
 * Next.js route handler, which adds the shared secret. That keeps BACKEND_API_KEY
 * out of the client bundle — a `NEXT_PUBLIC_` variable would ship it to anyone
 * who opens devtools — and it means the browser only ever talks to its own
 * origin, so no CORS configuration is needed.
 */

export const API_BASE_URL = (process.env.API_BASE_URL ?? "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);

function headers(extra?: HeadersInit): Headers {
  const merged = new Headers(extra);
  const key = process.env.BACKEND_API_KEY;
  if (key) merged.set("X-API-Key", key);
  return merged;
}

export async function forward(path: string, init: RequestInit = {}): Promise<Response> {
  try {
    return await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: headers(init.headers),
      cache: "no-store",
    });
  } catch {
    return Response.json(
      { detail: "Cannot reach the API. Is the FastAPI server running?" },
      { status: 502 },
    );
  }
}

/** Pass a backend response through unchanged, including its status code. */
export async function relay(response: Response): Promise<Response> {
  return new Response(await response.text(), {
    status: response.status,
    headers: {
      "content-type": response.headers.get("content-type") ?? "application/json",
    },
  });
}
