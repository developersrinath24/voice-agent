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
};

/** Shape returned by POST /chat on the FastAPI backend. */
export type ChatTurn = {
  session_id: string;
  response: string;
  grounded: boolean;
  sources: SourceRef[];
};

export type ClinicSection = {
  section: string;
  content: string;
};

/** Shape returned by GET /voice/session: what the browser needs to place a call. */
export type VoiceSession = {
  signed_url: string;
  max_seconds: number;
  remaining_calls: number;
};

/** Shape returned by GET /documents: one knowledge base file. */
export type ClinicDocument = {
  source: string;
  title: string;
  category: string;
  last_reviewed: string;
  sections: ClinicSection[];
  chunk_count: number;
};
