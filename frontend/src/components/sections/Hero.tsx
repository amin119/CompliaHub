"use client";

import { useRef } from "react";
import { useGSAP } from "@gsap/react";
import MagneticLink from "@/components/landing/MagneticLink";
import MarkSweep from "@/components/landing/MarkSweep";
import MaskedLines from "@/components/landing/MaskedLines";
import SplitPreview from "@/components/landing/SplitPreview";
import { MOTION, gsap, prefersReducedMotion } from "@/lib/gsap";
import { buttonClasses } from "@/lib/ui";

/**
 * The one orchestrated load sequence on the site. Everything else reveals on
 * scroll.
 *
 * Beat 1: the headline's two lines slide out from their masks.
 * Beat 2: the highlighter draws across "Scan hard code." (`MarkSweep`).
 * Beat 3: the sub, the CTAs, then the product shot settle in.
 *
 * `.hero-reveal` marks the elements that genuinely fade from 0 → 1, so a
 * test asserting `opacity: 1` on one of them is asserting the sequence
 * actually ran rather than just that the page loaded. Under
 * `prefers-reduced-motion` every element is set to its final state
 * immediately and no tween is created.
 *
 * Type-led and left-aligned rather than a centred stack: the headline is the
 * hero visual, and it names both halves of the product in one idea —
 * previously the entire marketing page only ever described the Ask half.
 */
export default function Hero() {
  const containerRef = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      const items = gsap.utils.toArray<HTMLElement>(".hero-reveal");

      if (prefersReducedMotion()) {
        gsap.set(items, { opacity: 1, y: 0 });
        return;
      }

      gsap.from(items, {
        opacity: 0,
        y: 20,
        duration: MOTION.durSlow,
        ease: MOTION.easeOut,
        stagger: 0.05,
        // Overlaps the tail of the headline reveal rather than waiting for
        // it, so the whole sequence reads as one movement and finishes
        // inside the 1.2s budget (0.25 + 0.10 stagger + 0.8 = 1.15s).
        delay: 0.25,
      });
    },
    { scope: containerRef },
  );

  return (
    <section
      ref={containerRef}
      className="relative overflow-hidden px-4 pt-16 pb-20 sm:px-8 sm:pt-24 sm:pb-28"
    >
      {/* One of only two ambient glows on the page (the other closes it).
          Everywhere else the ground is plain paper — a gradient used as
          filler is exactly the tell this redesign is escaping. */}
      <div
        aria-hidden="true"
        className="bg-ambient-glow pointer-events-none absolute inset-0 -z-10"
      />
      <div className="mx-auto max-w-7xl">
        {/* `MaskedLines`, not `RevealText`: the second line contains a nested
            component, and SplitText's innerHTML rewriting orphans those —
            see MaskedLines' own note. */}
        <MaskedLines
          as="h1"
          trigger="mount"
          className="font-display text-display max-w-5xl font-semibold text-foreground"
          lines={[
            "Ask hard questions.",
            <MarkSweep key="scan" trigger="mount" delay={0.5} duration={0.65}>
              Scan hard code.
            </MarkSweep>,
          ]}
        />

        <p className="hero-reveal measure text-lead mt-8 text-muted">
          Compliance answers with real citations, and a scanner that audits your repository
          against ISO 27001, GDPR, and AI governance.
        </p>

        <div className="hero-reveal mt-9 flex flex-wrap items-center gap-3">
          <MagneticLink
            href="/chat"
            cursorLabel="Ask"
            className={buttonClasses({ size: "lg" })}
          >
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

        <div className="hero-reveal mt-16 sm:mt-20">
          <SplitPreview />
        </div>
      </div>
    </section>
  );
}
