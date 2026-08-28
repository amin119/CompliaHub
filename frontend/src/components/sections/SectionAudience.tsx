"use client";

import { useRef } from "react";
import { useGSAP } from "@gsap/react";
import { gsap } from "@/lib/gsap";
import Eyebrow from "./Eyebrow";

const WHO_ITS_FOR = [
  { label: "COMPLIANCE", size: "text-4xl sm:text-5xl" },
  { label: "LEGAL", size: "text-2xl sm:text-3xl" },
  { label: "RISK", size: "text-3xl sm:text-4xl" },
  { label: "SECURITY", size: "text-2xl sm:text-3xl" },
  { label: "AUDIT", size: "text-4xl sm:text-5xl" },
  { label: "GOVERNANCE", size: "text-2xl sm:text-3xl" },
];

/**
 * Brief section 12: a typographic composition, not six equal cards —
 * mostly complete as static markup already. The one addition here is a
 * subtle scroll-triggered stagger so the words settle into place rather
 * than appearing all at once, consistent with the rest of the page's
 * scroll-scrubbed reveal language.
 */
export default function SectionAudience() {
  const containerRef = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      const words = gsap.utils.toArray<HTMLSpanElement>(".audience-word");
      const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (reducedMotion) {
        gsap.set(words, { opacity: 1, y: 0 });
        return;
      }
      gsap.fromTo(
        words,
        { opacity: 0, y: 14 },
        {
          opacity: 1,
          y: 0,
          stagger: 0.08,
          ease: "none",
          scrollTrigger: {
            trigger: containerRef.current,
            start: "top 85%",
            end: "top 55%",
            scrub: true,
          },
        },
      );
    },
    { scope: containerRef },
  );

  return (
    <section className="font-landing-sans mx-auto w-full max-w-4xl px-4 pb-28 text-center sm:px-8">
      <Eyebrow>Built for people navigating complexity</Eyebrow>
      <div ref={containerRef} className="mt-8 flex flex-wrap items-center justify-center gap-x-6 gap-y-3">
        {WHO_ITS_FOR.map((word) => (
          <span
            key={word.label}
            className={`audience-word font-landing-serif ${word.size} text-landing-fg`}
          >
            {word.label}
          </span>
        ))}
      </div>
    </section>
  );
}
