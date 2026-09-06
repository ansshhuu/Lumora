"use client";

import { useState } from "react";
import QuestionPanel from "./components/QuestionPanel";
import TracePanel from "./components/TracePanel";
import ConnectRepo, { ActiveRepo } from "./components/ConnectRepo";
import { TraceAnswer, TraceStep } from "@/lib/types";
import { queryRepo, isQueryError } from "@/lib/api";

const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? "";

/* ─── Page ─────────────────────────────────────────────────────────────── */
export default function Home() {
  const [activeRepo, setActiveRepo] = useState<ActiveRepo | null>(null);

  // Query state — no mock data, all real.
  const [thinking, setThinking] = useState(false);
  const [steps, setSteps] = useState<TraceStep[]>([]);
  const [answer, setAnswer] = useState<TraceAnswer | undefined>(undefined);
  const [queryError, setQueryError] = useState<string | null>(null);

  // No repo connected yet — show the connect screen.
  if (!activeRepo) {
    return <ConnectRepo onConnected={setActiveRepo} />;
  }

  async function handleQuestion(question: string) {
    if (thinking) return; // prevent double-submit while in-flight

    // Clear stale state before starting a new request.
    setSteps([]);
    setAnswer(undefined);
    setQueryError(null);
    setThinking(true);

    // Wall-clock start for each in-flight step, keyed by step id. Held in a
    // local map rather than state so timing never triggers a re-render.
    const startedAt = new Map<string, number>();
    let seq = 0;

    const result = await queryRepo(
      question,
      activeRepo!.collection,
      (event) => {
        if (event.type === "tool_call") {
          const id = `step-${seq++}`;
          startedAt.set(id, performance.now());
          setSteps((prev) => [
            ...prev,
            {
              id,
              toolName: event.name,
              description: event.input,
              status: "active",
            },
          ]);
          return;
        }

        if (event.type === "retry") {
          // The backend abandoned that attempt and is starting over, so the
          // steps already on screen belong to a run that no longer counts.
          console.warn(
            `[query] retrying (attempt ${event.attempt}): ${event.reason}`
          );
          startedAt.clear();
          setSteps([]);
          return;
        }

        if (event.type === "tool_result") {
          // Close the most recent still-active step for this tool: the agent
          // may call the same tool several times, and results arrive in order.
          setSteps((prev) => {
            const index = prev.findLastIndex(
              (s) => s.toolName === event.name && s.status === "active"
            );
            if (index === -1) return prev;

            const started = startedAt.get(prev[index].id);
            const next = [...prev];
            next[index] = {
              ...next[index],
              status: "done",
              elapsedSeconds:
                started === undefined
                  ? undefined
                  : (performance.now() - started) / 1000,
            };
            return next;
          });
          return;
        }

        if (event.type === "final_answer") {
          // The agent can finish while a call is unresolved (e.g. it answered
          // from a result it already had); don't strand a gold dot.
          setSteps((prev) =>
            prev.map((s) => (s.status === "active" ? { ...s, status: "done" } : s))
          );
          setAnswer({
            text: event.text,
            citation: event.citation ?? undefined,
          });
        }
      },
      API_KEY
    );

    setThinking(false);

    if (isQueryError(result)) {
      setQueryError(result.error);
    }
    // On success the answer was already set by the final_answer event above,
    // so there is nothing left to do here.
  }

  // Repo is connected — show the main question/trace UI.
  return (
    <div className="flex flex-col h-screen overflow-hidden">
      {/* ── Top bar ────────────────────────────────────────────────── */}
      <header
        id="topbar"
        className="flex items-center justify-between px-5 flex-shrink-0 border-b border-[var(--wire)]"
        style={{ height: "56px" }}
      >
        {/* Left: wordmark + repo label + change link */}
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
            <span
              className="text-[var(--paper)] text-xs"
              style={{ fontFamily: "var(--font-ibm-plex-mono, monospace)" }}
            >
              {activeRepo.label}
            </span>
            {/* "change" link — resets to ConnectRepo screen */}
            <button
              id="change-repo-btn"
              onClick={() => {
                // Also clear query state when switching repos.
                setActiveRepo(null);
                setSteps([]);
                setAnswer(undefined);
                setQueryError(null);
                setThinking(false);
              }}
              aria-label="Connect a different repository"
              style={{
                fontFamily: "var(--font-inter, sans-serif)",
                fontSize: "0.6875rem",
                color: "var(--ghost)",
                background: "none",
                border: "none",
                cursor: "pointer",
                padding: "0 0.125rem",
                textDecoration: "none",
                lineHeight: 1,
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.textDecoration = "underline";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.textDecoration = "none";
              }}
            >
              change
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
          <QuestionPanel onSubmit={handleQuestion} disabled={thinking} />
        </section>

        {/* Right column — Trace panel (65%) */}
        <section
          id="trace-panel"
          aria-label="Trace output"
          className="flex-1 overflow-y-auto"
        >
          <TracePanel
            steps={steps}
            answer={answer}
            thinking={thinking}
            error={queryError}
          />
        </section>
      </main>
    </div>
  );
}
