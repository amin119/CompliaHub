"use client";

import { useRef, type ElementType, type ReactNode } from "react";
import { useGSAP } from "@gsap/react";
import { MOTION, SplitText, gsap, prefersReducedMotion } from "@/lib/gsap";

/**
 * The signature motion of this design: a heading whose lines are masked and
 * slide up into place, one after another.
 *
 * Uses SplitText's own `mask: "lines"` rather than hand-rolling
 * overflow-hidden wrappers, and `autoSplit: true` so the split is redone if
 * the text reflows — which it will, because the display face (Poppins) loads
 * via `next/font` *after* first paint, and a headline split against the
 * fallback metrics would keep stale line boundaries forever. `onSplit`
 * returns the tween so GSAP owns its lifecycle across those re-splits.
 *
 * Under `prefers-reduced-motion` the text is never split at all — it renders
 * as ordinary markup in its final state, which also keeps it simplest for
 * screen readers.
 *
 * **Plain text only.** Because SplitText rewrites the heading's innerHTML —
 * and `autoSplit` rewrites it again on every reflow — anything React renders
 * inside gets orphaned. A heading containing a `MarkSweep`, a link, or any
 * other component belongs in `MaskedLines` instead.
 */
export default function RevealText({
  children,
  as: Tag = "h2",
  className,
  delay = 0,
  trigger = "scroll",
  start = "top 82%",
  onComplete,
}: {
  children: ReactNode;
  as?: ElementType;
  className?: string;
  delay?: number;
  /** `mount` plays immediately (the hero); `scroll` waits for the element. */
  trigger?: "mount" | "scroll";
  start?: string;
  onComplete?: () => void;
}) {
  const ref = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      const element = ref.current;
      if (!element) return;

      if (prefersReducedMotion()) {
        onComplete?.();
        return;
      }

      const split = SplitText.create(element, {
        type: "lines",
        mask: "lines",
        autoSplit: true,
        onSplit: (self) =>
          gsap.from(self.lines, {
            yPercent: 110,
            duration: MOTION.durHero,
            ease: MOTION.easeOut,
            stagger: MOTION.stagger,
            delay,
            onComplete,
            ...(trigger === "scroll"
              ? { scrollTrigger: { trigger: element, start, once: true } }
              : {}),
          }),
      });

      return () => split.revert();
    },
    { scope: ref, dependencies: [trigger, start, delay] },
  );

  return (
    <Tag ref={ref} className={className}>
      {children}
    </Tag>
  );
}
