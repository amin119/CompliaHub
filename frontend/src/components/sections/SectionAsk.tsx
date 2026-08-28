import Link from "next/link";
import Eyebrow from "./Eyebrow";
import BrowserFrame from "@/components/landing/BrowserFrame";
import DemoCitation from "@/components/landing/DemoCitation";

const DEMO_STAGES = [
  "Searching…",
  "Retrieving relevant clauses…",
  "Cross-checking internal policy…",
  "Grounding the answer…",
];

const RETENTION_CITATIONS = [
  {
    label: "Article 5(1)(e) · GDPR (EU) 2016/679",
    title: "GDPR (EU) 2016/679",
    excerpt:
      "Personal data shall be kept in a form which permits identification of data subjects for no longer than is necessary for the purposes for which the personal data are processed.",
  },
  {
    label: "4.2 · retention-policy.pdf",
    title: "retention-policy.pdf",
    excerpt:
      "All customer records are retained for a period of 24 months from last activity, across all data categories.",
  },
];

/**
 * Brief section 6, SectionAsk: "reuse the real conversational interface
 * (framed) as the proof-of-concept." Same disclosed approach as
 * SectionIngestion — built from `/chat`'s own real bubble/citation
 * classes and copy, no real screenshot available yet.
 */
export default function SectionAsk() {
  return (
    <section className="font-landing-sans mx-auto w-full max-w-6xl px-4 pb-28 sm:px-8">
      <div className="grid gap-14 lg:grid-cols-[0.85fr_1.15fr] lg:items-center lg:gap-20">
        <div>
          <Eyebrow>Ask the labyrinth</Eyebrow>
          <h2 className="font-landing-serif mt-4 text-3xl leading-tight font-normal text-landing-fg sm:text-4xl">
            Ask a question. Follow the evidence.
          </h2>
          <p className="mt-5 leading-relaxed text-landing-fg/70">
            &ldquo;Are our current data retention policies aligned with the latest
            requirements?&rdquo; Every stage of that search streams back as it happens, before
            the answer itself streams in.
          </p>
          <Link
            href="/chat"
            className="mt-6 inline-block border-b border-landing-accent pb-0.5 text-sm font-medium text-landing-accent transition-opacity hover:opacity-70"
          >
            Open the conversation →
          </Link>
        </div>
        <BrowserFrame path="/chat">
          <div className="flex flex-col gap-3">
            <div className="ml-auto max-w-[80%] rounded-2xl rounded-br-md bg-landing-accent px-4 py-2.5 text-sm text-landing-accent-fg">
              Are our current data retention policies aligned with the latest requirements?
            </div>
            <div className="mr-auto flex flex-col gap-1 rounded-2xl rounded-bl-md bg-landing-surface px-4 py-2.5 text-xs text-landing-fg/60">
              {DEMO_STAGES.map((stage) => (
                <span key={stage} className="flex items-center gap-2">
                  <span className="h-1 w-1 rounded-full bg-landing-accent" />
                  {stage}
                </span>
              ))}
            </div>
            <div className="mr-auto max-w-[90%] rounded-2xl rounded-bl-md bg-landing-surface px-4 py-2.5 text-sm text-landing-fg">
              Article 5(1)(e) limits storage to what&apos;s necessary for the stated purpose.
              Your policy applies a blanket 24-month window that isn&apos;t clearly tied to a
              documented purpose per category.
              <div className="mt-2.5 flex flex-wrap gap-1.5 border-t border-landing-border/60 pt-2.5">
                {RETENTION_CITATIONS.map((citation) => (
                  <DemoCitation key={citation.label} {...citation} />
                ))}
              </div>
            </div>
          </div>
        </BrowserFrame>
      </div>
    </section>
  );
}
