import Link from "next/link";
import Reveal from "@/components/landing/Reveal";
import RevealText from "@/components/landing/RevealText";

/**
 * The jobs people actually bring here, three per half of the product.
 * Deliberately an editorial list with hairline rules and alternating indent
 * rather than a 2x3 grid of identical cards — six matching rounded cards
 * with the same shadow is the layout this design is trying to get away from.
 *
 * Every row links to the real route that does the job.
 */

const USE_CASES = [
  {
    half: "Ask",
    title: "Answer an auditor's question, with the clause attached",
    body: "Ask in plain language and get back the requirement plus the exact text it came from.",
    href: "/chat",
    action: "Ask a question",
  },
  {
    half: "Ask",
    title: "Find what one standard requires that another doesn't",
    body: "Cross-standard gap analysis across the documents you've ingested, not a generic checklist.",
    href: "/chat",
    action: "Ask a question",
  },
  {
    half: "Ask",
    title: "Trace how a control, a risk and a requirement connect",
    body: "Multi-hop questions that follow relationships across separate documents.",
    href: "/chat",
    action: "Ask a question",
  },
  {
    half: "Scan",
    title: "Check a repo against ISO 27001 before you ship",
    body: "Findings mapped to real Annex A controls, with the file and line that triggered each one.",
    href: "/scanner",
    action: "Scan a repo",
  },
  {
    half: "Scan",
    title: "Find the weak crypto before an auditor does",
    body: "Deterministic rules catch secrets, weak hashing and insecure config with no LLM in the loop.",
    href: "/scanner",
    action: "Scan a repo",
  },
  {
    half: "Scan",
    title: "Hand over a report instead of a spreadsheet",
    body: "A printable evidence report showing what was found, what was fixed, and who reviewed it.",
    href: "/scanner",
    action: "Scan a repo",
  },
];

export default function SectionUseCases() {
  return (
    <section
      id="use-cases"
      className="mx-auto w-full max-w-7xl scroll-mt-24 px-4 py-20 sm:px-8 sm:py-24"
    >
      <div className="max-w-3xl">
        <RevealText as="h2" className="font-display text-h2 font-semibold text-foreground">
          What people actually come here to do.
        </RevealText>
      </div>

      <ul className="mt-12 border-t border-surface-border">
        {USE_CASES.map((useCase, index) => (
          <li key={useCase.title} className="border-b border-surface-border">
            <Reveal
              delay={(index % 3) * 0.05}
              className={`flex flex-col gap-4 py-8 md:flex-row md:items-baseline md:gap-10 ${
                index % 2 === 1 ? "md:pl-[8%]" : ""
              }`}
            >
              <span className="font-display shrink-0 text-sm text-muted md:w-16">
                {String(index + 1).padStart(2, "0")}
              </span>
              <div className="flex-1">
                <h3 className="font-display text-xl leading-snug font-semibold text-foreground sm:text-2xl">
                  {useCase.title}
                </h3>
                <p className="measure mt-2 text-sm leading-relaxed text-muted">{useCase.body}</p>
              </div>
              <Link
                href={useCase.href}
                data-cursor={useCase.half}
                className="shrink-0 text-sm font-medium text-accent transition-opacity hover:opacity-70"
              >
                {useCase.action}
              </Link>
            </Reveal>
          </li>
        ))}
      </ul>
    </section>
  );
}
