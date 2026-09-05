"use client";

import { TraceStep as TraceStepType, TraceAnswer } from "@/lib/types";
import TraceStepComponent from "./TraceStep";

interface TracePanelProps {
  steps: TraceStepType[];
  answer?: TraceAnswer;
  /** True while a query is in flight — show the thinking indicator. */
  thinking?: boolean;
  /** Error message from a failed query — shown in --error color. */
  error?: string | null;
}

/** Very lightweight manual syntax tinting — no external lib needed yet */
function highlightLine(line: string): React.ReactNode {
  // Split into tokens and colorize keywords/strings
  const parts: React.ReactNode[] = [];
  let remaining = line;
  let key = 0;

  const patterns: { re: RegExp; className: string }[] = [
    // strings
    { re: /^(['"`])(.*?)\1/, className: "text-[var(--signal)]" },
    // keywords
    {
      re: /^(const|let|var|if|else|return|function|async|await|import|export|from|default|new|class|typeof|void|null|undefined|true|false|throw|try|catch|finally)\b/,
      className: "text-[var(--pending)]",
    },
  ];

  while (remaining.length > 0) {
    let matched = false;
    for (const { re, className } of patterns) {
      const m = remaining.match(re);
      if (m) {
        parts.push(
          <span key={key++} className={className}>
            {m[0]}
          </span>
        );
        remaining = remaining.slice(m[0].length);
        matched = true;
        break;
      }
    }
    if (!matched) {
      // consume one character as plain text
      const char = remaining[0];
      // merge with previous plain text node if possible
      const last = parts[parts.length - 1];
      if (typeof last === "string") {
        parts[parts.length - 1] = last + char;
      } else {
        parts.push(char);
      }
      remaining = remaining.slice(1);
    }
  }

  return <>{parts}</>;
}

function CodeExcerpt({
  code,
  startLine,
}: {
  code: string;
  startLine: number;
}) {
  const lines = code.split("\n");
  return (
    <div
      className="overflow-x-auto"
      style={{
        background: "color-mix(in srgb, var(--wire) 40%, var(--ink))",
        borderRadius: "2px",
        padding: "12px 0",
      }}
    >
      <table className="w-full border-collapse text-xs" style={{ fontFamily: "var(--font-ibm-plex-mono, monospace)" }}>
        <tbody>
          {lines.map((line, i) => (
            <tr key={i} className="leading-relaxed">
              <td
                className="select-none text-right pr-4 pl-4 text-[var(--ghost)] tabular-nums"
                style={{ width: "3rem", minWidth: "3rem", verticalAlign: "top" }}
              >
                {startLine + i}
              </td>
              <td className="pr-4 text-[var(--paper)] whitespace-pre">
                {highlightLine(line)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function TracePanel({ steps, answer, thinking, error }: TracePanelProps) {
  return (
    <div className="flex flex-col h-full px-6 py-6">
      {/* "trace" label + rule */}
      <div className="flex items-center gap-3 mb-2">
        <span
          className="text-[var(--ghost)] text-xs"
          style={{ fontFamily: "var(--font-ibm-plex-mono, monospace)" }}
        >
          trace
        </span>
        <div className="flex-1 border-t border-[var(--wire)]" />
      </div>

      {/* Timeline */}
      <div className="relative flex-1 overflow-y-auto">
        {/* Vertical line — only show when steps are visible */}
        {!thinking && !error && steps.length > 0 && (
          <div
            className="absolute top-0 bottom-0 border-l border-[var(--wire)]"
            style={{ left: "9px" }}
            aria-hidden="true"
          />
        )}

        {/* ── Thinking state ── */}
        {thinking && (
          <div
            className="flex items-center gap-3 mt-2"
            aria-live="polite"
            aria-label="Thinking…"
          >
            <span
              className="trace-dot-active block rounded-full bg-[var(--pending)] shrink-0"
              style={{ width: "8px", height: "8px" }}
              aria-hidden="true"
            />
            <span
              className="text-[var(--ghost)] text-xs"
              style={{ fontFamily: "var(--font-ibm-plex-mono, monospace)" }}
            >
              thinking...
            </span>
          </div>
        )}

        {/* ── Error state ── */}
        {!thinking && error && (
          <div className="mt-2 ml-0" role="alert">
            <p
              className="text-xs leading-relaxed"
              style={{
                fontFamily: "var(--font-inter, sans-serif)",
                color: "var(--error)",
              }}
            >
              {error}
            </p>
          </div>
        )}

        {/* ── Steps (real trace — currently empty until streaming is implemented) ── */}
        {!thinking && !error && steps.length > 0 && (
          <div className="flex flex-col">
            {steps.map((step) => (
              <TraceStepComponent key={step.id} step={step} />
            ))}
          </div>
        )}

        {/* ── Answer block ── */}
        {!thinking && !error && answer && (
          <div className="mt-4 ml-8">
            <div className="border-t border-[var(--wire)] mb-3" />
            <p
              className="text-[var(--ghost)] text-xs mb-3"
              style={{ fontFamily: "var(--font-ibm-plex-mono, monospace)" }}
            >
              answer
            </p>

            {/* Answer text */}
            <p
              className="text-[var(--paper)] text-sm leading-relaxed mb-3"
              style={{ fontFamily: "var(--font-inter, sans-serif)" }}
            >
              {answer.text}
              {answer.citation && (
                <>
                  {" "}
                  <button
                    className="text-[var(--pending)] cursor-pointer underline-offset-2 hover:underline focus-visible:underline focus-visible:outline-none transition-none"
                    style={{
                      fontFamily: "var(--font-ibm-plex-mono, monospace)",
                      fontSize: "0.75rem",
                      background: "none",
                      border: "none",
                      padding: 0,
                    }}
                    aria-label={`Open ${answer.citation.file} lines ${answer.citation.lineStart}–${answer.citation.lineEnd}`}
                  >
                    {answer.citation.file}:{answer.citation.lineStart}-
                    {answer.citation.lineEnd}
                  </button>
                </>
              )}
            </p>

            {/* Code excerpt */}
            {answer.codeExcerpt && (
              <CodeExcerpt
                code={answer.codeExcerpt.code}
                startLine={answer.codeExcerpt.startLine}
              />
            )}
          </div>
        )}

        {/* ── Empty state — no query yet ── */}
        {!thinking && !error && !answer && steps.length === 0 && (
          <div className="flex items-center mt-4">
            <p
              className="text-[var(--ghost)] text-xs"
              style={{ fontFamily: "var(--font-ibm-plex-mono, monospace)" }}
            >
              ask a question to see the answer here
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
