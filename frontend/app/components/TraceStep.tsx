"use client";

import { TraceStep as TraceStepType } from "@/lib/types";

interface TraceStepProps {
  step: TraceStepType;
}

export default function TraceStep({ step }: TraceStepProps) {
  const { toolName, description, status, elapsedSeconds } = step;

  return (
    <div className="flex items-start gap-4 py-3 relative">
      {/* Timeline dot */}
      <div className="flex-shrink-0 flex items-center justify-center" style={{ width: "20px", marginTop: "2px" }}>
        {status === "done" && (
          <span
            className="block rounded-full bg-[var(--signal)]"
            style={{ width: "8px", height: "8px" }}
            aria-label="Done"
          />
        )}
        {status === "active" && (
          <span
            className="trace-dot-active block rounded-full bg-[var(--pending)]"
            style={{ width: "8px", height: "8px" }}
            aria-label="Active"
          />
        )}
        {status === "pending" && (
          <span
            className="block rounded-full bg-transparent"
            style={{
              width: "8px",
              height: "8px",
              boxSizing: "border-box",
              border: "1.5px solid var(--wire)",
            }}
            aria-label="Pending"
          />
        )}
      </div>

      {/* Step content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline justify-between gap-2">
          {/* Tool name */}
          <span
            className="text-[var(--paper)] text-sm font-medium leading-tight truncate"
            style={{ fontFamily: "var(--font-ibm-plex-mono, monospace)" }}
          >
            {toolName}
          </span>
          {/* Elapsed time */}
          {elapsedSeconds !== undefined && (
            <span
              className="flex-shrink-0 text-[var(--ghost)] text-xs tabular-nums"
              style={{ fontFamily: "var(--font-ibm-plex-mono, monospace)" }}
            >
              {elapsedSeconds.toFixed(1)}s
            </span>
          )}
        </div>
        {/* Description */}
        <p
          className="mt-0.5 text-[var(--ghost)] text-xs leading-snug"
          style={{ fontFamily: "var(--font-ibm-plex-mono, monospace)" }}
        >
          {description}
        </p>
      </div>
    </div>
  );
}
