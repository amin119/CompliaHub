import Link from "next/link";
import Eyebrow from "./Eyebrow";
import Reveal from "@/components/landing/Reveal";

const BADGE_TINTS = [
  "bg-accent-soft text-accent",
  "bg-[color-mix(in_srgb,var(--purple)_18%,transparent)] text-[var(--purple)]",
  "bg-[color-mix(in_srgb,var(--pink)_45%,transparent)] text-accent",
];

const USE_CASES = [
  {
    title: "Regulatory research",
    body: "Find the requirement buried three clauses deep — not just the document that happens to mention it.",
    tags: ["#ISO27001", "#GDPR"],
    icon: (
      <>
        <rect x="4" y="3" width="11" height="14" rx="1.5" fill="currentColor" fillOpacity="0.18" />
        <path d="M7 7h5M7 10h5M7 13h3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
        <circle cx="16" cy="16" r="4" fill="currentColor" fillOpacity="0.18" stroke="currentColor" strokeWidth="1.6" />
        <path d="m19.2 19.2 2.3 2.3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </>
    ),
  },
  {
    title: "Gap analysis",
    body: "See what one standard requires that another doesn't, across your own ingested corpus.",
    tags: ["#ISO42001", "#ISO27001"],
    icon: (
      <>
        <rect x="3" y="5" width="10" height="13" rx="2" fill="currentColor" fillOpacity="0.16" />
        <rect x="11" y="7" width="10" height="13" rx="2" fill="currentColor" fillOpacity="0.32" />
        <path d="M11 9v9" stroke="currentColor" strokeWidth="1.4" strokeDasharray="1 2.4" strokeLinecap="round" />
      </>
    ),
  },
  {
    title: "Relationship mapping",
    body: "Trace how a control, a risk, and a requirement connect across separate documents.",
    tags: ["#Control", "#Risk"],
    icon: (
      <>
        <path d="M7 7 12 17 17 7" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="7" cy="7" r="3" fill="currentColor" fillOpacity="0.25" stroke="currentColor" strokeWidth="1.4" />
        <circle cx="17" cy="7" r="3" fill="currentColor" fillOpacity="0.25" stroke="currentColor" strokeWidth="1.4" />
        <circle cx="12" cy="18" r="3" fill="currentColor" fillOpacity="0.5" stroke="currentColor" strokeWidth="1.4" />
      </>
    ),
  },
  {
    title: "Audit preparation",
    body: "Go from a plain-language question to the exact clause an auditor would ask you to produce.",
    tags: ["#Evidence", "#Audit"],
    icon: (
      <>
        <rect x="5" y="4" width="14" height="17" rx="2" fill="currentColor" fillOpacity="0.16" />
        <rect x="8.5" y="2.5" width="7" height="3.5" rx="1" fill="currentColor" fillOpacity="0.4" />
        <path d="m8.5 13 2.6 2.6L16 10" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
      </>
    ),
  },
  {
    title: "Risk identification",
    body: "Discover where a control is missing before an auditor does.",
    tags: ["#Risk", "#Control"],
    icon: (
      <>
        <path
          d="M12 2.5 20 6v6c0 5-3.4 8.3-8 9.5C7.4 20.3 4 17 4 12V6l8-3.5Z"
          fill="currentColor"
          fillOpacity="0.2"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
        <path d="M12 8v5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <circle cx="12" cy="16" r="1.1" fill="currentColor" />
      </>
    ),
  },
  {
    title: "Compliance assessment",
    body: "Understand where your organization stands against a given standard, right now.",
    tags: ["#GDPR", "#Assessment"],
    icon: (
      <>
        <circle cx="12" cy="10" r="6.5" fill="currentColor" fillOpacity="0.2" stroke="currentColor" strokeWidth="1.5" />
        <path d="m9.2 10 1.9 1.9L15 8" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
        <path d="m8.5 15.5-1.7 5.5 5.2-2.4 5.2 2.4-1.7-5.5" fill="currentColor" fillOpacity="0.3" strokeLinejoin="round" />
      </>
    ),
  },
];

/**
 * Matches the reference design's "Popular Jobs" card grid — same 2x3 card
 * layout, icon/title/description/tags/two-buttons pattern — with content
 * that fits this platform instead of job listings. Both card buttons are
 * real, working links into `/chat`, not a fake "read qualifications" flow.
 *
 * Icons are duotone (a filled base shape plus a stroked/filled detail
 * layer) rather than plain thin outlines, and each card's badge rotates
 * through the palette's three accent tones so the grid doesn't read as
 * six identical blue circles.
 */
export default function SectionUseCases() {
  return (
    <section id="use-cases" className="mx-auto w-full max-w-6xl px-4 py-20 sm:px-8">
      <Reveal className="mb-12 text-center">
        <Eyebrow>Use cases</Eyebrow>
        <h2 className="font-display mt-3 text-3xl leading-tight font-bold text-foreground sm:text-4xl">
          Real questions, real answers
        </h2>
      </Reveal>
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {USE_CASES.map((useCase, i) => (
          <Reveal key={useCase.title} delay={(i % 3) * 0.08}>
            <div className="flex h-full flex-col rounded-3xl border border-surface-border bg-surface p-6 shadow-sm">
              <span
                className={`mb-4 flex h-11 w-11 items-center justify-center rounded-full ${BADGE_TINTS[i % BADGE_TINTS.length]}`}
              >
                <svg viewBox="0 0 24 24" fill="none" className="h-5.5 w-5.5">
                  {useCase.icon}
                </svg>
              </span>
              <h3 className="text-base font-bold text-foreground">{useCase.title}</h3>
              <p className="mt-2 flex-1 text-sm leading-relaxed text-muted">{useCase.body}</p>
              <div className="mt-4 flex flex-wrap gap-1.5">
                {useCase.tags.map((tag) => (
                  <span
                    key={tag}
                    className="rounded-full bg-surface px-2.5 py-1 text-[11px] text-muted"
                  >
                    {tag}
                  </span>
                ))}
              </div>
              <div className="mt-5 flex items-center gap-4 border-t border-surface-border pt-4">
                <Link
                  href="/chat"
                  className="rounded-full border border-accent px-4 py-1.5 text-xs font-semibold text-accent transition-colors hover:bg-accent hover:text-white"
                >
                  Ask now
                </Link>
                <a
                  href="#showcase"
                  className="text-xs font-semibold text-muted transition-colors hover:text-foreground"
                >
                  See example
                </a>
              </div>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}
