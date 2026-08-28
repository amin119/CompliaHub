import Link from "next/link";
import Eyebrow from "./Eyebrow";
import BrowserFrame from "@/components/landing/BrowserFrame";

/**
 * Brief section 6, SectionIngestion: "use the existing upload interface as
 * proof — do not redesign the actual upload UI." No real screenshot was
 * provided, so this mockup is built from `/documents`'s own real classes/
 * copy (dropzone, status badge) rather than a fabricated UI — same
 * disclosed approach used since Phase 6 Part 1. Framed in `BrowserFrame`
 * with the real route shown in its address bar.
 */
export default function SectionIngestion() {
  return (
    <section className="font-landing-sans mx-auto w-full max-w-6xl px-4 py-28 sm:px-8">
      <div className="grid gap-14 lg:grid-cols-[0.85fr_1.15fr] lg:items-center lg:gap-20">
        <div>
          <Eyebrow>From documents to intelligence</Eyebrow>
          <h2 className="font-landing-serif mt-4 text-3xl leading-tight font-normal text-landing-fg sm:text-4xl">
            Every document becomes part of the map.
          </h2>
          <p className="mt-5 leading-relaxed text-landing-fg/70">
            A regulation. A policy. A standard. An internal document. Uploaded once, parsed
            clause by clause, and woven into the same graph every question is answered from.
          </p>
          <Link
            href="/documents"
            className="mt-6 inline-block border-b border-landing-accent pb-0.5 text-sm font-medium text-landing-accent transition-opacity hover:opacity-70"
          >
            Upload a standard →
          </Link>
        </div>
        <BrowserFrame path="/documents">
          <div className="flex flex-col items-center justify-center gap-2 rounded-sm border-2 border-dashed border-landing-border p-8 text-sm text-landing-fg/50">
            <svg viewBox="0 0 24 24" fill="none" className="h-6 w-6">
              <path
                d="M12 16V4m0 0 4 4m-4-4-4 4M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"
                stroke="currentColor"
                strokeWidth="1.4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            Drop a PDF or DOCX standard
          </div>
          <div className="mt-4 flex items-center justify-between rounded-sm border border-landing-border px-4 py-3 text-sm">
            <span className="text-landing-fg">iso-27001-2022.pdf</span>
            <span className="inline-flex items-center gap-1.5 text-xs text-landing-olive">
              <span className="h-1.5 w-1.5 rounded-full bg-current" />
              ready
            </span>
          </div>
        </BrowserFrame>
      </div>
    </section>
  );
}
