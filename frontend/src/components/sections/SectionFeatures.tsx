import Reveal from "@/components/landing/Reveal";
import RevealText from "@/components/landing/RevealText";

/**
 * A bento grid rather than a row of identical cards: tiles are deliberately
 * different sizes so the eye has somewhere to go, and each one is tagged
 * with which half of the product it belongs to — that tag encodes real
 * structure (Ask / Scan / both), which is the only reason a small label
 * survives in this design at all.
 *
 * Every tile is a capability that exists today. Nothing aspirational.
 */

type Tile = {
  half: "Ask" | "Scan" | "Both";
  title: string;
  body: string;
  span?: string;
};

const TILES: Tile[] = [
  {
    half: "Ask",
    title: "Answers that cite their source",
    body: "Every claim carries the clause it came from, and one click opens the real text of that clause from your own ingested standard.",
    span: "md:col-span-2",
  },
  {
    half: "Ask",
    title: "An inspectable evidence graph",
    body: "See the entities and relationships an answer was actually built from.",
  },
  {
    half: "Scan",
    title: "Audit a whole repository",
    body: "Upload a .zip and get security, GDPR and AI-governance findings, each pinned to a real file and line.",
    span: "md:col-span-2",
  },
  {
    half: "Ask",
    title: "Conversations that continue",
    body: "Follow-up questions keep their context, and past conversations can be reopened.",
  },
  {
    half: "Scan",
    title: "Mapped to ISO 27001",
    body: "Findings land on real Annex A control IDs, not a vague category.",
  },
  {
    half: "Scan",
    title: "AI that suggests, never decides",
    body: "It validates a finding against your standards and can draft a diff — but it cannot mark anything compliant.",
  },
  {
    half: "Scan",
    title: "Only a human verifies",
    body: "Verified status requires a person and a written justification, recorded as an audit trail.",
  },
  {
    half: "Scan",
    title: "Printable evidence reports",
    body: "Severity, status and framework coverage in a report that survives being printed — with no invented compliance score anywhere in it.",
    span: "md:col-span-2",
  },
  {
    half: "Both",
    title: "Light, dark, keyboard, print",
    body: "One design system, two themes, reduced-motion honoured throughout.",
  },
];

export default function SectionFeatures() {
  return (
    <section
      id="features"
      className="mx-auto w-full max-w-7xl scroll-mt-24 px-4 py-20 sm:px-8 sm:py-24"
    >
      <div className="max-w-3xl">
        <RevealText as="h2" className="font-display text-h2 font-semibold text-foreground">
          Two halves of the same job.
        </RevealText>
        <Reveal>
          <p className="measure text-lead mt-6 text-muted">
            One side answers questions about the standards. The other checks your code against
            them. Both refuse to claim anything they can&rsquo;t show you the evidence for.
          </p>
        </Reveal>
      </div>

      <div className="mt-12 grid gap-4 md:grid-cols-3">
        {TILES.map((tile, index) => (
          <Reveal key={tile.title} delay={(index % 3) * 0.06} className={tile.span}>
            <div className="card-interactive flex h-full flex-col rounded-3xl border border-surface-border bg-surface p-6">
              <span
                className={`mb-4 w-fit rounded-full px-2.5 py-0.5 text-[11px] font-medium ${
                  tile.half === "Scan"
                    ? "bg-mark-soft text-foreground"
                    : tile.half === "Ask"
                      ? "bg-accent-soft text-accent"
                      : "bg-surface-raised text-muted"
                }`}
              >
                {tile.half}
              </span>
              <h3 className="font-display text-lg leading-snug font-semibold text-foreground">
                {tile.title}
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-muted">{tile.body}</p>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}
