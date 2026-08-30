import Link from "next/link";
import Reveal from "@/components/landing/Reveal";

const STANDARDS = [
  { code: "27001", label: "ISO 27001", position: "top-8 left-6 -rotate-12 sm:left-14" },
  { code: "42001", label: "ISO 42001", position: "top-10 right-6 rotate-12 sm:right-14" },
  { code: "GDPR", label: "GDPR", position: "bottom-10 left-10 rotate-6 sm:left-24" },
];

/**
 * The reference design scatters little face-avatar icons around this
 * headline and closes with Google Play / App Store badges — this platform
 * has no mobile app, so the avatars are replaced with small badges naming
 * the standards CompliaHub can actually answer questions about, and the
 * two real routes replace the store badges. The badges name the
 * *standards*, not a claim that the platform itself is certified against
 * them — an important distinction this project has been careful about
 * throughout (no fabricated certifications).
 */
export default function SectionFinalCta() {
  return (
    <section className="mx-auto w-full max-w-4xl px-4 pb-20 sm:px-8">
      <Reveal className="bg-surface-blue relative overflow-hidden rounded-3xl px-6 py-16 text-center">
        {STANDARDS.map((standard) => (
          <StandardBadge key={standard.code} {...standard} />
        ))}

        <h2 className="font-display relative mx-auto max-w-lg text-3xl leading-tight font-bold text-foreground sm:text-4xl">
          Get ready to navigate compliance with confidence
        </h2>
        <p className="relative mx-auto mt-4 max-w-md text-sm text-muted">
          Upload your standards for free and start asking real compliance questions today.
        </p>
        <div className="relative mt-8 flex flex-wrap items-center justify-center gap-4">
          <Link
            href="/chat"
            className="rounded-full bg-cta px-7 py-3.5 text-sm font-semibold text-white shadow-sm transition-transform hover:scale-105"
          >
            Explore the platform
          </Link>
          <Link
            href="/documents"
            className="rounded-full border border-surface-border bg-surface px-7 py-3.5 text-sm font-semibold text-foreground transition-colors hover:border-accent hover:text-accent"
          >
            Upload a standard
          </Link>
        </div>
      </Reveal>
    </section>
  );
}

function StandardBadge({ code, label, position }: { code: string; label: string; position: string }) {
  return (
    <span
      aria-hidden="true"
      className={`absolute hidden h-14 w-14 flex-col items-center justify-center rounded-2xl bg-surface text-center shadow-sm sm:flex ${position}`}
      title={label}
    >
      <span className="text-[10px] font-bold tracking-tight text-accent">{code}</span>
      <span className="mt-0.5 h-1 w-5 rounded-full bg-cta" />
    </span>
  );
}
