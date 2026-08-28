import { forceCollide, forceLink, forceManyBody, forceSimulation, forceX } from "d3-force";

type Tier = 0 | 1 | 2 | 3;
type NodeType = "reg" | "neutral" | "accent" | "bronze" | "terracotta";

type MapNode = {
  id: string;
  label: string;
  type: NodeType;
  tier: Tier;
  x: number;
  y: number;
  fy?: number;
};

const TIER_Y: Record<Tier, number> = { 0: 50, 1: 140, 2: 230, 3: 300 };

// Explicit deterministic initial x/y per node (never left to d3-force's own
// defaults, which can otherwise differ run to run) — required so the
// simulation below produces byte-identical output during SSR and client
// hydration; no Math.random anywhere in this module.
const RAW_NODES: MapNode[] = [
  { id: "reg", label: "Regulation", type: "reg", tier: 0, x: 150, y: TIER_Y[0] },
  { id: "pol", label: "Policy", type: "reg", tier: 0, x: 400, y: TIER_Y[0] },
  { id: "art1", label: "Article", type: "neutral", tier: 1, x: 100, y: TIER_Y[1] },
  { id: "art2", label: "Article", type: "neutral", tier: 1, x: 250, y: TIER_Y[1] },
  { id: "req1", label: "Requirement", type: "accent", tier: 1, x: 400, y: TIER_Y[1] },
  { id: "req2", label: "Requirement", type: "accent", tier: 1, x: 520, y: TIER_Y[1] },
  { id: "ctl1", label: "Control", type: "bronze", tier: 2, x: 180, y: TIER_Y[2] },
  { id: "ctl2", label: "Control", type: "bronze", tier: 2, x: 340, y: TIER_Y[2] },
  { id: "evi", label: "Evidence", type: "accent", tier: 2, x: 480, y: TIER_Y[2] },
  { id: "risk", label: "Risk", type: "terracotta", tier: 3, x: 320, y: TIER_Y[3] },
];

const RAW_EDGES: [string, string][] = [
  ["reg", "art1"],
  ["reg", "art2"],
  ["art1", "req1"],
  ["art2", "req2"],
  ["req1", "pol"],
  ["req1", "ctl1"],
  ["req2", "evi"],
  ["pol", "risk"],
  ["ctl1", "risk"],
  ["ctl1", "evi"],
  ["ctl2", "risk"],
  ["ctl2", "ctl1"],
];

/**
 * Brief section 8: "use d3-force purely for node-position physics, then
 * hand-style the rendering in SVG/React" — so the layout is a real force
 * simulation, not another hand-placed diagram, but it isn't a free-floating
 * hairball either. `fy` pins every node to its tier's row (Regulation/
 * Policy → Requirement/Article → Control/Evidence → Risk); only x is left
 * free for `forceLink`/`forceManyBody`/`forceCollide` to settle — the
 * "roughly layered, not automatic" layout the brief asks for.
 *
 * Run synchronously to convergence at module load (300 ticks, well past
 * typical d3-force stabilization) rather than animated in the browser —
 * this is a static brand illustration, not a live simulation, and running
 * it once at import time keeps the result identical between SSR and
 * client hydration.
 */
type RawEdge = { source: string; target: string };

function layoutNodes(): MapNode[] {
  const nodes = RAW_NODES.map((n) => ({ ...n, fy: TIER_Y[n.tier] }));
  const edges: RawEdge[] = RAW_EDGES.map(([source, target]) => ({ source, target }));
  const simulation = forceSimulation(nodes)
    .force(
      "link",
      forceLink<MapNode, RawEdge>(edges)
        .id((d) => d.id)
        .distance(95)
        .strength(0.25),
    )
    .force("charge", forceManyBody().strength(-90))
    .force("collide", forceCollide(38))
    .force("x", forceX(310).strength(0.03))
    .stop();

  for (let i = 0; i < 300; i++) simulation.tick();
  return nodes;
}

export const NODES = layoutNodes();
export const NODE_BY_ID = new Map(NODES.map((n) => [n.id, n]));

const DOT_CLASS: Record<NodeType, string> = {
  reg: "fill-landing-olive",
  neutral: "fill-landing-fg/40",
  accent: "fill-landing-accent",
  bronze: "fill-landing-thread",
  terracotta: "fill-landing-terracotta",
};

const LEGEND: { label: string; type: NodeType }[] = [
  { label: "Regulation / Policy", type: "reg" },
  { label: "Requirement / Evidence", type: "accent" },
  { label: "Control", type: "bronze" },
  { label: "Risk", type: "terracotta" },
];

export default function KnowledgeGraph({ overlay }: { overlay?: React.ReactNode } = {}) {
  return (
    <div>
      <svg
        viewBox="0 0 620 340"
        className="h-auto w-full text-landing-border"
        role="img"
        aria-label="A force-layout map connecting regulations, requirements, controls, evidence, and risks"
      >
        {RAW_EDGES.map(([a, b]) => {
          const from = NODE_BY_ID.get(a)!;
          const to = NODE_BY_ID.get(b)!;
          return (
            <line
              key={`${a}-${b}`}
              x1={from.x}
              y1={from.y}
              x2={to.x}
              y2={to.y}
              stroke="currentColor"
              strokeWidth={1}
            />
          );
        })}
        {NODES.map((node) => (
          <g key={node.id} data-node-id={node.id}>
            <circle cx={node.x} cy={node.y} r={5} className={DOT_CLASS[node.type]} />
            <text
              x={node.x}
              y={node.y - 11}
              textAnchor="middle"
              className="fill-landing-fg/60"
              style={{ fontSize: 9.5, letterSpacing: "0.03em" }}
            >
              {node.label}
            </text>
          </g>
        ))}
        {/* Rendered inside this same <svg>/viewBox — not a second,
            separately-positioned overlay element — so callers extending
            the map (e.g. SectionChange's "new requirement" node) never
            have to fight a coordinate-system mismatch against this
            component's own legend/wrapper sizing. */}
        {overlay}
      </svg>
      <div className="mt-4 flex flex-wrap items-center justify-center gap-x-6 gap-y-2">
        {LEGEND.map((item) => (
          <span
            key={item.label}
            className="inline-flex items-center gap-1.5 text-xs text-landing-fg/60"
          >
            <svg width="8" height="8">
              <circle cx="4" cy="4" r="4" className={DOT_CLASS[item.type]} />
            </svg>
            {item.label}
          </span>
        ))}
      </div>
    </div>
  );
}
