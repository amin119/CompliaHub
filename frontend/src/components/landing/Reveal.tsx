"use client";

import { useRef } from "react";
import { useGSAP } from "@gsap/react";
import { gsap } from "@/lib/gsap";

/**
 * The one scroll-reveal primitive for the landing page's sections — a
 * fade-up triggered when the element scrolls into view, guarded by
 * `prefers-reduced-motion`. Used throughout Showcase/Features/UseCases/
 * FinalCta so the page doesn't feel static once you scroll past the hero.
 */
export default function Reveal({
  children,
  className,
  delay = 0,
  y = 20,
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
  y?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (reducedMotion || !ref.current) return;

      gsap.from(ref.current, {
        opacity: 0,
        y,
        duration: 0.7,
        delay,
        ease: "power2.out",
        scrollTrigger: {
          trigger: ref.current,
          start: "top 85%",
        },
      });
    },
    { scope: ref },
  );

  return (
    <div ref={ref} className={className}>
      {children}
    </div>
  );
}
