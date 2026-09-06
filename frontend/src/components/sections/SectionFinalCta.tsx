import MagneticLink from "@/components/landing/MagneticLink";
import MaskedLines from "@/components/landing/MaskedLines";
import Reveal from "@/components/landing/Reveal";
import MarkSweep from "@/components/landing/MarkSweep";
import { buttonClasses } from "@/lib/ui";

/**
 * The close. One of only two places on the page that gets the ambient glow
 * (the other is the hero), and the last chance to make the Scan half
 * visible — so it closes on two CTAs, one per half of the product, rather
 * than the single "Explore the platform" button that used to be here.
 *
 * The three standards named below are the ones CompliaHub can actually
 * answer questions about. They name the *standards*, never a claim that the
 * platform is certified against them.
 */

const STANDARDS = ["ISO 27001", "ISO 42001", "GDPR"];

export default function SectionFinalCta() {
  return (
    <section className="relative overflow-hidden px-4 py-24 sm:px-8 sm:py-32">
      <div
        aria-hidden="true"
        className="bg-ambient-glow pointer-events-none absolute inset-0 -z-10"
      />

      <div className="mx-auto max-w-5xl text-center">
        <MaskedLines
          as="h2"
          className="font-display text-h1 font-semibold text-foreground"
          lines={["Stop guessing.", <MarkSweep key="citing">Start citing.</MarkSweep>]}
        />

        <Reveal>
          <p className="measure text-lead mx-auto mt-8 text-muted">
            Upload your standards, ask the questions you&rsquo;d otherwise ask a consultant, and
            point the scanner at the code you&rsquo;re about to ship.
          </p>
        </Reveal>

        <Reveal delay={0.08}>
          <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
            <MagneticLink href="/chat" cursorLabel="Ask" className={buttonClasses({ size: "lg" })}>
              Ask a question
            </MagneticLink>
            <MagneticLink
              href="/scanner"
              cursorLabel="Scan"
              className={buttonClasses({ variant: "secondary", size: "lg" })}
            >
              Scan a repo
            </MagneticLink>
          </div>
        </Reveal>

        <Reveal delay={0.12}>
          <div className="mt-12 flex flex-wrap items-center justify-center gap-x-8 gap-y-3 border-t border-surface-border pt-8">
            {STANDARDS.map((standard) => (
              <span key={standard} className="font-display text-lg font-semibold text-muted">
                {standard}
              </span>
            ))}
          </div>
        </Reveal>
      </div>
    </section>
  );
}
