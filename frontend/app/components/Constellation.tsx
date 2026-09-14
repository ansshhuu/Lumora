"use client";

/**
 * Constellation — the repository's dependency structure as a force-directed field.
 *
 * Every position comes from the real graph: d3-force resolves the layout from
 * the edges the backend extracted, so two repos never look alike and nothing
 * here is hand-placed. The simulation is never allowed to fully settle — alpha
 * is topped up on each tick — which is what keeps the field weightless rather
 * than frozen.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
  type Simulation,
} from "d3-force";
import type { GraphEdge, GraphNode, RepoGraph } from "@/lib/types";

/* ─── Simulation node/link shapes ──────────────────────────────────────── */

interface SimNode extends GraphNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
  fx?: number | null;
  fy?: number | null;
  /** Per-node phase offset so idle drift never looks synchronised. */
  phase: number;
  radius: number;
}

interface SimLink {
  source: SimNode;
  target: SimNode;
  kind: GraphEdge["kind"];
}

/* ─── Palette (mirrors the CSS tokens; canvas can't read var()) ────────── */

const INK = "#050608";
const PAPER = "#EDEFF2";
const SIGNAL = "#4DE8D8";
const WIRE = "#3A4250";
const GHOST = "#7A8494";

/** Dot size by symbol kind — files anchor the field, methods are the finest grain. */
const RADIUS: Record<GraphNode["type"], number> = {
  file: 3.1,
  class: 2.6,
  function: 2.1,
  method: 1.8,
};

const MONO =
  "var(--font-jetbrains-mono), ui-monospace, SFMono-Regular, Menlo, monospace";

interface ConstellationProps {
  graph: RepoGraph;
  /** Node ids on the currently lit path — labels stay visible for these. */
  litPath?: string[];
  onSelect?: (node: GraphNode | null) => void;
  className?: string;
}

export default function Constellation({
  graph,
  litPath,
  onSelect,
  className,
}: ConstellationProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);

  const simRef = useRef<Simulation<SimNode, undefined> | null>(null);
  const nodesRef = useRef<SimNode[]>([]);
  const linksRef = useRef<SimLink[]>([]);
  const frameRef = useRef<number | null>(null);
  const sizeRef = useRef({ width: 0, height: 0, dpr: 1 });

  // Pointer state lives in refs: it changes on every mousemove and must not
  // re-render React at that rate. Hover is published to state only when the
  // node under the cursor actually changes.
  const pointerRef = useRef<{ x: number; y: number } | null>(null);
  const hoverRef = useRef<SimNode | null>(null);
  // The readout needs the node's identity, not its live position, so a snapshot
  // in state is both sufficient and safe to read while rendering.
  const [hovered, setHovered] = useState<GraphNode | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  // Mirrored into a ref so selecting a node does not restart the render loop.
  const selectedRef = useRef<string | null>(null);
  useEffect(() => {
    selectedRef.current = selectedId;
  }, [selectedId]);

  const litSet = useMemo(() => new Set(litPath ?? []), [litPath]);

  /** Adjacency, for dimming everything that is not connected to the focused node. */
  const neighbours = useMemo(() => {
    const map = new Map<string, Set<string>>();
    for (const edge of graph.edges) {
      if (!map.has(edge.source)) map.set(edge.source, new Set());
      if (!map.has(edge.target)) map.set(edge.target, new Set());
      map.get(edge.source)!.add(edge.target);
      map.get(edge.target)!.add(edge.source);
    }
    return map;
  }, [graph.edges]);

  /* ─── Build the simulation whenever the graph changes ────────────────── */
  useEffect(() => {
    const byId = new Map<string, SimNode>();

    // Seed positions on a deterministic ring rather than at the origin: d3's
    // default jitter around (0,0) makes the first few hundred ms look like an
    // explosion, and identical seeds would leave coincident nodes stuck.
    const seeded: SimNode[] = graph.nodes.map((node, i) => {
      const angle = (i / Math.max(graph.nodes.length, 1)) * Math.PI * 2;
      const ring = 60 + (i % 7) * 18;
      const simNode: SimNode = {
        ...node,
        x: Math.cos(angle) * ring,
        y: Math.sin(angle) * ring,
        vx: 0,
        vy: 0,
        phase: (i * 2.399963) % (Math.PI * 2),
        radius: RADIUS[node.type] ?? RADIUS.function,
      };
      byId.set(node.id, simNode);
      return simNode;
    });

    // Edges referencing a trimmed node are dropped — forceLink throws on an
    // unresolved endpoint, and the server trims nodes independently of edges.
    const links: SimLink[] = [];
    for (const edge of graph.edges) {
      const source = byId.get(edge.source);
      const target = byId.get(edge.target);
      if (source && target) links.push({ source, target, kind: edge.kind });
    }

    nodesRef.current = seeded;
    linksRef.current = links;

    const simulation = forceSimulation<SimNode>(seeded)
      .force(
        "link",
        forceLink<SimNode, SimLink>(links)
          .id((d) => d.id)
          // Import edges are structural and hold tighter than call edges.
          .distance((l) => (l.kind === "import" ? 42 : 66))
          .strength(0.32)
      )
      .force("charge", forceManyBody<SimNode>().strength(-118).distanceMax(420))
      .force("collide", forceCollide<SimNode>((d) => d.radius + 9))
      .force("center", forceCenter(0, 0).strength(0.06))
      // A weak pull to origin keeps disconnected components from drifting off
      // screen forever — isolated files are common and would otherwise escape.
      .force("x", forceX(0).strength(0.022))
      .force("y", forceY(0).strength(0.022))
      .alpha(1)
      .alphaDecay(0.028)
      .velocityDecay(0.36);

    // Rendering is driven by our own rAF loop, so d3's internal timer would
    // only duplicate the work.
    simulation.stop();
    simRef.current = simulation;

    hoverRef.current = null;

    return () => {
      simulation.stop();
      simRef.current = null;
    };
  }, [graph]);

  /* ─── Canvas sizing (DPR-aware) ──────────────────────────────────────── */
  useEffect(() => {
    const wrap = wrapRef.current;
    const canvas = canvasRef.current;
    if (!wrap || !canvas) return;

    const resize = () => {
      const { width, height } = wrap.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      sizeRef.current = { width, height, dpr };
      canvas.width = Math.max(1, Math.round(width * dpr));
      canvas.height = Math.max(1, Math.round(height * dpr));
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
    };

    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(wrap);
    return () => observer.disconnect();
  }, []);

  /** Nearest node to the pointer, within a forgiving radius. */
  const pickNode = useCallback((px: number, py: number): SimNode | null => {
    const { width, height } = sizeRef.current;
    const cx = width / 2;
    const cy = height / 2;
    let best: SimNode | null = null;
    let bestDist = 14 * 14;

    for (const node of nodesRef.current) {
      const dx = node.x + cx - px;
      const dy = node.y + cy - py;
      const dist = dx * dx + dy * dy;
      if (dist < bestDist) {
        bestDist = dist;
        best = node;
      }
    }
    return best;
  }, []);

  /* ─── Render loop ────────────────────────────────────────────────────── */
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduceMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;

    let elapsed = 0;

    const draw = () => {
      const simulation = simRef.current;
      const { width, height, dpr } = sizeRef.current;
      if (!simulation || width === 0 || height === 0) {
        frameRef.current = requestAnimationFrame(draw);
        return;
      }

      elapsed += 1 / 60;

      // Never let the simulation converge. Once alpha decays to the floor the
      // field would lock rigid; topping it up is what keeps nodes weightless.
      if (!reduceMotion) {
        if (simulation.alpha() < 0.035) simulation.alpha(0.035);
        simulation.tick();

        // Low-amplitude jitter applied as velocity, not position, so collision
        // and link forces still arbitrate the result and nothing overlaps.
        for (const node of nodesRef.current) {
          node.vx += Math.cos(elapsed * 0.32 + node.phase) * 0.0072;
          node.vy += Math.sin(elapsed * 0.27 + node.phase * 1.3) * 0.0072;
        }
      } else if (simulation.alpha() > 0.002) {
        simulation.tick();
      }

      ctx.save();
      ctx.scale(dpr, dpr);
      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = INK;
      ctx.fillRect(0, 0, width, height);
      ctx.translate(width / 2, height / 2);

      const focusId = hoverRef.current?.id ?? selectedRef.current;
      const focusNeighbours = focusId ? neighbours.get(focusId) : undefined;
      const hasLit = litSet.size > 0;

      /* Edges — 1px slate, low opacity. */
      ctx.lineWidth = 1;
      for (const link of linksRef.current) {
        const litEdge =
          hasLit && litSet.has(link.source.id) && litSet.has(link.target.id);
        const focusEdge =
          focusId != null &&
          (link.source.id === focusId || link.target.id === focusId);

        let alpha: number;
        if (litEdge) alpha = 0.5;
        else if (focusEdge) alpha = 0.42;
        else if (focusId != null || hasLit) alpha = 0.06;
        else alpha = 0.16;

        ctx.globalAlpha = alpha;
        ctx.strokeStyle = litEdge || focusEdge ? SIGNAL : WIRE;

        ctx.beginPath();
        ctx.moveTo(link.source.x, link.source.y);
        ctx.lineTo(link.target.x, link.target.y);

        // Call edges read as derived rather than structural.
        if (link.kind === "call") ctx.setLineDash([2, 3]);
        else ctx.setLineDash([]);
        ctx.stroke();
      }
      ctx.setLineDash([]);

      /* Nodes — solid dot plus a thin ring. No glow anywhere. */
      for (const node of nodesRef.current) {
        const isLit = litSet.has(node.id);
        const isFocus = node.id === focusId;
        const isNeighbour = focusNeighbours?.has(node.id) ?? false;
        const dimmed = (focusId != null || hasLit) && !isLit && !isFocus && !isNeighbour;

        const accent = isLit || isFocus;
        const baseAlpha = accent ? 0.95 : dimmed ? 0.07 : 0.14;

        ctx.globalAlpha = baseAlpha;
        ctx.fillStyle = accent ? SIGNAL : PAPER;
        ctx.beginPath();
        ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
        ctx.fill();

        ctx.globalAlpha = accent ? 0.55 : dimmed ? 0.05 : 0.1;
        ctx.strokeStyle = accent ? SIGNAL : PAPER;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.arc(node.x, node.y, node.radius + 3.5, 0, Math.PI * 2);
        ctx.stroke();
      }

      /* Labels — monospace, tiny, grey. Only on hover, selection, or lit path. */
      ctx.font = `10px ${MONO}`;
      ctx.textBaseline = "middle";
      for (const node of nodesRef.current) {
        const isLit = litSet.has(node.id);
        const isFocus = node.id === focusId;
        const isNeighbour = focusNeighbours?.has(node.id) ?? false;
        if (!isLit && !isFocus && !isNeighbour) continue;

        ctx.globalAlpha = isFocus || isLit ? 0.92 : 0.4;
        ctx.fillStyle = isFocus || isLit ? PAPER : GHOST;
        ctx.fillText(node.label, node.x + node.radius + 7, node.y);
      }

      ctx.restore();

      // Hover resolution shares the frame so it always matches drawn positions.
      const pointer = pointerRef.current;
      const next = pointer ? pickNode(pointer.x, pointer.y) : null;
      if (next?.id !== hoverRef.current?.id) {
        hoverRef.current = next;
        setHovered(next);
      }

      frameRef.current = requestAnimationFrame(draw);
    };

    frameRef.current = requestAnimationFrame(draw);
    return () => {
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
    };
  }, [graph, litSet, neighbours, pickNode]);

  /* ─── Pointer handling ───────────────────────────────────────────────── */
  const handleMove = useCallback((event: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    pointerRef.current = {
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
    };
  }, []);

  const handleLeave = useCallback(() => {
    pointerRef.current = null;
  }, []);

  // Clicking the already-selected node clears it, so the field can be returned
  // to its unfocused state without hunting for empty space.
  const handleClick = useCallback(() => {
    const node = hoverRef.current;
    const nextId = node && node.id !== selectedRef.current ? node.id : null;
    setSelectedId(nextId);
    onSelect?.(nextId ? (node as GraphNode) : null);
  }, [onSelect]);

  return (
    <div
      ref={wrapRef}
      className={`relative h-full w-full overflow-hidden ${className ?? ""}`}
    >
      <canvas
        ref={canvasRef}
        onMouseMove={handleMove}
        onMouseLeave={handleLeave}
        onClick={handleClick}
        className="block h-full w-full"
        style={{ cursor: hovered ? "pointer" : "default" }}
        aria-label={`Dependency constellation: ${graph.nodes.length} nodes, ${graph.edges.length} connections`}
      />

      {/* Hover readout — pinned, so it never occludes the field it describes. */}
      {hovered && (
        <div
          className="pointer-events-none absolute left-3 bottom-3 max-w-[min(30rem,calc(100%-1.5rem))] border px-3 py-2"
          style={{ background: "var(--panel)", borderColor: "var(--wire)" }}
        >
          <div
            className="truncate text-[11px]"
            style={{ fontFamily: MONO, color: "var(--paper)" }}
          >
            {hovered.qualified ?? hovered.label}
          </div>
          <div
            className="mt-0.5 truncate text-[10px]"
            style={{ fontFamily: MONO, color: "var(--ghost)" }}
          >
            {hovered.file}
            {hovered.line ? `:${hovered.line}` : ""}
          </div>
        </div>
      )}

      {/* Scale readout. Grotesk for the label, mono for the values. */}
      <div className="pointer-events-none absolute right-3 top-3 flex items-center gap-3">
        <span
          className="text-[10px] uppercase tracking-[0.14em]"
          style={{ color: "var(--ghost)" }}
        >
          Structure
        </span>
        <span className="text-[10px]" style={{ fontFamily: MONO, color: "var(--ghost)" }}>
          {graph.nodes.length}
          {graph.truncated ? `/${graph.total_nodes}` : ""} nodes · {graph.edges.length} edges
        </span>
      </div>
    </div>
  );
}
