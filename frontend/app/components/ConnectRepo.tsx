/*
 * ConnectRepo.tsx — Entry screen for Lumora.
 *
 * NOT IMPLEMENTED (single-user scope):
 *   - Repo history list (only the currently active repo is tracked in memory)
 *   - Multi-user auth / login (no user system; one API key, one instance)
 *   - Real indexing progress % (backend doesn't expose progress; bar is a pulse animation only)
 *   - Multi-repo simultaneous view
 */

"use client";

import { useState, useRef, KeyboardEvent } from "react";
import { indexRepo, isIndexError } from "@/lib/api";

export interface ActiveRepo {
  url: string;
  /** e.g. "owner/repo" derived from the URL */
  label: string;
  collection: string;
  itemsCount: number;
}

interface ConnectRepoProps {
  onConnected: (repo: ActiveRepo) => void;
}

function repoLabel(url: string): string {
  try {
    const u = new URL(url.trim());
    // pathname is "/owner/repo" or "/owner/repo.git" etc.
    return u.pathname.replace(/^\//, "").replace(/\.git$/, "");
  } catch {
    return url.trim();
  }
}

type Phase = "idle" | "submitting" | "success";

export default function ConnectRepo({ onConnected }: ConnectRepoProps) {
  const [url, setUrl] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const disabled = phase !== "idle";

  async function handleSubmit() {
    const trimmed = url.trim();
    if (!trimmed || disabled) return;

    setErrorMsg(null);
    setPhase("submitting");

    const result = await indexRepo(trimmed);

    if (isIndexError(result)) {
      setPhase("idle");
      setErrorMsg(result.error);
      inputRef.current?.focus();
      return;
    }

    setPhase("success");

    // Brief "indexed ✓" moment before handing off.
    setTimeout(() => {
      onConnected({
        url: trimmed,
        label: repoLabel(trimmed),
        collection: result.collection,
        itemsCount: result.itemsCount,
      });
    }, 900);
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      handleSubmit();
    }
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "2rem 1rem",
        background: "var(--ink)",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "480px",
          display: "flex",
          flexDirection: "column",
          gap: "1.5rem",
        }}
      >
        {/* ── Wordmark ──────────────────────────────────────────────── */}
        <div style={{ textAlign: "center" }}>
          <span
            style={{
              fontFamily: "var(--font-inter, sans-serif)",
              fontWeight: 700,
              fontSize: "1.625rem",
              letterSpacing: "-0.02em",
              color: "var(--paper)",
              userSelect: "none",
            }}
          >
            Lumora
          </span>
          <p
            style={{
              fontFamily: "var(--font-inter, sans-serif)",
              fontSize: "0.8125rem",
              color: "var(--ghost)",
              marginTop: "0.5rem",
              lineHeight: 1.5,
            }}
          >
            connect a github repository to start asking questions
          </p>
        </div>

        {/* ── Input + button ────────────────────────────────────────── */}
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "stretch" }}>
            {/* URL input */}
            <input
              ref={inputRef}
              id="repo-url-input"
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={disabled}
              placeholder="https://github.com/owner/repo"
              autoComplete="off"
              spellCheck={false}
              aria-label="GitHub repository URL"
              style={{
                flex: 1,
                fontFamily: "var(--font-ibm-plex-mono, monospace)",
                fontSize: "0.8125rem",
                color: "var(--paper)",
                background: "transparent",
                border: "1px solid var(--wire)",
                borderRadius: "4px",
                padding: "0.625rem 0.75rem",
                outline: "none",
                opacity: disabled ? 0.5 : 1,
                transition: "opacity 0.15s ease, border-color 0.15s ease",
              }}
              onFocus={(e) => {
                e.currentTarget.style.borderColor = "var(--ghost)";
              }}
              onBlur={(e) => {
                e.currentTarget.style.borderColor = "var(--wire)";
              }}
            />

            {/* Submit button */}
            <button
              id="index-repo-btn"
              onClick={handleSubmit}
              disabled={disabled}
              aria-label={
                phase === "submitting"
                  ? "Indexing repository…"
                  : phase === "success"
                  ? "Repository indexed"
                  : "Index repository"
              }
              style={{
                fontFamily: "var(--font-ibm-plex-mono, monospace)",
                fontSize: "0.75rem",
                color: phase === "success" ? "var(--signal)" : "var(--paper)",
                background: "transparent",
                border: "1px solid var(--wire)",
                borderRadius: "4px",
                padding: "0.625rem 1rem",
                cursor: disabled ? "default" : "pointer",
                opacity: disabled && phase !== "success" ? 0.6 : 1,
                transition:
                  "background 0.15s ease, opacity 0.15s ease, color 0.15s ease",
                whiteSpace: "nowrap",
                flexShrink: 0,
              }}
              onMouseEnter={(e) => {
                if (!disabled) {
                  e.currentTarget.style.background =
                    "color-mix(in srgb, var(--wire) 35%, transparent)";
                }
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "transparent";
              }}
            >
              {phase === "submitting"
                ? "indexing..."
                : phase === "success"
                ? "indexed ✓"
                : "index repository"}
            </button>
          </div>

          {/* Progress bar (submitting only) */}
          {phase === "submitting" && (
            <div
              aria-hidden="true"
              style={{
                height: "2px",
                background: "var(--wire)",
                borderRadius: "1px",
                overflow: "hidden",
              }}
            >
              <div
                className="index-progress-bar"
                style={{
                  height: "100%",
                  background: "var(--signal)",
                  borderRadius: "1px",
                }}
              />
            </div>
          )}

          {/* Help text */}
          {phase !== "success" && (
            <p
              style={{
                fontFamily: "var(--font-inter, sans-serif)",
                fontSize: "0.6875rem",
                color: "var(--ghost)",
                margin: 0,
                lineHeight: 1.4,
              }}
            >
              public github repositories only
            </p>
          )}

          {/* Error message */}
          {errorMsg && phase === "idle" && (
            <p
              role="alert"
              style={{
                fontFamily: "var(--font-inter, sans-serif)",
                fontSize: "0.75rem",
                color: "var(--error)",
                margin: 0,
                lineHeight: 1.4,
              }}
            >
              {errorMsg}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
