/** FastAPI puts human-readable messages in `detail`; prefer it over a status code. */
export function detailOf(payload: unknown, status: number): string {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return `The server returned ${status}.`;
}
