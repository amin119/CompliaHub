import BrowserFrame from "@/components/landing/BrowserFrame";
import DemoCitation from "@/components/landing/DemoCitation";
import AnimatedConversation from "@/components/landing/AnimatedConversation";
import MagneticLink from "@/components/landing/MagneticLink";
import RevealText from "@/components/landing/RevealText";
import Reveal from "@/components/landing/Reveal";
import { buttonClasses } from "@/lib/ui";

/**
 * The Ask half. Text-led on the left, a live-styled preview on the right —
 * the reference design's own "video demo" slot was a placeholder linking to
 * nothing, so this shows the real interface instead, with the messages
 * staggering in so it reads as an exchange rather than a screenshot.
 *
 * Every claim in the list is a capability the product actually has.
 */

const POINTS = [
  {
    title: "Answers stream as they're written",
    body: "Server-sent events, so you watch the answer form instead of staring at a spinner.",
  },
  {
    title: "Every claim cites its clause",
    body: "Citation chips open the real clause text from your own ingested standards.",
  },
  {
    title: "The retrieval is inspectable",
    body: "See which entities and relationships the answer was actually built from.",
  },
];

export default function SectionDemo() {
  return (
    <section className="mx-auto w-full max-w-7xl px-4 py-20 sm:px-8 sm:py-24">
      <div className="grid items-center gap-12 lg:grid-cols-2 lg:gap-16">
        <div>
          <RevealText as="h2" className="font-display text-h2 font-semibold text-foreground">
            Ask it like you&rsquo;d ask a colleague.
          </RevealText>
          <Reveal>
            <p className="measure text-lead mt-6 text-muted">
              Plain-language questions about ISO 27001, ISO 42001 and GDPR, answered from the
              standards you&rsquo;ve ingested — with the clause it came from attached.
            </p>
          </Reveal>

          <Reveal delay={0.08}>
            <ul className="mt-8 flex flex-col gap-5">
              {POINTS.map((point) => (
                <li key={point.title} className="border-l-2 border-surface-border pl-4">
                  <p className="font-medium text-foreground">{point.title}</p>
                  <p className="mt-1 text-sm leading-relaxed text-muted">{point.body}</p>
                </li>
              ))}
            </ul>
          </Reveal>

          <Reveal delay={0.12}>
            <MagneticLink
              href="/chat"
              cursorLabel="Ask"
              className={buttonClasses({ size: "lg", className: "mt-9" })}
            >
              Ask a question
            </MagneticLink>
          </Reveal>
        </div>

        <Reveal delay={0.1}>
          <BrowserFrame path="compliahub.app/chat">
            <AnimatedConversation className="flex flex-col gap-3 py-2">
              <div className="ml-auto max-w-[80%] rounded-3xl rounded-br-md bg-cta px-4 py-2.5 text-sm text-accent-contrast">
                What controls satisfy GDPR Article 32?
              </div>
              <div className="mr-auto flex items-center gap-2 rounded-3xl rounded-bl-md bg-surface px-4 py-2 text-xs text-muted">
                <span className="h-1.5 w-1.5 rounded-full bg-accent motion-safe:animate-pulse" />
                Retrieving evidence
              </div>
              <div className="mr-auto max-w-[88%] rounded-3xl rounded-bl-md border border-surface-border bg-surface px-4 py-2.5 text-sm text-foreground">
                Article 32 requires &ldquo;appropriate technical and organisational measures&rdquo;
                proportionate to risk, including encryption, resilience, and regular testing.
                <div className="mt-2.5 flex flex-wrap gap-1.5 border-t border-surface-border pt-2.5">
                  <DemoCitation
                    label="GDPR Article 32"
                    title="GDPR (EU) 2016/679"
                    excerpt="Taking into account the state of the art... the controller and processor shall implement appropriate technical and organisational measures to ensure a level of security appropriate to the risk."
                  />
                  <DemoCitation
                    label="ISO 27001 A.8.24"
                    title="ISO/IEC 27001:2022 — Annex A"
                    excerpt="Rules for the effective use of cryptography, including key management, shall be defined and implemented."
                  />
                </div>
              </div>
            </AnimatedConversation>
          </BrowserFrame>
        </Reveal>
      </div>
    </section>
  );
}
