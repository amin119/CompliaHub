"use client";

import { useRef, type ElementType, type ReactNode } from "react";
import { useGSAP } from "@gsap/react";
import { MOTION, gsap, prefersReducedMotion } from "@/lib/gsap";

/**
 * `RevealText` with the line breaks decided by the author instead of by
 * SplitText.
 *
 * Use this for any heading that contains a nested component — a `MarkSweep`,
 * a link, anything React renders. SplitText rewrites the heading's innerHTML
 * to build its masks, and `autoSplit` rewrites it again whenever the text
 * reflows (a font finishing loading, a window resize), which orphans anything
 * React put inside. A `MarkSweep` nested in a `RevealText` therefore either
 * never sweeps or silently un-sweeps later — a real bug this codebase hit on
 * the hero headline.
 *
 * `RevealText` is still the right tool for a heading of plain text, where
 * letting SplitText find the line boundaries is what makes it reflow well.
 *
 * The trade-off here is that the breaks are fixed: a line too long for the
 * viewport wraps inside its own mask and the whole block slides up together,
 * which is fine but less refined than a per-line reveal. Keep the lines short.
 */
export default function MaskedLines({
  lines,
  as: Tag = "h2",
  className,
  delay = 0,
  trigger = "scroll",
  start = "top 82%",
}: {
  lines: ReactNode[];
  as?: ElementType;
  className?: string;
  delay?: number;
  /** `mount` plays immediately (the hero); `scroll` waits for the element. */
  trigger?: "mount" | "scroll";
  start?: string;
}) {
  const ref = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      const element = ref.current;
      if (prefersReducedMotion() || !element) return;

      gsap.from(element.querySelectorAll(".masked-line"), {
        yPercent: 110,
        duration: MOTION.durHero,
        ease: MOTION.easeOut,
        stagger: MOTION.stagger,
        delay,
        ...(trigger === "scroll"
          ? { scrollTrigger: { trigger: element, start, once: true } }
          : {}),
      });
    },
    { scope: ref, dependencies: [trigger, start, delay] },
  );

  return (
    <Tag ref={ref} className={className}>
      {lines.map((line, index) => (
        // The padding/negative-margin pair gives descenders room inside the
        // clipping box without changing the spacing between lines.
        <span key={index} className="-mb-[0.12em] block overflow-hidden pb-[0.12em]">
          <span className="masked-line block">{line}</span>
        </span>
      ))}
    </Tag>
  );
}
