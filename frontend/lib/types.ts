export type StepStatus = "done" | "active" | "pending";

export interface TraceStep {
  id: string;
  toolName: string;
  description: string;
  status: StepStatus;
  elapsedSeconds?: number;
}

export interface TraceAnswer {
  text: string;
  citation?: { file: string; lineStart: number; lineEnd: number };
  codeExcerpt?: { code: string; startLine: number };
}

/** Decoded SSE frames streamed by POST /query. */
export type QueryEvent =
  | { type: "tool_call"; name: string; input: string }
  | { type: "tool_result"; name: string; preview: string }
  | { type: "retry"; reason: string; attempt: number }
  | {
      type: "final_answer";
      text: string;
      citation?: TraceAnswer["citation"] | null;
    }
  | { type: "error"; message: string };
