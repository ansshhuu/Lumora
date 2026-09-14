/*
 * ConnectRepo.tsx — Lumora landing screen.
 *
 * Dark lab-instrument aesthetic:
 *   - Ambient constellation canvas (sparse network graph, slow drift). This one
 *     is decorative; the post-scan Constellation is laid out from real graph data.
 *   - Grotesk for the wordmark and labels, JetBrains Mono for code and URLs
 *   - Cyan #4DE8D8 as the only accent colour
 *   - Near-black #050608 background, flat — no gradients, no blur, no glow
 *
 * NOT IMPLEMENTED (single-user scope):
 *   - Repo history list
 *   - Multi-user auth / login
 *   - Real indexing progress % (bar is animation only)
 *   - Multi-repo simultaneous view
 */

"use client";

import { useState, useRef, useEffect, useCallback, KeyboardEvent } from "react";
import { indexRepo, isIndexError } from "@/lib/api";

/* ─── Types ──────────────────────────────────────────────────────────────── */

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

type Phase = "idle" | "submitting" | "success";

/* ─── Helpers ────────────────────────────────────────────────────────────── */

function repoLabel(url: string): string {
  try {
    const u = new URL(url.trim());
    return u.pathname.replace(/^\//, "").replace(/\.git$/, "");
  } catch {
    return url.trim();
  }
}

/* ─── Constellation canvas ───────────────────────────────────────────────── */

const FILENAMES = [
  "main.py", "utils.ts", "index.js", "app.go", "server.rs",
  "routes.py", "types.ts", "config.yml", "schema.sql", "mod.rs",
  "handler.go", "api.ts", "models.py", "helpers.js", "parser.ts",
  "auth.py", "db.ts", "cli.go", "core.rs", "queue.py",
];

interface StarNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
  label: string;
  size: number;
}

function ConstellationCanvas({ scanning }: { scanning: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef   = useRef<number>(0);
  const nodesRef  = useRef<StarNode[]>([]);
  const pulseRef  = useRef(0);
  const scanRef   = useRef(scanning);

  useEffect(() => { scanRef.current = scanning; }, [scanning]);

  const initNodes = useCallback((w: number, h: number) => {
    const count = Math.min(50, Math.floor((w * h) / 18000));
    nodesRef.current = Array.from({ length: count }, (_, i) => ({
      x: Math.random() * w,
      y: Math.random() * h,
      vx: (Math.random() - 0.5) * 0.18,
      vy: (Math.random() - 0.5) * 0.18,
      label: FILENAMES[i % FILENAMES.length],
      size: Math.random() < 0.3 ? 2.5 : 1.8,
    }));
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const resize = () => {
      canvas.width  = window.innerWidth;
      canvas.height = window.innerHeight;
      initNodes(canvas.width, canvas.height);
    };
    resize();
    window.addEventListener("resize", resize);

    const MAX_DIST = 180;
    let last = performance.now();

    const draw = (now: number) => {
      const dt = Math.min((now - last) / 16.67, 3);
      last = now;
      pulseRef.current = (pulseRef.current + dt * 0.012) % (Math.PI * 2);
      const pulse = (Math.sin(pulseRef.current) + 1) / 2;

      const W = canvas.width;
      const H = canvas.height;
      const cx = W / 2;
      const cy = H / 2;

      ctx.clearRect(0, 0, W, H);

      const nodes = nodesRef.current;
      const isScanning = scanRef.current;

      // Move nodes — gentle drift, wrap at edges
      for (const n of nodes) {
        n.x += n.vx * dt;
        n.y += n.vy * dt;
        if (n.x < -20)    n.x = W + 20;
        if (n.x > W + 20) n.x = -20;
        if (n.y < -20)    n.y = H + 20;
        if (n.y > H + 20) n.y = -20;
      }

      // Draw edges
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i];
          const b = nodes[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist > MAX_DIST) continue;

          const fade = 1 - dist / MAX_DIST;
          const mx = (a.x + b.x) / 2 - cx;
          const my = (a.y + b.y) / 2 - cy;
          const mDist = Math.sqrt(mx * mx + my * my);
          const centerRadius = Math.min(W, H) * 0.28;
          const centerFactor = Math.max(0, 1 - mDist / centerRadius);

          if (centerFactor > 0.05 || isScanning) {
            // Cyan lift near the centre (and while scanning) — an edge reading
            // as live, not a bloom. Alpha only; the line stays 1px and crisp.
            const liftAlpha =
              centerFactor * fade * (0.16 + pulse * 0.2) * (isScanning ? 1.4 : 1);
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.strokeStyle = `rgba(77,232,216,${Math.min(liftAlpha, 0.42)})`;
            ctx.lineWidth = 1;
            ctx.stroke();
          } else {
            // Plain slate edges
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.strokeStyle = `rgba(58,66,80,${fade * 0.09})`;
            ctx.lineWidth = 1;
            ctx.stroke();
          }
        }
      }

      // Draw nodes + labels — solid dot, thin ring, no glow.
      ctx.font =
        "9px var(--font-jetbrains-mono), ui-monospace, SFMono-Regular, monospace";
      for (const n of nodes) {
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.size, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(237,239,242,0.5)";
        ctx.fill();

        ctx.beginPath();
        ctx.arc(n.x, n.y, n.size + 3, 0, Math.PI * 2);
        ctx.strokeStyle = "rgba(237,239,242,0.1)";
        ctx.lineWidth = 1;
        ctx.stroke();

        if (n.size > 2.0) {
          ctx.fillStyle = "rgba(122,132,148,0.55)";
          ctx.fillText(n.label, n.x + 6, n.y - 3);
        }
      }

      animRef.current = requestAnimationFrame(draw);
    };

    animRef.current = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(animRef.current);
      window.removeEventListener("resize", resize);
    };
  }, [initNodes]);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      style={{
        position: "fixed",
        inset: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "none",
        zIndex: 0,
      }}
    />
  );
}

/* ─── Main component ─────────────────────────────────────────────────────── */

export default function ConnectRepo({ onConnected }: ConnectRepoProps) {
  const [url,      setUrl]      = useState("");
  const [phase,    setPhase]    = useState<Phase>("idle");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const disabled  = phase !== "idle";
  const scanning  = phase === "submitting";
  const succeeded = phase === "success";

  const MONO: React.CSSProperties = {
    fontFamily:
      "var(--font-jetbrains-mono), ui-monospace, SFMono-Regular, Menlo, monospace",
  };

  async function handleSubmit() {
    if (disabled) return;
    const trimmed = url.trim();
    if (!trimmed) {
      setErrorMsg("Please include a valid repository");
      inputRef.current?.focus();
      return;
    }

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
    <>
      <style>{`
        @keyframes scan-progress {
          0%   { width: 0%;  opacity: 1; }
          55%  { width: 72%; opacity: 1; }
          80%  { width: 88%; opacity: 0.9; }
          100% { width: 88%; opacity: 0.9; }
        }
        @keyframes scan-success {
          0%   { width: 88%;  opacity: 0.9; }
          100% { width: 100%; opacity: 1; }
        }
        /* A thin ring that ticks outward — measurement, not luminescence. */
        @keyframes cx-pulse {
          0%   { box-shadow: 0 0 0 0 rgba(77,232,216,0.5); }
          70%  { box-shadow: 0 0 0 3px rgba(77,232,216,0); }
          100% { box-shadow: 0 0 0 3px rgba(77,232,216,0); }
        }
        .lumora-input:focus {
          outline: none;
          border-color: rgba(77,232,216,0.45) !important;
        }
        .lumora-input::placeholder {
          color: rgba(122,132,148,0.6);
        }
        .lumora-scan-btn:hover:not(:disabled) {
          background: rgba(77,232,216,0.07) !important;
        }
        .lumora-scan-btn:disabled {
          opacity: 0.55;
          cursor: default;
        }
        @media (prefers-reduced-motion: reduce) {
          .lumora-progress-bar { animation: none !important; width: 55% !important; }
          .lumora-scan-btn     { animation: none !important; }
        }
      `}</style>

      {/* Constellation layer */}
      <ConstellationCanvas scanning={scanning} />

      {/* Full-viewport centred stack */}
      <div
        style={{
          position: "relative",
          zIndex: 1,
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: "2rem 1.25rem",
          background: "#050608",
        }}
      >
        <div
          style={{
            width: "100%",
            maxWidth: "420px",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: "0.875rem",
          }}
        >
          {/* ── Wordmark ──────────────────────────────────────────────── */}
          <div style={{ textAlign: "center", marginBottom: "0.25rem" }}>
            <span
              style={{
                ...MONO,
                fontWeight: 500,
                fontSize: "18px",
                letterSpacing: "0.32em",
                color: "#EDEFF2",
                userSelect: "none",
                display: "block",
              }}
            >
              LUMORA
            </span>
            <span
              style={{
                ...MONO,
                fontSize: "11px",
                letterSpacing: "0.04em",
                color: "#7A8494",
                marginTop: "0.55rem",
                display: "block",
              }}
            >
              load a repository to begin scanning
            </span>
          </div>

          {/* ── Input strip ──────────────────────────────────────────── */}
          <div style={{ width: "100%", display: "flex", alignItems: "stretch" }}>
            <input
              ref={inputRef}
              id="repo-url-input"
              className="lumora-input"
              type="url"
              value={url}
              onChange={(e) => {
                setUrl(e.target.value);
                if (errorMsg) setErrorMsg(null);
              }}
              onKeyDown={handleKeyDown}
              disabled={disabled}
              placeholder="owner/repo"
              autoComplete="off"
              spellCheck={false}
              aria-label="GitHub repository URL"
              style={{
                ...MONO,
                flex: 1,
                fontSize: "12px",
                color: "#EDEFF2",
                background: "transparent",
                borderTop: errorMsg ? "1px solid #C4645A" : "1px solid #3A4250",
                borderBottom: errorMsg ? "1px solid #C4645A" : "1px solid #3A4250",
                borderLeft: errorMsg ? "1px solid #C4645A" : "1px solid #3A4250",
                borderRight: "none",
                borderRadius: "2px 0 0 2px",
                padding: "0.6rem 0.75rem",
                opacity: disabled ? 0.55 : 1,
                transition: "border-color 0.15s ease, opacity 0.15s ease",
                minWidth: 0,
              }}
            />

            <button
              id="scan-repo-btn"
              className="lumora-scan-btn"
              onClick={handleSubmit}
              disabled={disabled}
              aria-label={
                scanning
                  ? "Scanning repository…"
                  : succeeded
                  ? "Repository scanned"
                  : "Scan repository"
              }
              style={{
                ...MONO,
                fontSize: "11px",
                letterSpacing: "0.08em",
                color: succeeded ? "#EDEFF2" : "#4DE8D8",
                background: "transparent",
                border: succeeded ? "1px solid #3A4250" : "1px solid #4DE8D8",
                borderRadius: "0 2px 2px 0",
                padding: "0.6rem 0.9rem",
                cursor: "pointer",
                whiteSpace: "nowrap",
                flexShrink: 0,
                transition:
                  "background 0.15s ease, border-color 0.15s ease, color 0.15s ease",
                animation: !disabled ? "cx-pulse 3s ease-in-out infinite" : "none",
              }}
            >
              {scanning ? "scanning…" : succeeded ? "indexed ✓" : "[ SCAN ]"}
            </button>
          </div>

          {/* ── Progress track ───────────────────────────────────────── */}
          <div
            aria-hidden="true"
            style={{
              width: "100%",
              height: "1px",
              background: "#3A4250",
              position: "relative",
              overflow: "hidden",
            }}
          >
            {(scanning || succeeded) && (
              <div
                className="lumora-progress-bar"
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  height: "100%",
                  background: "#4DE8D8",
                  animation: succeeded
                    ? "scan-success 0.6s ease-out forwards"
                    : "scan-progress 4s ease-out forwards",
                }}
              />
            )}
          </div>

          {/* ── Help text ────────────────────────────────────────────── */}
          {!succeeded && !errorMsg && (
            <span
              style={{
                ...MONO,
                fontSize: "10px",
                color: "#4A5260",
                letterSpacing: "0.04em",
                alignSelf: "flex-start",
              }}
            >
              public github repositories only
            </span>
          )}

          {/* ── Error message ─────────────────────────────────────────── */}
          {errorMsg && phase === "idle" && (
            <p
              role="alert"
              style={{
                ...MONO,
                fontSize: "11px",
                color: "#C4645A",
                margin: 0,
                alignSelf: "flex-start",
                lineHeight: 1.4,
              }}
            >
              {errorMsg}
            </p>
          )}
        </div>
      </div>
    </>
  );
}
