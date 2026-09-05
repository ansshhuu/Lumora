"use client";

import { useState, useRef, KeyboardEvent } from "react";
import { CornerDownLeft, ChevronRight } from "lucide-react";

const SUGGESTIONS = [
  "Show me the authentication flow",
  "Where is user session stored?",
  "Find all places where redirect() is used",
  "How is unauthorized access handled?",
];

interface QuestionPanelProps {
  onSubmit?: (query: string) => void;
}

export default function QuestionPanel({ onSubmit }: QuestionPanelProps) {
  const [query, setQuery] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function handleSubmit() {
    const trimmed = query.trim();
    if (!trimmed) return;
    onSubmit?.(trimmed);
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSubmit();
    }
  }

  function fillSuggestion(text: string) {
    setQuery(text);
    textareaRef.current?.focus();
  }

  return (
    <div className="flex flex-col h-full px-6 py-6 gap-6">
      {/* Heading */}
      <h2
        style={{ fontFamily: "var(--font-inter, sans-serif)" }}
        className="text-[var(--paper)] text-base font-medium leading-tight"
      >
        What do you want to know?
      </h2>

      {/* Textarea area */}
      <div className="flex flex-col gap-0">
        <div
          className="relative border border-[var(--wire)]"
          style={{ borderRadius: "4px" }}
        >
          <textarea
            ref={textareaRef}
            id="query-input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="ask anything about this codebase"
            rows={6}
            className="w-full resize-none bg-transparent text-[var(--paper)] text-sm leading-relaxed px-3 py-3 pr-10 placeholder:text-[var(--ghost)] focus:outline-none"
            style={{
              fontFamily: "var(--font-ibm-plex-mono, monospace)",
              borderRadius: "4px",
            }}
            aria-label="Query input"
          />
          {/* Send button */}
          <button
            id="send-query-btn"
            onClick={handleSubmit}
            aria-label="Submit query"
            className="absolute bottom-3 right-3 text-[var(--paper)] opacity-50 hover:opacity-100 transition-opacity duration-150 focus-visible:outline focus-visible:outline-1 focus-visible:outline-[var(--signal)] focus-visible:outline-offset-2 rounded-sm p-0.5"
          >
            <CornerDownLeft size={15} strokeWidth={1.5} />
          </button>
        </div>
        <p
          className="mt-1.5 text-[var(--ghost)] text-xs leading-none"
          style={{ fontFamily: "var(--font-inter, sans-serif)" }}
        >
          ⌘↵ to submit
        </p>
      </div>

      {/* Suggested questions */}
      <div className="flex flex-col divide-y divide-[var(--wire)]">
          {SUGGESTIONS.map((text, i) => (
            <button
              key={i}
              id={`suggestion-${i}`}
              onClick={() => fillSuggestion(text)}
              className="suggested-question flex items-center justify-between gap-3 px-3 py-3 text-left text-sm text-[var(--paper)] focus-visible:outline focus-visible:outline-1 focus-visible:outline-[var(--signal)] focus-visible:outline-offset-[-1px]"
              style={{
                fontFamily: "var(--font-inter, sans-serif)",
                background: "transparent",
                border: "none",
                cursor: "pointer",
                borderRadius: "2px",
              }}
              aria-label={`Suggested query: ${text}`}
            >
              <span className="leading-snug">{text}</span>
              <ChevronRight
                size={13}
                strokeWidth={1.5}
                className="shrink-0 text-[var(--ghost)]"
              />
            </button>
          ))}
      </div>
    </div>
  );
}
