"use client";

import { useRef } from "react";
import { useGSAP } from "@gsap/react";
import { gsap } from "@/lib/gsap";

/**
 * Reveals its children one at a time, staggered, the moment the block
 * scrolls into view — used to make the chat-mockup previews (SectionDemo,
 * SectionFeatures) read as a real exchange happening in front of you
 * rather than a static screenshot. Scroll-triggered once (not on every
 * re-entry) so re-scrolling past it doesn't replay the "conversation"
 * on a loop, which would undercut the "this is real" framing it's going
 * for. Falls back to showing everything immediately under
 * `prefers-reduced-motion`.
 */
export default function AnimatedConversation({
  children,
  className,
}: {
  children: React.ReactNode[];
  className?: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      if (!containerRef.current) return;
      const items = gsap.utils.toArray<HTMLElement>(".convo-item", containerRef.current);
      const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

      if (reducedMotion) {
        gsap.set(items, { opacity: 1, y: 0, scale: 1 });
        return;
      }

      gsap.set(items, { opacity: 0, y: 14, scale: 0.98 });
      gsap.to(items, {
        opacity: 1,
        y: 0,
        scale: 1,
        duration: 0.45,
        ease: "power2.out",
        stagger: 0.5,
        scrollTrigger: { trigger: containerRef.current, start: "top 75%", once: true },
      });
    },
    { scope: containerRef },
  );

  return (
    <div ref={containerRef} className={className}>
      {children.map((child, i) => (
        <div key={i} className="convo-item">
          {child}
        </div>
      ))}
    </div>
  );
}
