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
