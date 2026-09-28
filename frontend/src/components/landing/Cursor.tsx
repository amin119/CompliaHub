"use client";

import { useEffect, useRef, useState } from "react";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { gsap } from "@/lib/gsap";

/**
 * The landing page's custom cursor: a small mark that trails the pointer and
 * swells into a labelled pill over anything interactive. On-brand rather than
 * generic — the hover state is the highlighter, so the thing you're about to
 * act on is literally marked.
 *
 * Deliberately landing-only. A custom cursor over the scanner's 200-row
 * findings table would be actively hostile to the person reading it — see
 * DESIGN-SYSTEM.md's two-register principle.
 *
 * Never renders on touch/coarse-pointer devices or under
 * `prefers-reduced-motion`, and the native cursor is only hidden once this
 * component has actually mounted and taken over (the `cursor-none` class is
 * added from JS, never in the static markup) — so if the script fails, the
 * real cursor is still there.
 *
 * Any element can set its own label with `data-cursor="Ask"`.
 */
export default function Cursor() {
  const dotRef = useRef<HTMLDivElement>(null);
  const [label, setLabel] = useState<string | null>(null);
  const [active, setActive] = useState(false);

  const finePointer = useMediaQuery("(pointer: fine)");
  const reducedMotion = useMediaQuery("(prefers-reduced-motion: reduce)");
  const enabled = finePointer && !reducedMotion;

  useEffect(() => {
    if (!enabled) return;
    document.documentElement.classList.add("cursor-none");
    return () => document.documentElement.classList.remove("cursor-none");
  }, [enabled]);

  useEffect(() => {
    const dot = dotRef.current;
    if (!enabled || !dot) return;

    // quickTo keeps this to one interpolated setter per axis instead of
    // creating a tween on every pointermove event.
    const moveX = gsap.quickTo(dot, "x", { duration: 0.35, ease: "power3.out" });
    const moveY = gsap.quickTo(dot, "y", { duration: 0.35, ease: "power3.out" });

    function handleMove(event: PointerEvent) {
      moveX(event.clientX);
      moveY(event.clientY);
    }

    function handleOver(event: PointerEvent) {
      const target = event.target as HTMLElement | null;
      const labelled = target?.closest<HTMLElement>("[data-cursor]");
      if (labelled) {
        setLabel(labelled.dataset.cursor ?? null);
        setActive(true);
        return;
      }
      setLabel(null);
      setActive(Boolean(target?.closest("a, button, [role='button'], input, textarea, select")));
    }

    window.addEventListener("pointermove", handleMove, { passive: true });
    window.addEventListener("pointerover", handleOver, { passive: true });
    return () => {
      window.removeEventListener("pointermove", handleMove);
      window.removeEventListener("pointerover", handleOver);
    };
  }, [enabled]);

  if (!enabled) return null;

  return (
    <div
      ref={dotRef}
      aria-hidden="true"
      className="pointer-events-none fixed top-0 left-0 z-[70] -translate-x-1/2 -translate-y-1/2 will-change-transform"
    >
      <div
        className={`flex items-center justify-center rounded-full font-medium transition-[width,height,background-color,color] duration-200 ease-out ${
          label
            ? "h-auto w-auto bg-mark px-3 py-1.5 text-[11px] text-mark-contrast"
            : active
              ? "h-9 w-9 bg-mark text-[0px]"
              : "h-2.5 w-2.5 bg-accent text-[0px]"
        }`}
      >
        {label}
      </div>
    </div>
  );
}
