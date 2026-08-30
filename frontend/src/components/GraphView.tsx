"use client";

import { useEffect, useRef } from "react";
import type ForceGraph from "force-graph";
import type { GraphEvidence } from "@/lib/api";

type NodeDatum = { id: string; name: string; group: string };
type LinkDatum = { source: string; target: string; label: string };
type ForceGraphInstance = ForceGraph<NodeDatum, LinkDatum>;

/**
 * Phase 6 Part 2: renders the entities/relations retrieval actually used
 * (`QueryResponse.graph_evidence`) as an interactive force-directed graph.
 *
 * Uses `force-graph` (canvas-based) rather than a React-wrapped graph
 * library — it has no React peer dependency at all, which matters against
 * this project's brand-new React 19 / Next 16 stack where an older
 * React-graph wrapper could easily fail to install cleanly. Loaded via a
 * dynamic `import()` inside `useEffect` (client-only, after mount) instead
 * of a top-level import, since it touches the DOM/canvas directly and would
 * break server-side rendering otherwise.
 */
export default function GraphView({ evidence }: { evidence: GraphEvidence }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<ForceGraphInstance | null>(null);

  useEffect(() => {
    if (!containerRef.current || evidence.nodes.length === 0) return;
    let cancelled = false;
    const container = containerRef.current;

    import("force-graph").then(({ default: ForceGraphCtor }) => {
      if (cancelled || !container) return;
      const graph: ForceGraphInstance = new ForceGraphCtor<NodeDatum, LinkDatum>(container)
        .graphData({
          nodes: evidence.nodes.map((node) => ({
            id: node.id,
            name: node.name,
            group: node.entity_type,
          })),
          links: evidence.edges.map((edge) => ({
            source: edge.source,
            target: edge.target,
            label: edge.relation_type,
          })),
        })
        .nodeId("id")
        .nodeLabel((node) => `${node.name} (${node.group})`)
        .nodeAutoColorBy("group")
        .linkLabel((link) => link.label)
        .linkColor(() => "rgba(148, 163, 184, 0.5)")
        .linkDirectionalArrowLength(4)
        .linkDirectionalArrowRelPos(1)
        .backgroundColor("rgba(0,0,0,0)")
        .width(container.clientWidth)
        .height(280);
      graphRef.current = graph;
    });

    return () => {
      cancelled = true;
      graphRef.current?._destructor?.();
      graphRef.current = null;
    };
  }, [evidence]);

  if (evidence.nodes.length === 0) return null;

  return (
    <div className="mt-3 overflow-hidden rounded-2xl border border-surface-border bg-background">
      <p className="border-b border-surface-border px-2.5 py-1.5 text-[11px] font-medium text-zinc-500 dark:text-zinc-500">
        Retrieval graph — {evidence.nodes.length} entities, {evidence.edges.length} relations
      </p>
      <div ref={containerRef} />
    </div>
  );
}
