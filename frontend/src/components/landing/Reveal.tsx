"use client";

import { useRef } from "react";
import { useGSAP } from "@gsap/react";
import { MOTION, gsap, prefersReducedMotion } from "@/lib/gsap";

/**
 * The generic scroll-reveal for blocks that aren't headings (headings use
 * `RevealText`'s line masks instead). Deliberately restrained: a short rise
 * with no fade-from-zero, because a page where every single block fades up
 * identically is its own kind of template tell. Use it for the two or three
 * moments per section that benefit, not for every element.
 */
export default function Reveal({
  children,
  className,
  delay = 0,
  y = 24,
  start = "top 85%",
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
  y?: number;
  start?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      if (prefersReducedMotion() || !ref.current) return;

      gsap.from(ref.current, {
        opacity: 0,
        y,
        duration: MOTION.durSlow,
        delay,
        ease: MOTION.easeOut,
        scrollTrigger: { trigger: ref.current, start, once: true },
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
