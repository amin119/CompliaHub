import Eyebrow from "./Eyebrow";
import Reveal from "@/components/landing/Reveal";

const CHECKLIST = [
  "Every answer traces back to its source clause",
  "Cross-standard mapping across ISO and GDPR",
  "The right context for every question",
];

const CARDS = [
  {
    clause: "Clause 8.2 · ISO 27001",
    excerpt:
      "The organization shall perform information security risk assessments at planned intervals.",
    tags: ["#RiskAssessment", "#ISO27001", "#Evidence"],
    rotate: "-rotate-3",
    offset: "top-0 left-0",
  },
  {
    clause: "Clause 6.1.2 · ISO 42001",
    excerpt:
      "The organization shall define and apply an AI risk assessment process throughout the system lifecycle.",
    tags: ["#AIRisk", "#ISO42001"],
    rotate: "rotate-2",
    offset: "top-8 left-10",
  },
  {
    clause: "Article 32 · GDPR",
    excerpt:
      "Appropriate technical and organisational measures to ensure a level of security appropriate to the risk.",
    tags: ["#GDPR", "#Security"],
    rotate: "-rotate-1",
    offset: "top-16 left-4",
  },
];

function CheckIcon() {
  return (
    <span className="bg-cta flex h-6 w-6 shrink-0 items-center justify-center rounded-full">
      <svg viewBox="0 0 20 20" fill="none" className="h-3 w-3">
        <path
          d="m4 10 4 4 8-8"
          stroke="white"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  );
}

function EvidenceCard({ card, className }: { card: (typeof CARDS)[number]; className?: string }) {
  return (
    <div
      className={`absolute w-64 rounded-3xl border border-surface-border bg-surface p-5 shadow-lg sm:w-72 ${card.rotate} ${card.offset} ${className ?? ""}`}
    >
      <div className="flex items-start justify-between">
        <p className="text-sm font-semibold text-foreground">{card.clause}</p>
        <span className="text-muted">×</span>
      </div>
      <p className="mt-2 text-xs leading-relaxed text-muted">&ldquo;{card.excerpt}&rdquo;</p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {card.tags.map((tag) => (
          <span key={tag} className="rounded-full bg-surface px-2.5 py-1 text-[11px] text-muted">
            {tag}
          </span>
        ))}
      </div>
      <div className="mt-4 flex items-center gap-2 border-t border-surface-border pt-3">
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-100 text-emerald-600">
          <svg viewBox="0 0 20 20" fill="none" className="h-3 w-3">
            <path
              d="m4 10 4 4 8-8"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </span>
        <span className="text-xs font-medium text-foreground">Verified source</span>
      </div>
    </div>
  );
}

/**
 * Matches the reference design's split "showcase" section: a floating,
 * messily-overlapped card stack on one side, an eyebrow + headline +
 * checklist on the other. The reference stacks 2-3 mockup cards at
 * varied rotations/offsets rather than cleanly side by side — reproduced
 * here with 3 real evidence cards (one per supported standard: ISO 27001,
 * ISO 42001, GDPR) instead of the reference's job-notification mockups.
 */
export default function SectionShowcase() {
  return (
    <section id="showcase" className="mx-auto w-full max-w-6xl px-4 py-20 sm:px-8">
      <div className="grid items-center gap-16 lg:grid-cols-2">
        <Reveal className="relative mx-auto h-96 w-full max-w-sm sm:h-[26rem]">
          <EvidenceCard card={CARDS[0]} className="z-10" />
          <EvidenceCard card={CARDS[1]} className="z-20" />
          <EvidenceCard card={CARDS[2]} className="z-30" />
        </Reveal>

        <Reveal delay={0.1}>
          <Eyebrow>Showcase</Eyebrow>
          <h2 className="font-display mt-3 text-3xl leading-tight font-bold text-foreground sm:text-4xl">
            Find answers easily and quickly with CompliaHub
          </h2>
          <p className="mt-4 text-base leading-relaxed text-muted">
            Now you can find a grounded answer quickly and easily. CompliaHub also shows
            exactly which clause it came from.
          </p>
          <ul className="mt-6 flex flex-col gap-3">
            {CHECKLIST.map((item) => (
              <li key={item} className="flex items-center gap-3 text-sm text-foreground">
                <CheckIcon />
                {item}
              </li>
            ))}
          </ul>
        </Reveal>
      </div>
    </section>
  );
}
