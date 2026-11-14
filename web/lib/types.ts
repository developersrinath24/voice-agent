export type SourceRef = {
  section: string;
  source: string;
  score: number;
};

export type Turn = {
  id: string;
  role: "user" | "assistant";
  text: string;
  sources?: SourceRef[];
  grounded?: boolean;
  timings?: Record<string, number>;
};

/** Shape returned by POST /voice/turn on the FastAPI backend. */
export type VoiceTurn = {
  session_id: string;
  transcript: string;
  response: string;
  grounded: boolean;
  sources: SourceRef[];
  audio_base64: string;
  audio_mime: string;
  timings_ms: Record<string, number>;
};

/** Shape returned by POST /chat on the FastAPI backend. */
export type ChatTurn = {
  session_id: string;
  response: string;
  grounded: boolean;
  sources: SourceRef[];
};
