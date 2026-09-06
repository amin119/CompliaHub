import Reveal from "@/components/landing/Reveal";
import MaskedLines from "@/components/landing/MaskedLines";
import MarkSweep from "@/components/landing/MarkSweep";

/**
 * How the retrieval actually works, and why the answers can cite anything at
 * all. The three strategies named here are the three the backend really runs
 * (see docs/phase-2-vector-layer.md and docs/phase-4-graph-retrieval.md) —
 * not a marketing number.
 *
 * The evidence cards are a deliberately messy, overlapping stack rather than
 * a tidy row: three real clauses, one per supported standard.
 */

const STRATEGIES = [
  {
    name: "Vector search",
    body: "Finds clauses that mean the same thing as your question, not just ones that share its words.",
  },
  {
    name: "Graph traversal",
    body: "Follows the relationships between controls, risks and requirements across separate documents.",
  },
  {
    name: "Agentic retrieval",
    body: "For broad questions, it plans, retrieves, critiques its own evidence, and searches again if it falls short.",
  },
];

const CARDS = [
  {
    clause: "ISO 27001 — Clause 8.2",
    excerpt:
      "The organization shall perform information security risk assessments at planned intervals.",
    tags: ["Risk assessment", "Evidence"],
    position: "left-0 top-0 -rotate-3",
  },
  {
    clause: "ISO 42001 — Clause 6.1.2",
    excerpt:
      "The organization shall define and apply an AI risk assessment process throughout the system lifecycle.",
    tags: ["AI risk"],
    position: "left-10 top-28 rotate-2",
  },
  {
    clause: "GDPR — Article 32",
    excerpt:
      "Appropriate technical and organisational measures to ensure a level of security appropriate to the risk.",
    tags: ["Security"],
    position: "left-4 top-56 -rotate-1",
  },
];

export default function SectionShowcase() {
  return (
    <section
      id="showcase"
      className="mx-auto w-full max-w-7xl scroll-mt-24 px-4 py-20 sm:px-8 sm:py-24"
    >
      <div className="grid items-center gap-16 lg:grid-cols-2">
        <Reveal className="relative mx-auto h-[30rem] w-full max-w-sm">
          {CARDS.map((card, index) => (
            <div
              key={card.clause}
              style={{ zIndex: index + 1 }}
              className={`absolute w-72 rounded-3xl border border-surface-border bg-surface-raised p-5 shadow-[0_24px_60px_-32px_rgba(20,16,25,0.5)] ${card.position}`}
            >
              <p className="text-sm font-semibold text-foreground">{card.clause}</p>
              <p className="mt-2 text-xs leading-relaxed text-muted">
                &ldquo;{card.excerpt}&rdquo;
              </p>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {card.tags.map((tag) => (
                  <span
                    key={tag}
                    className="rounded-full bg-surface px-2.5 py-1 text-[11px] text-muted"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </Reveal>

        <div>
          <MaskedLines
            as="h2"
            className="font-display text-h2 font-semibold text-foreground"
            lines={[
              "Three ways to find",
              <MarkSweep key="answer">one answer.</MarkSweep>,
            ]}
          />
          <Reveal>
            <p className="measure text-lead mt-6 text-muted">
              A question about a single clause and a question spanning three standards need
              different retrieval. CompliaHub classifies each one and routes it to the cheapest
              strategy that can actually answer it.
            </p>
          </Reveal>
          <Reveal delay={0.08}>
            <ul className="mt-8 flex flex-col divide-y divide-surface-border border-y border-surface-border">
              {STRATEGIES.map((strategy) => (
                <li key={strategy.name} className="py-4">
                  <p className="font-display text-base font-semibold text-foreground">
                    {strategy.name}
                  </p>
                  <p className="mt-1 text-sm leading-relaxed text-muted">{strategy.body}</p>
                </li>
              ))}
            </ul>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
