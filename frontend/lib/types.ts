export type StepStatus = "done" | "active" | "pending";

/* ─── Dependency graph (GET /graph) ─────────────────────────────────────── */

export type GraphNodeType = "file" | "class" | "function" | "method";

export interface GraphNode {
  id: string;
  label: string;
  file: string;
  type: GraphNodeType;
  /** Absent on file nodes. */
  module?: string;
  qualified?: string;
  line?: number;
  degree: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  kind: "import" | "call";
}

export interface RepoGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  /** True when the repo had more nodes than the server returned. */
  truncated: boolean;
  total_nodes: number;
}

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
