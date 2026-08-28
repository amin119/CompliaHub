"use client";

import { useRef } from "react";
import { useGSAP } from "@gsap/react";
import { gsap } from "@/lib/gsap";

type ThreadProps = {
  d: string;
  viewBox: string;
  className?: string;
  /** "mount" draws once when the component enters the DOM (used inside
   * already-scroll-revealed sections); "scroll" scrubs the draw to scroll
   * position via its own ScrollTrigger (used for the long inter-section
   * thread and any section that should feel scroll-*caused*, per brief
   * section 6's SectionLabyrinth note). */
  trigger?: "mount" | "scroll";
  duration?: number;
  delay?: number;
};

/**
 * The one shared thread-drawing primitive (brief section 7) — every place
 * a "thread" appears (hero, section dividers, evidence-to-citation links,
 * agent-convergence paths) draws through this same component and the same
 * DrawSVG technique, rather than a slightly different effect hand-rolled
 * per section, so a visitor unconsciously recognizes it as the same
 * drawing tool throughout.
 */
export default function Thread({
  d,
  viewBox,
  className,
  trigger = "scroll",
  duration = 1.4,
  delay = 0,
}: ThreadProps) {
  const containerRef = useRef<SVGSVGElement>(null);
  const pathRef = useRef<SVGPathElement>(null);

  useGSAP(
    () => {
      if (!pathRef.current) return;
      const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (reducedMotion) {
        gsap.set(pathRef.current, { drawSVG: "100%" });
        return;
      }

      if (trigger === "mount") {
        gsap.fromTo(
          pathRef.current,
          { drawSVG: "0%" },
          { drawSVG: "100%", duration, delay, ease: "power2.inOut" },
        );
      } else {
        gsap.fromTo(
          pathRef.current,
          { drawSVG: "0%" },
          {
            drawSVG: "100%",
            ease: "none",
            scrollTrigger: {
              trigger: containerRef.current,
              start: "top 85%",
              end: "bottom 65%",
              scrub: true,
            },
          },
        );
      }
    },
    { scope: containerRef, dependencies: [d, trigger] },
  );

  return (
    <svg ref={containerRef} viewBox={viewBox} className={className} aria-hidden="true">
      <path
        ref={pathRef}
        d={d}
        fill="none"
        className="stroke-landing-thread"
        strokeWidth={1.4}
        strokeLinecap="round"
      />
    </svg>
  );
}
