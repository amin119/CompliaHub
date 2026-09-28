"use client";

import { useRef, type ReactNode } from "react";
import { useGSAP } from "@gsap/react";
import { MOTION, gsap, prefersReducedMotion } from "@/lib/gsap";

/**
 * A phrase with the highlighter drawn across it, left to right.
 *
 * Two identical text layers are stacked — plain underneath, marked on top —
 * and the marked layer's `clip-path` is animated open. That's deliberate:
 * the marked text is dark ink on amber, so animating a single layer's
 * background width would leave the not-yet-highlighted part as dark ink on
 * a dark ground in dark mode. Stacking keeps the phrase fully legible at
 * every frame in both themes.
 *
 * The duplicate layer is `aria-hidden`, so assistive tech reads the phrase
 * once.
 *
 * Applied to a whole phrase, never a single word inside a sentence —
 * recolouring one word of a headline is a template tell, and a marker
 * stroke across a full line is what the product actually does to a clause.
 */
export default function MarkSweep({
  children,
  delay = 0,
  duration = 0.7,
  trigger = "scroll",
  className,
}: {
  children: ReactNode;
  delay?: number;
  duration?: number;
  trigger?: "mount" | "scroll";
  className?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);

  useGSAP(
    () => {
      const layer = ref.current?.querySelector<HTMLElement>(".mark-sweep");
      if (!layer) return;

      if (prefersReducedMotion()) {
        gsap.set(layer, { clipPath: "inset(0 0% 0 0)" });
        return;
      }

      gsap.to(layer, {
        clipPath: "inset(0 0% 0 0)",
        duration,
        delay,
        ease: MOTION.easeOutSoft,
        ...(trigger === "scroll"
          ? { scrollTrigger: { trigger: ref.current, start: "top 80%", once: true } }
          : {}),
      });
    },
    { scope: ref, dependencies: [delay, duration, trigger] },
  );

  return (
    <span ref={ref} className={`relative inline-block ${className ?? ""}`}>
      <span className="relative">{children}</span>
      <span aria-hidden="true" className="mark-sweep absolute inset-0">
        {children}
      </span>
    </span>
  );
}
