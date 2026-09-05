"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import QuestionPanel from "./components/QuestionPanel";
import TracePanel from "./components/TracePanel";
import { TraceStep, TraceAnswer } from "@/lib/types";

/* ─── Hardcoded mock data ──────────────────────────────────────────────── */
const MOCK_STEPS: TraceStep[] = [
  {
    id: "1",
    toolName: "search_codebase",
    description: "searching for session redirect handling",
    status: "done",
    elapsedSeconds: 0.6,
  },
  {
    id: "2",
    toolName: "search_codebase",
    description: "expanding search to middleware layer",
    status: "done",
    elapsedSeconds: 0.4,
  },
  {
    id: "3",
    toolName: "fetch_file: src/middleware/auth.middleware.ts",
    description: "reading authentication middleware",
    status: "done",
    elapsedSeconds: 0.3,
  },
  {
    id: "4",
    toolName: "search_codebase",
    description: "looking for redirect() call sites",
    status: "done",
    elapsedSeconds: 0.5,
  },
  {
    id: "5",
    toolName: "fetch_file: src/lib/session.ts",
    description: "reading session utility",
    status: "active",
    elapsedSeconds: undefined,
  },
  {
    id: "6",
    toolName: "synthesize_answer",
    description: "composing final response",
    status: "pending",
    elapsedSeconds: undefined,
  },
];

const MOCK_ANSWER: TraceAnswer = {
  text: "Unauthorized access is handled in the authentication middleware. When a request arrives, the middleware calls",
  citation: {
    file: "src/middleware/auth.middleware.ts",
    lineStart: 42,
    lineEnd: 48,
  },
  codeExcerpt: {
    startLine: 42,
    code: `export async function authMiddleware(req: Request) {
  const session = await getSession(req)
  if (!session?.userId) {
    return redirect('/login')
  }
  return next()
}`,
  },
};

/* ─── Page ─────────────────────────────────────────────────────────────── */
export default function Home() {
  const [_query, setQuery] = useState("");
  // In production this would drive an API call;
  // for now the mock data is always shown.

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      {/* ── Top bar ────────────────────────────────────────────────── */}
      <header
        id="topbar"
        className="flex items-center justify-between px-5 flex-shrink-0 border-b border-[var(--wire)]"
        style={{ height: "56px" }}
      >
        {/* Left: wordmark + repo selector */}
        <div className="flex items-center gap-5">
          <span
            className="text-[var(--paper)] font-bold text-sm tracking-tight select-none"
            style={{ fontFamily: "var(--font-inter, sans-serif)" }}
          >
            Lumora
          </span>

          <div className="hidden sm:flex items-center gap-1.5">
            <span
              className="text-[var(--ghost)] text-xs"
              style={{ fontFamily: "var(--font-ibm-plex-mono, monospace)" }}
            >
              repo:
            </span>
            <button
              id="repo-selector"
              className="flex items-center gap-1 text-[var(--paper)] text-xs focus-visible:outline focus-visible:outline-1 focus-visible:outline-[var(--signal)] focus-visible:rounded-sm"
              style={{ fontFamily: "var(--font-ibm-plex-mono, monospace)", background: "none", border: "none", cursor: "pointer", padding: 0 }}
              aria-label="Select repository"
              aria-haspopup="listbox"
            >
              lumora/backend
              <ChevronDown size={11} strokeWidth={1.5} className="text-[var(--ghost)] mt-px" />
            </button>
          </div>
        </div>

        {/* Right: live indicator */}
        <div
          className="flex items-center gap-2"
          style={{ fontFamily: "var(--font-inter, sans-serif)" }}
          aria-label="Connection status: live"
        >
          <span
            className="signal-pulse block rounded-full bg-[var(--signal)]"
            style={{ width: "7px", height: "7px" }}
            aria-hidden="true"
          />
          <span className="text-[var(--ghost)] text-xs">live</span>
        </div>
      </header>

      {/* ── Two-column body ─────────────────────────────────────────── */}
      <main
        id="main-content"
        className="flex flex-col sm:flex-row flex-1 overflow-hidden"
      >
        {/* Left column — Question panel (35%) */}
        <section
          id="question-panel"
          aria-label="Query input"
          className="sm:w-[35%] overflow-y-auto border-b sm:border-b-0 sm:border-r border-[var(--wire)] flex-shrink-0"
        >
          <QuestionPanel onSubmit={(q) => setQuery(q)} />
        </section>

        {/* Right column — Trace panel (65%) */}
        <section
          id="trace-panel"
          aria-label="Trace output"
          className="flex-1 overflow-y-auto"
        >
          <TracePanel steps={MOCK_STEPS} answer={MOCK_ANSWER} />
        </section>
      </main>
    </div>
  );
}
