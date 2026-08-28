"use client";

import { useRef } from "react";
import { useGSAP } from "@gsap/react";
import { gsap } from "@/lib/gsap";
import { squareSpiral, resolvedPath, type Point } from "@/lib/labyrinth";

const CENTER: Point = [260, 60];
const SPIRAL = squareSpiral(CENTER, 80, 10, 8);
const RESOLVED_D = resolvedPath([0, 60], [520, 60], 8);

/**
 * Brief section 10, deliberately the calmest section: large whitespace,
 * minimal type, the shared labyrinth asset (the same generator the hero
 * and SectionLabyrinth use, `lib/labyrinth.ts`) visually disappearing as
 * the visitor scrolls, leaving only the thread — a genuine breathing
 * moment, not crammed with more content.
 */
export default function SectionClarity() {
  const containerRef = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      const spiral = containerRef.current?.querySelector(".clarity-spiral");
      const line = containerRef.current?.querySelector(".clarity-line");
      if (!spiral || !line) return;

      const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (reducedMotion) {
        gsap.set(spiral, { opacity: 0 });
        gsap.set(line, { drawSVG: "100%", opacity: 1 });
        return;
      }

      gsap.set(line, { drawSVG: "0%" });
      gsap
        .timeline({
          scrollTrigger: {
            trigger: containerRef.current,
            start: "top 75%",
            end: "bottom 55%",
            scrub: true,
          },
        })
        .to(spiral, { opacity: 0, ease: "none" })
        .to(line, { drawSVG: "100%", ease: "none" }, "<");
    },
    { scope: containerRef },
  );

  return (
    <section className="font-landing-sans mx-auto w-full max-w-2xl px-4 py-32 text-center sm:px-8">
      <div ref={containerRef} className="mx-auto mb-10 h-24 w-full max-w-md">
        <svg viewBox="0 0 520 120" className="h-full w-full text-landing-border" aria-hidden="true">
          <path
            d={SPIRAL.d}
            className="clarity-spiral stroke-landing-thread"
            fill="none"
            strokeWidth={1.2}
          />
          <path
            d={RESOLVED_D}
            className="clarity-line stroke-landing-thread"
            fill="none"
            strokeWidth={1.4}
            strokeLinecap="round"
          />
        </svg>
      </div>
      <p className="font-landing-serif text-3xl leading-snug font-normal text-landing-fg sm:text-4xl">
        Complexity in.
        <br />
        Clarity out.
      </p>
    </section>
  );
}
